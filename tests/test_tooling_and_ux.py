"""Integration tests for installer, shell wrappers, scorecard, hygiene, and UX."""

from __future__ import annotations

import base64
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import pty
import re
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest

import yaml

KIT_ROOT = Path(__file__).resolve().parents[1]
if str(KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(KIT_ROOT))

from deepthought.grader import GradeReport, grade_subject  # noqa: E402
from deepthought.scorecard import render_five_gate_scorecard, tilde_path  # noqa: E402
from deepthought.ui_theme import ThemeEngine  # noqa: E402
from deepthought.vogsphere import _is_temp_or_protected_host_home  # noqa: E402


def _load_script(path: Path, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _symlink_bin(dst_dir: Path, name: str, source: Path) -> None:
    target = dst_dir / name
    target.symlink_to(source)


def _build_minimal_toolchain(shim_dir: Path, *, include_bc: bool = True) -> None:
    """Expose standard core tools from host PATH plus shims so install.sh never triggers sudo."""
    shim_dir.mkdir(parents=True, exist_ok=True)
    for exe in (
        "sh",
        "grep",
        "dirname",
        "pwd",
        "readlink",
        "ln",
        "mkdir",
        "printf",
        "cc",
        "gcc",
        "make",
        "git",
        "diff",
        "tar",
        "python3",
    ):
        found = shutil.which(exe)
        if found and not (shim_dir / exe).exists():
            _symlink_bin(shim_dir, exe, Path(found))
    if not (shim_dir / "cc").exists() and (shim_dir / "gcc").exists():
        _symlink_bin(shim_dir, "cc", shim_dir / "gcc")
    if include_bc:
        real_bc = shutil.which("bc") or str(KIT_ROOT / "bin" / "bc")
        _symlink_bin(shim_dir, "bc", Path(real_bc))


class InstallerAndShellNormTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_shnorm_passes_install_sh_and_ifconfig(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(KIT_ROOT / "bin" / "shnorm"),
                "install.sh",
                "bin/ifconfig",
            ],
            cwd=str(KIT_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("install.sh: OK!", proc.stdout)
        self.assertIn("bin/ifconfig: OK!", proc.stdout)

    def test_install_sh_check_and_yes_in_isolated_home(self) -> None:
        home_dir = self.tmp / "home"
        home_dir.mkdir(parents=True, exist_ok=True)
        (home_dir / ".profile").write_text("# user profile\n", encoding="utf-8")

        shim_no_bc = self.tmp / "bin_no_bc"
        _build_minimal_toolchain(shim_no_bc, include_bc=False)
        env_missing = {
            "HOME": str(home_dir),
            "PATH": str(shim_no_bc),
            "TERM": "dumb",
        }
        chk_miss = subprocess.run(
            ["/bin/sh", str(KIT_ROOT / "install.sh"), "--check"],
            cwd=str(KIT_ROOT),
            env=env_missing,
            capture_output=True,
            text=True,
        )
        self.assertEqual(chk_miss.returncode, 1)
        self.assertIn("[MISSING] bc", chk_miss.stdout)
        self.assertIn("Missing packages:", chk_miss.stdout)

        shim_ok = self.tmp / "bin_ok"
        _build_minimal_toolchain(shim_ok, include_bc=True)
        env_install = {
            "HOME": str(home_dir),
            "PATH": str(shim_ok),
            "TERM": "dumb",
        }
        inst = subprocess.run(
            ["/bin/sh", str(KIT_ROOT / "install.sh"), "--yes"],
            cwd=str(KIT_ROOT),
            env=env_install,
            capture_output=True,
            text=True,
        )
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        local_bin = home_dir / ".local" / "bin"
        for tool in (
            "moulinette",
            "deepthought",
            "examshell",
            "norminette",
            "shnorm",
            "ft_lock",
            "bc",
            "ifconfig",
        ):
            link = local_bin / tool
            self.assertTrue(link.is_symlink(), f"missing symlink for {tool}")
            self.assertEqual(link.resolve(), (KIT_ROOT / "bin" / tool).resolve())
        self.assertIn(".local/bin", (home_dir / ".profile").read_text(encoding="utf-8"))

        env_ready = {
            "HOME": str(home_dir),
            "PATH": f"{local_bin}:{shim_ok}",
            "TERM": "dumb",
        }
        chk_ready = subprocess.run(
            ["/bin/sh", str(KIT_ROOT / "install.sh"), "--check"],
            cwd=str(KIT_ROOT),
            env=env_ready,
            capture_output=True,
            text=True,
        )
        self.assertEqual(chk_ready.returncode, 0, chk_ready.stdout + chk_ready.stderr)
        self.assertIn("[OK] Environment is ready.", chk_ready.stdout)


class IfconfigDelegationAndSandboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_delegates_to_system_ifconfig_without_recursion(self) -> None:
        wrapper_dir = self.tmp / "user_bin"
        sys_dir = self.tmp / "sys_bin"
        wrapper_dir.mkdir(parents=True, exist_ok=True)
        sys_dir.mkdir(parents=True, exist_ok=True)

        (wrapper_dir / "ifconfig").symlink_to(KIT_ROOT / "bin" / "ifconfig")
        sys_if = sys_dir / "ifconfig"
        sys_if.write_text(
            "#!/bin/sh\nprintf 'SYS_IFCONFIG:%s\\n' \"$*\"\n", encoding="utf-8"
        )
        sys_if.chmod(0o755)

        env = {"PATH": f"{wrapper_dir}:{sys_dir}:/bin:/usr/bin"}
        res = subprocess.run(
            [str(wrapper_dir / "ifconfig"), "eth0", "ether"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "SYS_IFCONFIG:eth0 ether")

        loop = subprocess.run(
            [str(KIT_ROOT / "bin" / "ifconfig")],
            env=dict(env, DT_IFCONFIG_DELEGATING="1"),
            capture_output=True,
            text=True,
        )
        self.assertEqual(loop.returncode, 127)
        self.assertIn("delegation loop", loop.stderr)

    def test_sandbox_flag_overrides_system_delegation_for_shell_grader(self) -> None:
        sys_dir = self.tmp / "sys_bin"
        sys_dir.mkdir(parents=True, exist_ok=True)
        sys_if = sys_dir / "ifconfig"
        sys_if.write_text(
            "#!/bin/sh\nprintf 'WRONG_SYSTEM_IFCONFIG\\n'\n", encoding="utf-8"
        )
        sys_if.chmod(0o755)

        env = {
            "PATH": f"{sys_dir}:/bin:/usr/bin",
            "DT_SANDBOX_IFCONFIG": "1",
            "DT_MOCK_ETHER": "de:ad:be:ef:42:01",
        }
        res = subprocess.run(
            [str(KIT_ROOT / "bin" / "ifconfig"), "eth0"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("de:ad:be:ef:42:01", res.stdout)
        self.assertNotIn("WRONG_SYSTEM_IFCONFIG", res.stdout)


class ScorecardParityAndGraderHardeningTest(unittest.TestCase):
    def test_scorecard_gate_classification_and_tilde_path_symlink(self) -> None:
        theme = ThemeEngine("plain")
        cases = [
            ("Nothing turned in", False, 0, "gate 1", "Gate 1"),
            ("Cheating (-42)", False, -42, "gate 2", "Gate 2"),
            ("Does not compile", False, 0, "gate 3", "Gate 3"),
            ("Segmentation fault (SIGSEGV)", False, 0, "gate 4", "Gate 4"),
            ("Diff KO :(", False, 0, "gate 5", "Gate 5"),
        ]
        for status, passed, _grade, dot_gate, badge_gate in cases:
            rep = GradeReport("ft_putchar", passed, status, "reason", "trace", "")
            dots = render_five_gate_scorecard(rep, theme, style="dots")
            badges = render_five_gate_scorecard(rep, theme, style="badges")
            dot_line = next(line for line in dots.splitlines() if dot_gate in line)
            badge_line = next(
                line for line in badges.splitlines() if badge_gate in line
            )
            self.assertIn("KO", dot_line, f"{status} -> {dot_line}")
            self.assertIn("[FAIL]", badge_line, f"{status} -> {badge_line}")

        ok_rep = GradeReport("ft_putchar", True, "OK :)", "Passed", "trace", "")
        ok_dots = render_five_gate_scorecard(ok_rep, theme, style="dots")
        ok_badges = render_five_gate_scorecard(ok_rep, theme, style="badges")
        self.assertNotIn("KO", ok_dots)
        self.assertNotIn("FAIL", ok_badges)

        with tempfile.TemporaryDirectory() as td:
            home_like = Path(td)
            real_sub = home_like / "ft_putchar"
            real_sub.mkdir()
            ex00_link = home_like / "ex00"
            ex00_link.symlink_to(real_sub)
            with tempfile.TemporaryDirectory():
                orig_home = os.environ.get("HOME")
                os.environ["HOME"] = str(home_like)
                try:
                    self.assertEqual(tilde_path(ex00_link), "~/ex00")
                finally:
                    if orig_home is None:
                        os.environ.pop("HOME", None)
                    else:
                        os.environ["HOME"] = orig_home

    def test_grader_ignores_stale_object_file_and_builds_from_c_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            poison_c = work / "poison.c"
            poison_c.write_text(
                '#include <unistd.h>\nvoid\tft_putchar(char c)\n{\n\t(void)c;\n\twrite(1, "Z", 1);\n}\n',
                encoding="utf-8",
            )
            stale_o = work / "ft_putchar.o"
            c_res = subprocess.run(
                ["cc", "-c", str(poison_c), "-o", str(stale_o)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(c_res.returncode, 0, c_res.stderr)
            poison_c.unlink()

            good_c = work / "ft_putchar.c"
            good_c.write_text(
                "#include <unistd.h>\n\nvoid\tft_putchar(char c)\n{\n\twrite(1, &c, 1);\n}\n",
                encoding="utf-8",
            )
            os.utime(stale_o, (time.time() + 120, time.time() + 120))

            rep = grade_subject(
                KIT_ROOT,
                "piscine/c00/ft_putchar",
                work,
                is_exam=True,
                strict=False,
                enforce_norm=False,
            )
            self.assertTrue(rep.passed, rep.trace)
            self.assertEqual(rep.grade, 100)


class VogsphereAndExamshellHygieneTest(unittest.TestCase):
    def test_vogsphere_temp_and_isolated_home_rules(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            real_home = Path.home()
            self.assertTrue(_is_temp_or_protected_host_home(tmp_path / "ws", real_home))
            self.assertTrue(
                _is_temp_or_protected_host_home(KIT_ROOT / "build" / "diag", real_home)
            )
            isolated_home = tmp_path / "student_home"
            isolated_home.mkdir()
            self.assertFalse(
                _is_temp_or_protected_host_home(
                    isolated_home / "exam-basedir", isolated_home
                )
            )

    def test_examshell_leaves_kit_workspace_untouched(self) -> None:
        gitkeep = KIT_ROOT / "workspace" / "rendu" / ".gitkeep"
        traces_dir = KIT_ROOT / "workspace" / "traces"
        self.assertTrue(gitkeep.is_file())
        self.assertTrue(traces_dir.is_dir())
        before_stat = gitkeep.stat()

        examshell_mod = _load_script(
            KIT_ROOT / "bin" / "examshell", "examshell_hygiene_test"
        )
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            home_dir = tmp / "home"
            home_dir.mkdir()
            basedir = tmp / "custom_exam_basedir"
            orig_home = os.environ.get("HOME")
            orig_skip = os.environ.get("DT_SKIP_HOME_SYMLINKS")
            os.environ["HOME"] = str(home_dir)
            os.environ["DT_SKIP_HOME_SYMLINKS"] = "1"
            try:
                sess = examshell_mod.ExamShell(
                    "rank02",
                    basedir=basedir,
                    fresh_confirmed=True,
                    no_color=True,
                )
                self.assertFalse(hasattr(sess, "do_solve"))
                self.assertFalse(hasattr(sess, "do_solution"))
                self.assertTrue((basedir / "rendu").is_dir())
                self.assertFalse((basedir / "rendu").is_symlink())
            finally:
                if orig_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = orig_home
                if orig_skip is None:
                    os.environ.pop("DT_SKIP_HOME_SYMLINKS", None)
                else:
                    os.environ["DT_SKIP_HOME_SYMLINKS"] = orig_skip

        self.assertTrue(gitkeep.is_file())
        self.assertFalse(gitkeep.is_symlink())
        self.assertEqual(gitkeep.stat().st_ino, before_stat.st_ino)
        self.assertTrue(traces_dir.is_dir())


class FtLockCliTest(unittest.TestCase):
    def test_ft_lock_status_dry_run_and_check_idle(self) -> None:
        for flag in ("--status", "--dry-run"):
            proc = subprocess.run(
                [sys.executable, str(KIT_ROOT / "bin" / "ft_lock"), flag],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Policy : lock=", proc.stdout)
            self.assertIn("Session:", proc.stdout)

        help_proc = subprocess.run(
            [sys.executable, str(KIT_ROOT / "bin" / "ft_lock"), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(help_proc.returncode, 0)
        self.assertIn("--check-idle", help_proc.stdout)

        idle_proc = subprocess.run(
            [sys.executable, str(KIT_ROOT / "bin" / "ft_lock"), "--check-idle"],
            env=dict(os.environ, TIMEOUT_LOCK_MINUTES="999999"),
            capture_output=True,
            text=True,
        )
        self.assertEqual(idle_proc.returncode, 0, idle_proc.stderr)


class MoulinetteSpartanUxPtyTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_help_and_subject_namesake_and_xp_ledger_consistency(self) -> None:
        help_res = subprocess.run(
            [sys.executable, str(KIT_ROOT / "bin" / "moulinette"), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(help_res.returncode, 0)
        self.assertNotIn("Pro Edition", help_res.stdout)
        self.assertNotIn("c01/c01_ft_strlen", help_res.stdout)
        self.assertIn("c01/ft_strlen", help_res.stdout)

        env = dict(
            os.environ, HOME=str(self.tmp), NO_COLOR="1", DT_SKIP_HOME_SYMLINKS="1"
        )
        subj_res = subprocess.run(
            [
                sys.executable,
                str(KIT_ROOT / "bin" / "moulinette"),
                "--no-color",
                "subject",
                "ft_strlen",
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(subj_res.returncode, 0, subj_res.stderr)
        self.assertIn("also", subj_res.stdout)
        self.assertIn("c01/ft_strlen", subj_res.stdout)
        self.assertIn("exams/ft_strlen", subj_res.stdout)

        prof_path = self.tmp / ".42_student_profile.json"
        prof_path.write_text(
            json.dumps({"login": "tester", "total_xp": 8400, "level": 8.6}),
            encoding="utf-8",
        )
        ledger_path = self.tmp / "ledger.json"
        xp_res = subprocess.run(
            [
                sys.executable,
                str(KIT_ROOT / "bin" / "moulinette"),
                "--no-color",
                "--xp-ledger",
                str(ledger_path),
                "xp",
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(xp_res.returncode, 0, xp_res.stderr)
        self.assertIn("Workspace : 0 XP", xp_res.stdout)
        self.assertIn("Profile   : 8400 XP", xp_res.stdout)

    def test_pty_session_preserves_scrollback_without_banner_or_tip_spam(self) -> None:
        empty_dir = self.tmp / "empty_ex00"
        empty_dir.mkdir()
        ledger = self.tmp / "pty_ledger.json"
        home = self.tmp / "home"
        home.mkdir()

        env = dict(
            os.environ,
            HOME=str(home),
            NO_COLOR="1",
            TERM="xterm-256color",
            DT_SKIP_HOME_SYMLINKS="1",
            MOULINETTE_SCROLLBACK="1",
        )
        env.pop("MOULINETTE_ALT_SCREEN", None)
        env.pop("MOULINETTE_NO_CLEAR", None)

        master, slave = pty.openpty()
        proc = subprocess.Popen(
            [
                sys.executable,
                str(KIT_ROOT / "bin" / "moulinette"),
                "--no-color",
                "--dir",
                str(empty_dir),
                "--xp-ledger",
                str(ledger),
            ],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            close_fds=True,
        )
        os.close(slave)

        script = "1\nc00\nsubject ft_putchar\nft_putchar\ntrace\nxp\nq\n"
        trace_file = (
            KIT_ROOT / "workspace" / "traces" / "piscine__c00__ft_putchar.trace"
        )
        existed_before = trace_file.exists()
        prior_trace = trace_file.read_text(encoding="utf-8") if existed_before else None
        os.write(master, script.encode())

        chunks: list[bytes] = []
        deadline = time.monotonic() + 20.0
        try:
            while time.monotonic() < deadline:
                rlist, _, _ = select.select([master], [], [], 0.2)
                if rlist:
                    try:
                        data = os.read(master, 4096)
                    except OSError:
                        break
                    if not data:
                        break
                    chunks.append(data)
                elif proc.poll() is not None:
                    break
        finally:
            os.close(master)
            if existed_before and prior_trace is not None:
                trace_file.write_text(prior_trace, encoding="utf-8")
            else:
                trace_file.unlink(missing_ok=True)
        proc.wait(timeout=5.0)

        out = b"".join(chunks).decode("utf-8", errors="replace")
        self.assertEqual(proc.returncode, 0, out)
        self.assertNotIn("\x1b[?1049h", out)
        self.assertNotIn("\x1b[2J", out)
        self.assertNotIn("=[ moulinette", out)
        self.assertNotIn("tip:", out)
        self.assertNotIn("==================== TRACE ====================", out)
        self.assertIn("moulinette (piscine/c00)>", out)
        self.assertIn("Summary: ft_putchar -> Nothing turned in", out)
        self.assertIn("Workspace : 0 XP", out)
        self.assertIn("trace file:", out)
        self.assertIn("moulinette>", out)
        self.assertNotIn("moulinette (grade)>", out)

    def test_responsive_catalog_widths_and_alt_screen_navigation(self) -> None:
        import fcntl
        import termios

        ansi_re = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

        # 1. All catalog tables fit cleanly within <= 79 columns on both 80-col and 140-col terminals,
        #    and c00 renders full filenames without premature ellipsis truncation.
        for cols in (80, 140):
            for target in ("piscine", "c00", "exams"):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(KIT_ROOT / "bin" / "moulinette"),
                        "--no-color",
                        "list",
                        target,
                    ],
                    cwd=str(KIT_ROOT),
                    env=dict(
                        os.environ,
                        HOME=str(self.tmp),
                        COLUMNS=str(cols),
                        LINES="40",
                        NO_COLOR="1",
                    ),
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                plain_lines = [
                    ansi_re.sub("", ln) for ln in proc.stdout.splitlines() if ln.strip()
                ]
                self.assertTrue(
                    all(len(ln) <= 79 for ln in plain_lines),
                    f"target={target} cols={cols}: {plain_lines}",
                )
                if target == "c00":
                    self.assertIn("ft_print_reverse_alphabet.c", proc.stdout)

        # 2. Interactive TTY enters bounded examshell-style alt-screen viewport by default; --scrollback keeps classic scrollback.
        def _run_pty(
            extra_args: list[str], payload: bytes, rows: int = 40, cols: int = 140
        ) -> tuple[int, str]:
            env = dict(
                os.environ,
                HOME=str(self.tmp),
                NO_COLOR="1",
                TERM="xterm-256color",
                DT_SKIP_HOME_SYMLINKS="1",
            )
            env.pop("MOULINETTE_ALT_SCREEN", None)
            env.pop("MOULINETTE_SCROLLBACK", None)
            env.pop("MOULINETTE_NO_CLEAR", None)
            master, slave = pty.openpty()
            fcntl.ioctl(
                slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0)
            )
            proc = subprocess.Popen(
                [
                    sys.executable,
                    str(KIT_ROOT / "bin" / "moulinette"),
                    "--no-color",
                    *extra_args,
                ],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                cwd=str(KIT_ROOT),
                env=env,
                close_fds=True,
            )
            os.close(slave)
            os.write(master, payload)
            chunks: list[bytes] = []
            deadline = time.monotonic() + 15.0
            try:
                while time.monotonic() < deadline:
                    rlist, _, _ = select.select([master], [], [], 0.2)
                    if rlist:
                        try:
                            data = os.read(master, 4096)
                        except OSError:
                            break
                        if not data:
                            break
                        chunks.append(data)
                    elif proc.poll() is not None:
                        break
            finally:
                os.close(master)
                if proc.poll() is None:
                    proc.kill()
            proc.wait(timeout=5.0)
            return proc.returncode, b"".join(chunks).decode("utf-8", errors="replace")

        rc_quiet, quiet_out = _run_pty(["--scrollback"], b"q\n")
        self.assertEqual(rc_quiet, 0, quiet_out)
        self.assertNotIn("\x1b[?1049h", quiet_out)
        self.assertNotIn("\x1b[2J", quiet_out)
        self.assertNotIn("42 / 1337 catalog sections", quiet_out)
        self.assertLessEqual(len(quiet_out.splitlines()), 3, quiet_out)

        rc_alt, alt_out = _run_pty(
            [], b"1\nc00\nback\nforward\nhelp\nback\nq\n", rows=40, cols=140
        )
        self.assertEqual(rc_alt, 0, alt_out)
        self.assertIn("\x1b[?1049h", alt_out)
        self.assertIn("\x1b[?1049l", alt_out)
        self.assertIn("########.fr", alt_out)
        self.assertIn("42 / 1337 Deepthought Grader (v0.1.1)", alt_out)
        self.assertIn("42 / 1337 catalog sections", alt_out)
        self.assertNotIn("Don't Panic", alt_out)
        self.assertNotIn("=[ moulinette", alt_out)
        self.assertNotIn("system summary", alt_out)
        self.assertNotIn("Student:", alt_out)
        self.assertNotIn("View:", alt_out)
        initial_frame = next(
            (
                f
                for f in alt_out.split("\x1b[H\x1b[2J")
                if "42 / 1337 catalog sections" in f
            ),
            alt_out,
        )
        self.assertEqual(
            len(re.findall(r"nav:", ansi_re.sub("", initial_frame))), 1, initial_frame
        )
        self.assertIn("moulinette (piscine/c00)>", alt_out)
        self.assertGreaterEqual(alt_out.count("\x1b[H\x1b[2J"), 6, alt_out)
        self.assertIn("ft_print_reverse_alphabet.c", alt_out)

        # Interactive sequence waiting for ViewportSession raw-mode before sending Tab / Ctrl+U.
        env_p = dict(
            os.environ,
            HOME=str(self.tmp),
            NO_COLOR="1",
            TERM="xterm-256color",
            DT_SKIP_HOME_SYMLINKS="1",
        )
        env_p.pop("MOULINETTE_ALT_SCREEN", None)
        env_p.pop("MOULINETTE_SCROLLBACK", None)
        env_p.pop("MOULINETTE_NO_CLEAR", None)
        master_p, slave_p = pty.openpty()
        fcntl.ioctl(slave_p, termios.TIOCSWINSZ, struct.pack("HHHH", 18, 80, 0, 0))
        proc_p = subprocess.Popen(
            [sys.executable, str(KIT_ROOT / "bin" / "moulinette"), "--no-color"],
            stdin=slave_p,
            stdout=slave_p,
            stderr=slave_p,
            cwd=str(KIT_ROOT),
            env=env_p,
            close_fds=True,
        )
        os.close(slave_p)
        page_buf = bytearray()
        scan_pos = 0

        def _read_until(needle: bytes, timeout_s: float = 5.0) -> None:
            nonlocal scan_pos
            deadline = time.monotonic() + timeout_s
            while time.monotonic() < deadline:
                found_at = page_buf.find(needle, scan_pos)
                if found_at != -1:
                    scan_pos = found_at + len(needle)
                    return
                rlist, _, _ = select.select([master_p], [], [], 0.05)
                if rlist:
                    try:
                        d = os.read(master_p, 4096)
                    except OSError:
                        break
                    if not d:
                        break
                    page_buf.extend(d)
                elif proc_p.poll() is not None:
                    break

        try:
            _read_until(b"moulinette>")
            os.write(master_p, b"1\n")
            _read_until(b"moulinette (piscine)>")
            os.write(master_p, b"more\n")
            _read_until(b"pager (Enter/k/g/G/q)>")
            os.write(master_p, b"j\n")
            _read_until(b"5-20/20")
            os.write(master_p, b"q\n")
            _read_until(b"moulinette (piscine)>")
            os.write(master_p, b"ft_put\t")
            _read_until(b"completions: ft_putchar")
            os.write(master_p, b"\x15q\n")
            _read_until(b"\x1b[?1049l")
            rc_page = proc_p.wait(timeout=5.0)
            while True:
                rlist, _, _ = select.select([master_p], [], [], 0.05)
                if not rlist:
                    break
                try:
                    d = os.read(master_p, 4096)
                except OSError:
                    break
                if not d:
                    break
                page_buf.extend(d)
        finally:
            os.close(master_p)
            if proc_p.poll() is None:
                proc_p.kill()
                proc_p.wait(timeout=2.0)
        page_out = page_buf.decode("utf-8", errors="replace")
        self.assertEqual(rc_page, 0, page_out)
        self.assertIn("[Showing ", page_out)
        self.assertIn("type 'more' to page", page_out)
        self.assertIn("j/Enter=down, k=up", page_out)
        self.assertIn("completions: ft_putchar", page_out)


class TestSubjectHygiene(unittest.TestCase):
    """Permanent regression checks across all piscine and exam subject specs."""

    _TAG_RE = re.compile(
        r"\[(?:cur|can|cpp|pool)_[a-z0-9_]+\]|\[EN\]|\[TR\]|\[SUBJECT MAIN\]",
        re.IGNORECASE,
    )
    _BAR_RE = re.compile(r"^={8,}\s*$", re.MULTILINE)
    _DUMP_RE = re.compile(r"^>>>", re.MULTILINE)
    _RECON_RE = re.compile(r"(?:Reconstruction note|Code-only imported)", re.IGNORECASE)
    _VER_RE = re.compile(r"^Version\s*:", re.MULTILINE)
    _BLANK_ALLOWED_RE = re.compile(
        r"^(?:Allowed functions|Allowed commands)\s*:\s*$",
        re.MULTILINE,
    )
    _TAIL_PROMPT_RE = re.compile(r"^(?:\$>|\?>|~\$|S>)\s*$")
    _CURLY_RE = re.compile(r"[‘’“”]")
    _BAD_CMDS = frozenset(
        {"./rstr_capitalizer", "./chessmate", "./validator", "./a.out", "$", "zaz$"}
    )

    def _iter_exercises(self):
        exercises = []
        for track in ("piscine", "exams"):
            for meta_path in sorted((KIT_ROOT / "subjects" / track).rglob("meta.yml")):
                exercises.append((track, meta_path.parent))
        return exercises

    def _check_text_hygiene(
        self,
        rel: str,
        label: str,
        text: str,
        track: str,
        ex_type: str,
        issues: list[str],
    ) -> None:
        if self._DUMP_RE.search(text):
            issues.append(f"{rel}/{label}: leaked >>> dump")
        if self._BAR_RE.search(text):
            issues.append(f"{rel}/{label}: leaked ==== bar")
        if self._TAG_RE.search(text):
            issues.append(f"{rel}/{label}: leaked internal tag")
        if "\u200b" in text:
            issues.append(f"{rel}/{label}: zero-width space")
        if self._RECON_RE.search(text):
            issues.append(f"{rel}/{label}: reconstruction note")
        if self._VER_RE.search(text):
            issues.append(f"{rel}/{label}: Version metadata line")
        if self._BLANK_ALLOWED_RE.search(text):
            issues.append(f"{rel}/{label}: blank Allowed header")
        lines = text.splitlines()
        non_empty = [ln for ln in lines if ln.strip()]
        if non_empty and self._TAIL_PROMPT_RE.match(non_empty[-1]):
            issues.append(
                f"{rel}/{label}: trailing standalone prompt {non_empty[-1]!r}"
            )
        if track == "exams" and self._CURLY_RE.search(text):
            issues.append(f"{rel}/{label}: curly quotes in exam")
        if ex_type == "c_function" and any(
            re.match(r"^\$>", ln.lstrip()) for ln in lines
        ):
            issues.append(f"{rel}/{label}: c_function contains $> prompt")
        if label == "examples.txt":
            if "Clean execution" in text:
                issues.append(f"{rel}/{label}: contains Clean execution placeholder")
            non_comment = [
                ln.strip()
                for ln in lines
                if ln.strip() and not ln.strip().startswith("#")
            ]
            if non_comment and re.match(r"^example\b", non_comment[0]):
                issues.append(
                    f"{rel}/{label}: starts with slice fragment {non_comment[0]!r}"
                )

    def _check_headers(
        self, rel: str, subj: str, meta: dict, issues: list[str]
    ) -> None:
        ex_id = str(meta.get("id", ""))
        expected_files = meta.get("expected_files", [])
        if isinstance(expected_files, str):
            expected_files = [expected_files]

        m_assign = re.search(r"^Assignment name\s*:\s*(.+)$", subj, re.MULTILINE)
        if not m_assign:
            issues.append(f"{rel}/subject.en.txt: missing Assignment name")
        else:
            aname = m_assign.group(1).strip()
            if aname != ex_id and not (
                ex_id == "vbc (without tree)" and aname == "vbc"
            ):
                issues.append(
                    f"{rel}/subject.en.txt: Assignment name {aname!r} != {ex_id!r}"
                )

        m_exp = re.search(r"^Expected files\s*:\s*(.*)$", subj, re.MULTILINE)
        if not m_exp:
            issues.append(f"{rel}/subject.en.txt: missing Expected files")
        else:
            ef_raw = m_exp.group(1).strip()
            if ef_raw == "" and expected_files:
                issues.append(f"{rel}/subject.en.txt: blank Expected files header")
            elif ef_raw not in ("", "None"):
                header_files = [
                    tok.strip() for tok in re.split(r"[\s,]+", ef_raw) if tok.strip()
                ]
                if sorted(header_files) != sorted(expected_files):
                    issues.append(
                        f"{rel}/subject.en.txt: Expected files {header_files} != {expected_files}"
                    )

    def _check_tests_yml(
        self, rel: str, ex_dir: Path, meta: dict, issues: list[str]
    ) -> None:
        tests_path = ex_dir / "tests.yml"
        if not tests_path.exists():
            return
        ex_id = str(meta.get("id", ""))
        ex_type = str(meta.get("type", ""))
        data = yaml.safe_load(tests_path.read_text(encoding="utf-8")) or {}
        for section in ("subject_examples", "near_examples"):
            for idx, case in enumerate(data.get(section) or []):
                cmd = str(case.get("command", ""))
                args = [str(a) for a in (case.get("args") or [])]
                exp = str(case.get("expected", ""))
                if section == "subject_examples" and ex_type == "c_function":
                    if cmd != f"eval {ex_id}":
                        issues.append(
                            f"{rel}/tests.yml: {section}[{idx}] command {cmd!r} != 'eval {ex_id}'"
                        )
                if cmd in self._BAD_CMDS or cmd.endswith("$") or "\n" in cmd:
                    issues.append(
                        f"{rel}/tests.yml: {section}[{idx}] bad command {cmd!r}"
                    )
                if "| cat -e" in exp:
                    issues.append(
                        f"{rel}/tests.yml: {section}[{idx}] expected leaks pipe"
                    )
                for arg in args:
                    if re.search(r"(?:→|-->)", arg) or (
                        "=" in arg and not re.match(r"^[A-Z0-9_]+=", arg)
                    ):
                        issues.append(
                            f"{rel}/tests.yml: {section}[{idx}] bad arg {arg!r}"
                        )

    def test_all_subjects_hygiene(self) -> None:
        exercises = self._iter_exercises()
        self.assertEqual(len(exercises), 439)
        self.assertEqual(sum(1 for track, _ in exercises if track == "piscine"), 136)
        self.assertEqual(sum(1 for track, _ in exercises if track == "exams"), 303)

        issues: list[str] = []
        for track, ex_dir in exercises:
            rel = ex_dir.relative_to(KIT_ROOT).as_posix()
            meta = yaml.safe_load((ex_dir / "meta.yml").read_text(encoding="utf-8"))
            ex_type = str(meta.get("type", ""))
            subj_path = ex_dir / "subject.en.txt"
            ex_path = ex_dir / "examples.txt"
            if not subj_path.exists():
                issues.append(f"{rel}: missing subject.en.txt")
                continue
            if not ex_path.exists():
                issues.append(f"{rel}: missing examples.txt")
                continue
            subj = subj_path.read_text(encoding="utf-8")
            ext = ex_path.read_text(encoding="utf-8")
            self._check_text_hygiene(
                rel, "subject.en.txt", subj, track, ex_type, issues
            )
            self._check_text_hygiene(rel, "examples.txt", ext, track, ex_type, issues)
            self._check_headers(rel, subj, meta, issues)
            self._check_tests_yml(rel, ex_dir, meta, issues)

        self.assertEqual(issues, [], "\n".join(issues))

    def test_targeted_subject_regressions(self) -> None:
        ft_div = (KIT_ROOT / "subjects/exams/ft_div/subject.en.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("int ft_div(int a, int b);", ft_div)

        fix_loop = (KIT_ROOT / "subjects/exams/fix_loop/subject.en.txt").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("while (i < len);", fix_loop)

        for header in ("c08/ft_boolean.h", "c08/ft_abs.h"):
            text = (
                KIT_ROOT / "subjects/piscine" / header / "subject.en.txt"
            ).read_text(encoding="utf-8")
            self.assertIn(
                "Norminette must be launched with the -R CheckDefine flag.", text
            )
            self.assertIn("Moulinette will use it too.", text)

        brainfuck = (KIT_ROOT / "subjects/exams/brainfuck/subject.en.txt").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("+++++[>++++[>++++H>+++++i<<-]\n", brainfuck)


class TestEvaluatorHardeningBatch1(unittest.TestCase):
    """Verify Batch 1 fixes: captured-bug tests, 10-queens verifier, ft_boolean.h, and shell checks."""

    @staticmethod
    def _hdr(fname: str) -> str:
        return (
            "/* ************************************************************************** */\n"
            "/*                                                                            */\n"
            "/*                                                        :::      ::::::::   */\n"
            f"/*   {fname:<51}*/\n"
            "/*                                                    +:+ +:+         +:+     */\n"
            "/*   By: marvin <marvin@42.fr>                      +#+  +:+       +#+        */\n"
            "/*                                                +#+#+#+#+#+   +#+           */\n"
            "/*   Created: 2026/01/01 00:00:00 by marvin            #+#    #+#             */\n"
            "/*   Updated: 2026/01/01 00:00:00 by marvin           ###   ########.fr       */\n"
            "/*                                                                            */\n"
            "/* ************************************************************************** */\n"
        )

    def test_c07_ft_convert_base_int_min(self) -> None:
        sdir = KIT_ROOT / "subjects/piscine/c07/ft_convert_base"
        cdir = KIT_ROOT / "corrections/piscine/c07/ft_convert_base"
        tests = yaml.safe_load((sdir / "tests.yml").read_text(encoding="utf-8"))
        t10 = [
            t
            for t in tests["fixed_tests"]
            if t.get("name") == "test_10_int_min_and_max"
        ][0]
        self.assertEqual(t10["stdout"], "-2147483648:2147483647\n")
        rep = grade_subject(
            KIT_ROOT,
            "ft_convert_base",
            cdir,
            strict=True,
            enforce_norm=True,
            subj_dir_override=sdir,
        )
        self.assertTrue(rep.passed, rep.trace[-400:])

    def test_rush_bsq_sudoku_and_bsq_invalid_inputs(self) -> None:
        sud_sdir = KIT_ROOT / "subjects/piscine/rush_bsq/sudoku"
        sud_cdir = KIT_ROOT / "corrections/piscine/rush_bsq/sudoku"
        sud_tests = yaml.safe_load((sud_sdir / "tests.yml").read_text(encoding="utf-8"))
        t09 = [
            t
            for t in sud_tests["fixed_tests"]
            if t.get("name") == "test_09_duplicate_in_first_row_error"
        ][0]
        self.assertEqual(t09["stdout"], "Error\n")
        self.assertTrue(
            grade_subject(
                KIT_ROOT,
                "sudoku",
                sud_cdir,
                strict=True,
                enforce_norm=True,
                subj_dir_override=sud_sdir,
            ).passed
        )

        bsq_sdir = KIT_ROOT / "subjects/piscine/rush_bsq/bsq"
        bsq_cdir = KIT_ROOT / "corrections/piscine/rush_bsq/bsq"
        bsq_tests = yaml.safe_load((bsq_sdir / "tests.yml").read_text(encoding="utf-8"))
        t10 = [
            t
            for t in bsq_tests["fixed_tests"]
            if t.get("name") == "test_10_invalid_map_error"
        ][0]
        self.assertEqual(t10["stdout"], "")
        self.assertEqual(t10["stderr"], "map error\n")
        self.assertTrue(
            grade_subject(
                KIT_ROOT,
                "bsq",
                bsq_cdir,
                strict=True,
                enforce_norm=True,
                subj_dir_override=bsq_sdir,
            ).passed
        )

    def test_ten_queens_rejects_fakes_and_accepts_reference(self) -> None:
        sdir = KIT_ROOT / "subjects/piscine/c05/ft_ten_queens_puzzle"
        cdir = KIT_ROOT / "corrections/piscine/c05/ft_ten_queens_puzzle"
        self.assertTrue(
            grade_subject(
                KIT_ROOT,
                "ft_ten_queens_puzzle",
                cdir,
                strict=True,
                enforce_norm=True,
                subj_dir_override=sdir,
            ).passed
        )
        hdr = self._hdr("ft_ten_queens_puzzle.c")
        for fake_body in (
            "\nint\tft_ten_queens_puzzle(void)\n{\n\treturn (724);\n}\n",
            '\n#include <unistd.h>\n\nint\tft_ten_queens_puzzle(void)\n{\n\tint\ti;\n\n\ti = 0;\n\twhile (i < 724)\n\t{\n\t\twrite(1, "0257948136\\n", 11);\n\t\ti++;\n\t}\n\treturn (724);\n}\n',
        ):
            with tempfile.TemporaryDirectory() as td:
                tp = Path(td)
                (tp / "ft_ten_queens_puzzle.c").write_text(
                    hdr + fake_body, encoding="utf-8"
                )
                rep = grade_subject(
                    KIT_ROOT,
                    "ft_ten_queens_puzzle",
                    tp,
                    enforce_norm=True,
                    subj_dir_override=sdir,
                )
                self.assertFalse(rep.passed)
                self.assertEqual(rep.status, "Diff KO :(")

    def test_ft_boolean_header_requires_msgs_and_unistd(self) -> None:
        sdir = KIT_ROOT / "subjects/piscine/c08/ft_boolean.h"
        cdir = KIT_ROOT / "corrections/piscine/c08/ft_boolean.h"
        self.assertTrue(
            grade_subject(
                KIT_ROOT,
                "ft_boolean.h",
                cdir,
                strict=True,
                enforce_norm=True,
                subj_dir_override=sdir,
            ).passed
        )
        hdr = self._hdr("ft_boolean.h")
        cases = [
            (
                "Does not compile",
                "\n#ifndef FT_BOOLEAN_H\n# define FT_BOOLEAN_H\n\n# include <unistd.h>\n\n"
                "# define TRUE 1\n# define FALSE 0\n# define SUCCESS 0\n# define EVEN(nbr) ((nbr % 2) == 0)\n\n"
                "typedef int\tt_bool;\n\n#endif\n",
            ),
            (
                "Diff KO :(",
                "\n#ifndef FT_BOOLEAN_H\n# define FT_BOOLEAN_H\n\n# include <unistd.h>\n\n"
                "# define TRUE 1\n# define FALSE 0\n# define SUCCESS 0\n# define EVEN(nbr) ((nbr % 2) == 0)\n"
                '# define EVEN_MSG "even\\n"\n# define ODD_MSG "odd\\n"\n\ntypedef int\tt_bool;\n\n#endif\n',
            ),
            (
                "Does not compile",
                "\n#ifndef FT_BOOLEAN_H\n# define FT_BOOLEAN_H\n\n"
                "# define TRUE 1\n# define FALSE 0\n# define SUCCESS 0\n# define EVEN(nbr) ((nbr % 2) == 0)\n"
                '# define EVEN_MSG "I have an even number of arguments.\\n"\n'
                '# define ODD_MSG "I have an odd number of arguments.\\n"\n\ntypedef int\tt_bool;\n\n#endif\n',
            ),
        ]
        for exp_status, body in cases:
            with tempfile.TemporaryDirectory() as td:
                tp = Path(td)
                (tp / "ft_boolean.h").write_text(hdr + body, encoding="utf-8")
                rep = grade_subject(
                    KIT_ROOT,
                    "ft_boolean.h",
                    tp,
                    enforce_norm=True,
                    subj_dir_override=sdir,
                )
                self.assertFalse(rep.passed)
                self.assertEqual(rep.status, exp_status)

    def test_shell_evaluator_hardened_checks(self) -> None:
        marvin_sdir = KIT_ROOT / "subjects/piscine/shell01/special_filename_MaRViN"
        marvin_exact = yaml.safe_load(
            (marvin_sdir / "meta.yml").read_text(encoding="utf-8")
        )["expected_files"][0]
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            (tp / marvin_exact).write_text("42", encoding="utf-8")
            self.assertTrue(
                grade_subject(
                    KIT_ROOT,
                    "special_filename_MaRViN",
                    tp,
                    subj_dir_override=marvin_sdir,
                ).passed
            )
        for fname, body, exp in (
            ("wrong_MaRViN_file", "42", "Nothing turned in"),
            (marvin_exact, "42\n", "Diff KO :("),
        ):
            with tempfile.TemporaryDirectory() as td:
                tp = Path(td)
                (tp / fname).write_text(body, encoding="utf-8")
                rep = grade_subject(
                    KIT_ROOT,
                    "special_filename_MaRViN",
                    tp,
                    subj_dir_override=marvin_sdir,
                )
                self.assertFalse(rep.passed)
                self.assertEqual(rep.status, exp)

        rsa_sdir = KIT_ROOT / "subjects/piscine/shell00/id_rsa_pub"
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            raw = (
                struct.pack(">I", 11)
                + b"ssh-ed25519"
                + struct.pack(">I", 32)
                + b"\x01" * 32
            )
            (tp / "id_rsa_pub").write_text(
                f"ssh-ed25519 {base64.b64encode(raw).decode('ascii')} u@42\n",
                encoding="utf-8",
            )
            self.assertTrue(
                grade_subject(
                    KIT_ROOT, "id_rsa_pub", tp, subj_dir_override=rsa_sdir
                ).passed
            )
        for bad_key in (
            "ssh-fake NOT_EVEN_BASE64\n",
            "ssh-rsa AAAA_WRONG_WIRE_HEADER_00000000000000000\n",
        ):
            with tempfile.TemporaryDirectory() as td:
                tp = Path(td)
                (tp / "id_rsa_pub").write_text(bad_key, encoding="utf-8")
                self.assertFalse(
                    grade_subject(
                        KIT_ROOT, "id_rsa_pub", tp, subj_dir_override=rsa_sdir
                    ).passed
                )

        bh_sdir = KIT_ROOT / "subjects/exams/black_hole"
        self.assertTrue(
            grade_subject(
                KIT_ROOT,
                "black_hole",
                KIT_ROOT / "corrections/exams/black_hole",
                is_exam=True,
                subj_dir_override=bh_sdir,
            ).passed
        )
        for bad_sh in (
            "#!/bin/sh\n# 2>/dev/null\necho OK\n",
            "#!/bin/sh\nprintf '2>/dev/null' >/dev/null\necho OK\n",
            "#!/bin/sh\nls /nonexistent_x 2>/dev/null || true\necho err >&2\necho OK\n",
            "#!/bin/sh\nls /nonexistent_x 2>/dev/null || true\ntouch junk.tmp\necho OK\n",
        ):
            with tempfile.TemporaryDirectory() as td:
                tp = Path(td)
                (tp / "black_hole.sh").write_text(bad_sh, encoding="utf-8")
                self.assertFalse(
                    grade_subject(
                        KIT_ROOT,
                        "black_hole",
                        tp,
                        is_exam=True,
                        subj_dir_override=bh_sdir,
                    ).passed
                )


class TestEvaluatorHardeningBatch2(unittest.TestCase):
    """Verify Batch 2 fixes: __CAPTURE__/mode cleanup, C++ contracts, socket/microshell harnesses."""

    def test_no_capture_placeholders_or_type_mode_mismatches(self) -> None:
        mismatches = []
        cap_hits = []
        empty_main_hits = []
        for meta_p in sorted(KIT_ROOT.glob("subjects/*/**/meta.yml")):
            tests_p = meta_p.parent / "tests.yml"
            if not tests_p.exists():
                continue
            meta = yaml.safe_load(meta_p.read_text(encoding="utf-8")) or {}
            txt = tests_p.read_text(encoding="utf-8")
            if "__CAPTURE__" in txt:
                cap_hits.append(meta_p.parent.as_posix())
            if "main_code: ''" in txt:
                empty_main_hits.append(meta_p.parent.as_posix())
            tests = yaml.safe_load(txt) or {}
            mt, tm = meta.get("type"), tests.get("mode")
            if tm is not None and mt != tm:
                mismatches.append((meta_p.parent.as_posix(), mt, tm))
        self.assertEqual(cap_hits, [])
        self.assertEqual(empty_main_hits, [])
        self.assertEqual(mismatches, [])

    def test_c08_ft_abs_rejects_unparenthesized_macro(self) -> None:
        sdir = KIT_ROOT / "subjects/piscine/c08/ft_abs.h"
        cdir = KIT_ROOT / "corrections/piscine/c08/ft_abs.h"
        self.assertTrue(
            grade_subject(
                KIT_ROOT,
                "ft_abs.h",
                cdir,
                strict=True,
                enforce_norm=True,
                subj_dir_override=sdir,
            ).passed
        )
        hdr = TestEvaluatorHardeningBatch1._hdr("ft_abs.h")
        bad_abs = (
            hdr
            + "\n#ifndef FT_ABS_H\n# define FT_ABS_H\n\n# define ABS(Value) (Value < 0 ? -Value : Value)\n\n#endif\n"
        )
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            (tp / "ft_abs.h").write_text(bad_abs, encoding="utf-8")
            rep = grade_subject(
                KIT_ROOT, "ft_abs.h", tp, enforce_norm=True, subj_dir_override=sdir
            )
            self.assertFalse(rep.passed)
            self.assertEqual(rep.status, "Diff KO :(")

    def test_cpp_must_not_compile_and_extra_tests(self) -> None:
        for sid in (
            "bigint",
            "vect2",
            "cpp_module_00",
            "cpp_module_01",
            "cpp_module_02",
        ):
            rep = grade_subject(
                KIT_ROOT,
                sid,
                KIT_ROOT / "corrections/exams" / sid,
                is_exam=True,
                strict=True,
                subj_dir_override=KIT_ROOT / "subjects/exams" / sid,
            )
            self.assertTrue(rep.passed, f"{sid}: {rep.status}\n{rep.trace[-500:]}")

        # 64-bit fake bigint must fail the arbitrary-precision extra C++ test (2^70)
        bigint_sdir = KIT_ROOT / "subjects/exams/bigint"
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            (tp / "bigint.hpp").write_text(
                "#ifndef BIGINT_HPP\n# define BIGINT_HPP\n# include <iostream>\n"
                "class bigint {\n unsigned long long v;\npublic:\n"
                " bigint(unsigned long long n = 0) : v(n) {}\n"
                " bigint(const bigint& o) : v(o.v) {}\n"
                " bigint& operator=(const bigint& o) { v = o.v; return *this; }\n"
                " bigint& operator++() { ++v; return *this; }\n"
                " bigint operator++(int) { bigint t(*this); ++v; return t; }\n"
                " bigint operator+(const bigint& o) const { return bigint(v + o.v); }\n"
                " bigint& operator+=(const bigint& o) { v += o.v; return *this; }\n"
                " bigint operator<<(int s) const { unsigned long long r = v; for (int i = 0; i < s; ++i) r *= 10; return bigint(r); }\n"
                " bigint operator<<(const bigint& o) const { return *this << (int)o.v; }\n"
                " bigint operator>>(int s) const { unsigned long long r = v; for (int i = 0; i < s; ++i) r /= 10; return bigint(r); }\n"
                " bigint operator>>(const bigint& o) const { return *this >> (int)o.v; }\n"
                " bigint& operator<<=(int s) { *this = *this << s; return *this; }\n"
                " bigint& operator<<=(const bigint& o) { return *this <<= (int)o.v; }\n"
                " bigint& operator>>=(int s) { *this = *this >> s; return *this; }\n"
                " bigint& operator>>=(const bigint& o) { return *this >>= (int)o.v; }\n"
                " bool operator<(const bigint& o) const { return v < o.v; }\n"
                " bool operator>(const bigint& o) const { return v > o.v; }\n"
                " bool operator<=(const bigint& o) const { return v <= o.v; }\n"
                " bool operator>=(const bigint& o) const { return v >= o.v; }\n"
                " bool operator==(const bigint& o) const { return v == o.v; }\n"
                " bool operator!=(const bigint& o) const { return v != o.v; }\n"
                " friend std::ostream& operator<<(std::ostream& os, const bigint& b) { return os << b.v; }\n"
                "};\n#endif\n",
                encoding="utf-8",
            )
            (tp / "bigint.cpp").write_text('#include "bigint.hpp"\n', encoding="utf-8")
            rep_bg = grade_subject(
                KIT_ROOT, "bigint", tp, is_exam=True, subj_dir_override=bigint_sdir
            )
            self.assertFalse(rep_bg.passed)
            self.assertEqual(rep_bg.status, "Diff KO :(")

        # Public copyable Warlock must fail must_not_compile in cpp_module_01
        cpp01_sdir = KIT_ROOT / "subjects/exams/cpp_module_01"
        cpp01_cdir = KIT_ROOT / "corrections/exams/cpp_module_01"
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            for fp in cpp01_cdir.iterdir():
                shutil.copy2(fp, tp / fp.name)
            wh = (tp / "Warlock.hpp").read_text(encoding="utf-8")
            # Expose copy ctor publicly so non-copyable must_not_compile check catches it
            wh_bad = wh.replace(
                "Warlock(const Warlock&);",
                "public:\n\t\tWarlock(const Warlock&) {}\n\tprivate:",
            )
            (tp / "Warlock.hpp").write_text(wh_bad, encoding="utf-8")
            rep_01 = grade_subject(
                KIT_ROOT,
                "cpp_module_01",
                tp,
                is_exam=True,
                subj_dir_override=cpp01_sdir,
            )
            self.assertFalse(rep_01.passed)
            self.assertEqual(rep_01.status, "Diff KO :(")

    def test_mini_db_mini_serv_and_microshell_harnesses(self) -> None:
        for sid in ("mini_db", "mini_serv", "microshell"):
            rep = grade_subject(
                KIT_ROOT,
                sid,
                KIT_ROOT / "corrections/exams" / sid,
                is_exam=True,
                strict=True,
                subj_dir_override=KIT_ROOT / "subjects/exams" / sid,
            )
            self.assertTrue(rep.passed, f"{sid}: {rep.status}\n{rep.trace[-500:]}")

        # microshell that leaks pipe FDs in parent must fail 50-pipe RLIMIT_NOFILE=25 check
        ms_sdir = KIT_ROOT / "subjects/exams/microshell"
        orig = (KIT_ROOT / "corrections/exams/microshell/microshell.c").read_text(
            encoding="utf-8"
        )
        lines = orig.splitlines()
        patched = []
        for ln in lines:
            if "if (has_pipe && (dup2(fd[0], 0)" in ln:
                patched.append("\tif (has_pipe && dup2(fd[0], 0) == -1)")
            else:
                patched.append(ln)
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            (tp / "microshell.c").write_text(
                "\n".join(patched) + "\n", encoding="utf-8"
            )
            rep_ms = grade_subject(
                KIT_ROOT, "microshell", tp, is_exam=True, subj_dir_override=ms_sdir
            )
            self.assertFalse(rep_ms.passed)

        # mini_db that skips saving on SIGINT must fail tcp_persistence_sigint_restart
        mdb_sdir = KIT_ROOT / "subjects/exams/mini_db"
        mdb_cdir = KIT_ROOT / "corrections/exams/mini_db"
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            for fp in mdb_cdir.glob("mini_db.*"):
                shutil.copy2(fp, tp / fp.name)
            bad_cpp = (
                (tp / "mini_db.cpp")
                .read_text(encoding="utf-8")
                .replace(
                    'file << it->first << " " << it->second << std::endl;',
                    "(void)it;",
                )
            )
            (tp / "mini_db.cpp").write_text(bad_cpp, encoding="utf-8")
            rep_mdb = grade_subject(
                KIT_ROOT, "mini_db", tp, is_exam=True, subj_dir_override=mdb_sdir
            )
            self.assertFalse(rep_mdb.passed)

        # mini_serv that uses raw fd (reused after disconnect) instead of monotonic next_id must fail
        msv_sdir = KIT_ROOT / "subjects/exams/mini_serv"
        msv_csrc = (KIT_ROOT / "corrections/exams/mini_serv/mini_serv.c").read_text(
            encoding="utf-8"
        )
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            (tp / "mini_serv.c").write_text(
                msv_csrc.replace("ids[fd] = next_id++;", "ids[fd] = fd;"),
                encoding="utf-8",
            )
            rep_msv = grade_subject(
                KIT_ROOT, "mini_serv", tp, is_exam=True, subj_dir_override=msv_sdir
            )
            self.assertFalse(rep_msv.passed)


class TestEvaluatorHardeningBatch3(unittest.TestCase):
    """Verify Batch 3 fixes: zero *_auto tests, bzero symbol check, shell/c_program fixes, and INT boundaries."""

    def test_no_auto_generated_tests_remaining(self) -> None:
        auto_hits = []
        tests_files = sorted(KIT_ROOT.glob("subjects/*/**/tests.yml"))
        self.assertEqual(len(tests_files), 439)
        for tests_p in tests_files:
            data = yaml.safe_load(tests_p.read_text(encoding="utf-8")) or {}
            for key in ("tests", "fixed_tests", "oracle_tests"):
                for item in data.get(key) or []:
                    name = str((item or {}).get("name", ""))
                    if "_auto" in name:
                        auto_hits.append(
                            (tests_p.relative_to(KIT_ROOT).as_posix(), key, name)
                        )
        self.assertEqual(auto_hits, [])

    def test_bzero_rejects_empty_and_noop_stubs(self) -> None:
        sdir = KIT_ROOT / "subjects/exams/bzero"
        cdir = KIT_ROOT / "corrections/exams/bzero"
        self.assertTrue(
            grade_subject(
                KIT_ROOT,
                "bzero",
                cdir,
                is_exam=True,
                strict=True,
                subj_dir_override=sdir,
            ).passed
        )
        for bad_src, exp_status in (
            ("/* empty stub */\n", "Does not compile"),
            (
                "#include <stddef.h>\nvoid bzero(void *s, size_t n) { (void)s; (void)n; }\n",
                "Diff KO :(",
            ),
        ):
            with tempfile.TemporaryDirectory() as td:
                tp = Path(td)
                (tp / "bzero.c").write_text(bad_src, encoding="utf-8")
                rep = grade_subject(
                    KIT_ROOT, "bzero", tp, is_exam=True, subj_dir_override=sdir
                )
                self.assertFalse(rep.passed)
                self.assertEqual(rep.status, exp_status)

    def test_shell_zombie_hunter_and_matrix_trans_contracts(self) -> None:
        for sid in ("zombie_hunter", "matrix_trans"):
            rep = grade_subject(
                KIT_ROOT,
                sid,
                KIT_ROOT / "corrections/exams" / sid,
                is_exam=True,
                strict=True,
                subj_dir_override=KIT_ROOT / "subjects/exams" / sid,
            )
            self.assertTrue(rep.passed, f"{sid}: {rep.status}\n{rep.trace[-400:]}")

        zh_sdir = KIT_ROOT / "subjects/exams/zombie_hunter"
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            (tp / "zombie_hunter.sh").write_text(
                "#!/bin/sh\nawk '$1 == \"Z\" { print $2 }'\n", encoding="utf-8"
            )
            rep_zh = grade_subject(
                KIT_ROOT, "zombie_hunter", tp, is_exam=True, subj_dir_override=zh_sdir
            )
            self.assertFalse(rep_zh.passed)
            self.assertEqual(rep_zh.status, "Diff KO :(")

    def test_c_program_batch3_fixes_slice_vbc_infin(self) -> None:
        for sid in ("slice", "vbc", "infin_add", "infin_mult"):
            rep = grade_subject(
                KIT_ROOT,
                sid,
                KIT_ROOT / "corrections/exams" / sid,
                is_exam=True,
                strict=True,
                subj_dir_override=KIT_ROOT / "subjects/exams" / sid,
            )
            self.assertTrue(rep.passed, f"{sid}: {rep.status}\n{rep.trace[-400:]}")

        vbc_cfg = (
            yaml.safe_load(
                (KIT_ROOT / "subjects/exams/vbc/tests.yml").read_text(encoding="utf-8")
            )
            or {}
        )
        by_name = {t["name"]: t for t in (vbc_cfg.get("fixed_tests") or [])}
        self.assertEqual(by_name["subj_ex_07"]["stdout"], "Unexpected end of input\n")
        self.assertEqual(by_name["subj_ex_07"]["expected_returncode"], 1)
        self.assertEqual(by_name["subj_ex_08"]["stdout"], "Unexpected token ')'\n")
        self.assertEqual(by_name["subj_ex_08"]["expected_returncode"], 1)
        self.assertEqual(by_name["subj_ex_15"]["stdout"], "Unexpected token '2'\n")
        self.assertEqual(by_name["subj_ex_15"]["expected_returncode"], 1)

        # Unguarded slice checking av[1][1] directly must fail when av[1] is ""
        slice_sdir = KIT_ROOT / "subjects/exams/slice"
        slice_src = (KIT_ROOT / "corrections/exams/slice/slice.c").read_text(
            encoding="utf-8"
        )
        bad_slice = slice_src.replace(
            "if (ac == 3 && av[1][0] != '\\0')", "if (ac == 3)"
        )
        self.assertNotEqual(bad_slice, slice_src)
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            (tp / "slice.c").write_text(bad_slice, encoding="utf-8")
            rep_sl = grade_subject(
                KIT_ROOT, "slice", tp, is_exam=True, subj_dir_override=slice_sdir
            )
            self.assertFalse(rep_sl.passed)

    def test_c_function_batch3_boundaries_and_add_binary(self) -> None:
        checks = [
            (
                "add_binary",
                "subjects/exams/add_binary",
                "corrections/exams/add_binary",
                True,
                False,
            ),
            (
                "ft_atoi",
                "subjects/exams/ft_atoi",
                "corrections/exams/ft_atoi",
                True,
                False,
            ),
            (
                "is_power_of_2",
                "subjects/exams/is_power_of_2",
                "corrections/exams/is_power_of_2",
                True,
                False,
            ),
            (
                "count_of_2",
                "subjects/exams/count_of_2",
                "corrections/exams/count_of_2",
                True,
                False,
            ),
            (
                "ft_sqrt",
                "subjects/piscine/c05/ft_sqrt",
                "corrections/piscine/c05/ft_sqrt",
                False,
                True,
            ),
            (
                "ft_range",
                "subjects/piscine/c07/ft_range",
                "corrections/piscine/c07/ft_range",
                False,
                True,
            ),
        ]
        for sid, srel, crel, is_exam, norm in checks:
            rep = grade_subject(
                KIT_ROOT,
                sid,
                KIT_ROOT / crel,
                is_exam=is_exam,
                strict=True,
                enforce_norm=norm,
                subj_dir_override=KIT_ROOT / srel,
            )
            self.assertTrue(rep.passed, f"{sid}: {rep.status}\n{rep.trace[-400:]}")

        # add_binary returning "0" instead of "" for ("", "") must fail edge_both_empty
        ab_sdir = KIT_ROOT / "subjects/exams/add_binary"
        ab_src = (KIT_ROOT / "corrections/exams/add_binary/add_binary.c").read_text(
            encoding="utf-8"
        )
        bad_ab = ab_src.replace(
            "    buf[k] = '\\0';",
            "    if (k == 0)\n        buf[k++] = '0';\n    buf[k] = '\\0';",
        )
        self.assertNotEqual(bad_ab, ab_src)
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            (tp / "add_binary.c").write_text(bad_ab, encoding="utf-8")
            rep_ab = grade_subject(
                KIT_ROOT, "add_binary", tp, is_exam=True, subj_dir_override=ab_sdir
            )
            self.assertFalse(rep_ab.passed)
            self.assertEqual(rep_ab.status, "Diff KO :(")


class TestEvaluatorHardeningBatch4(unittest.TestCase):
    """Covers Batch 4 hardening: allowed_functions parity, leak probes, stderr, extra files, and Real-42 defaults/switches."""

    def test_allowed_functions_parity_and_symbol_checks(self) -> None:
        for rel, sid in [
            ("exams/filter", "filter"),
            ("exams/powerset", "powerset"),
            ("exams/sandbox", "sandbox"),
            ("exams/tsp", "tsp"),
        ]:
            rep = grade_subject(
                KIT_ROOT,
                sid,
                KIT_ROOT / "corrections" / rel,
                is_exam=True,
                strict=True,
                subj_dir_override=KIT_ROOT / "subjects" / rel,
            )
            self.assertTrue(rep.passed, f"{rel}: {rep.status}\n{rep.trace[-400:]}")

        # filter subject allows calloc + memmove without triggering Cheating (-42)
        with tempfile.TemporaryDirectory() as td:
            sub = Path(td) / "filter"
            sub.mkdir()
            (sub / "filter.c").write_text(
                "#define _GNU_SOURCE\n"
                "#include <unistd.h>\n#include <stdlib.h>\n#include <string.h>\n"
                "int main(int ac, char **av) {\n"
                "  if (ac != 2 || !av[1][0]) return 1;\n"
                "  char *p = calloc(4096, 1);\n"
                "  if (!p) return 1;\n"
                "  ssize_t n = read(0, p, 4095);\n"
                "  size_t plen = strlen(av[1]);\n"
                "  char *m;\n"
                "  while (n > 0 && (m = memmem(p, (size_t)n, av[1], plen)) != NULL) {\n"
                "    for (size_t i = 0; i < plen; i++) m[i] = '*';\n"
                "  }\n"
                "  if (n > 0) write(1, p, (size_t)n);\n"
                "  free(p);\n"
                "  return 0;\n"
                "}\n",
                encoding="utf-8",
            )
            rep_f = grade_subject(
                KIT_ROOT,
                "filter",
                sub,
                is_exam=True,
                strict=True,
                subj_dir_override=KIT_ROOT / "subjects/exams/filter",
            )
            self.assertTrue(
                rep_f.passed,
                f"filter calloc/memmem failed: {rep_f.status}\n{rep_f.trace[-400:]}",
            )

    def test_malloc_c_function_leak_detection_batch4(self) -> None:
        suites = [
            ("exams/clone_list", "clone_list", "clone_list.c", True),
            ("exams/cycle_detector", "cycle_detector", "cycle_detector.c", True),
            ("exams/eval_expr", "eval_expr", "eval_expr.c", True),
            ("exams/ft_itoa_base", "ft_itoa_base", "ft_itoa_base.c", True),
            ("exams/ft_printf", "ft_printf", "ft_printf.c", True),
            ("exams/ft_split", "ft_split", "ft_split.c", True),
            ("exams/range_comb", "range_comb", "range_comb.c", True),
            (
                "piscine/c07/ft_split_whitespaces",
                "ft_split_whitespaces",
                "ft_split_whitespaces.c",
                False,
            ),
            ("piscine/c08/ft_strs_to_tab", "ft_strs_to_tab", "ft_strs_to_tab.c", False),
            ("piscine/c12/ft_create_elem", "ft_create_elem", "ft_create_elem.c", False),
            (
                "piscine/c13/btree_apply_by_level",
                "btree_apply_by_level",
                "btree_apply_by_level.c",
                False,
            ),
            (
                "piscine/c13/btree_create_node",
                "btree_create_node",
                "btree_create_node.c",
                False,
            ),
        ]
        with tempfile.TemporaryDirectory() as td:
            for rel, sid, fname, is_ex in suites:
                sub = Path(td) / sid
                shutil.copytree(KIT_ROOT / "corrections" / rel, sub)
                src = sub / fname
                txt = src.read_text(encoding="utf-8")
                if "#include <stdlib.h>" not in txt:
                    lines = txt.splitlines(keepends=True)
                    insert_at = 0 if is_ex else 12
                    lines.insert(insert_at, "#include <stdlib.h>\n")
                    txt = "".join(lines)
                clean_txt = re.sub(
                    r"/\*.*?\*/", lambda m: " " * len(m.group(0)), txt, flags=re.DOTALL
                )
                m_fn = re.search(rf"\b{re.escape(sid)}\s*\(", clean_txt)
                idx = m_fn.start() if m_fn else -1
                self.assertNotEqual(idx, -1, rel)
                brace_start = clean_txt.find("{", idx)
                self.assertNotEqual(brace_start, -1, rel)
                depth = 0
                end = -1
                for pos in range(brace_start, len(clean_txt)):
                    if clean_txt[pos] == "{":
                        depth += 1
                    elif clean_txt[pos] == "}":
                        depth -= 1
                        if depth == 0:
                            end = pos
                            break
                self.assertNotEqual(end, -1, rel)
                if sid == "btree_apply_by_level":
                    txt = txt[:end] + "\tif (!malloc(16))\n\t\treturn ;\n" + txt[end:]
                else:
                    ridx = clean_txt.rfind("return", idx, end)
                    self.assertNotEqual(ridx, -1, rel)
                    semi = txt.find(";", ridx)
                    stmt = txt[ridx : semi + 1]
                    if "(" in stmt:
                        inner = stmt[stmt.find("return") + 6 :].strip()[:-1].strip()
                        if inner.startswith("(") and inner.endswith(")"):
                            inner = inner[1:-1].strip()
                        txt = (
                            txt[:ridx]
                            + f"return ((void)malloc(16), {inner});"
                            + txt[semi + 1 :]
                        )
                    else:
                        expr = stmt[stmt.find("return") + 6 : -1].strip()
                        txt = (
                            txt[:ridx]
                            + f"return ((void)malloc(16), ({expr}));"
                            + txt[semi + 1 :]
                        )
                src.write_text(txt, encoding="utf-8")
                rep = grade_subject(
                    KIT_ROOT,
                    sid,
                    sub,
                    is_exam=is_ex,
                    strict=True,
                    enforce_norm=not is_ex,
                    subj_dir_override=KIT_ROOT / "subjects" / rel,
                )
                self.assertFalse(
                    rep.passed, f"{rel} failed to reject leaked malloc(16)"
                )
                self.assertIn(
                    "Leak", rep.status, f"{rel} -> {rep.status}\n{rep.trace[-400:]}"
                )

    def test_stderr_and_null_boundary_contracts(self) -> None:
        for rel, sid, is_ex in [
            ("exams/fix_result", "fix_result", True),
            ("exams/list_trait", "list_trait", True),
            ("exams/stderr_trap", "stderr_trap", True),
            ("piscine/c11/ft_map", "ft_map", False),
            ("piscine/c11/ft_is_sort", "ft_is_sort", False),
        ]:
            rep = grade_subject(
                KIT_ROOT,
                sid,
                KIT_ROOT / "corrections" / rel,
                is_exam=is_ex,
                strict=True,
                subj_dir_override=KIT_ROOT / "subjects" / rel,
            )
            self.assertTrue(rep.passed, f"{rel}: {rep.status}\n{rep.trace[-400:]}")

        with tempfile.TemporaryDirectory() as td:
            # fix_result with wrong stderr text on argc != 2 must fail
            fr_dir = Path(td) / "fix_result"
            shutil.copytree(KIT_ROOT / "corrections/exams/fix_result", fr_dir)
            fr_src = (fr_dir / "fix_result.c").read_text(encoding="utf-8")
            (fr_dir / "fix_result.c").write_text(
                fr_src.replace('"Error !\\n", 8', '"Wrong !\\n", 8'), encoding="utf-8"
            )
            rep_fr = grade_subject(
                KIT_ROOT,
                "fix_result",
                fr_dir,
                is_exam=True,
                subj_dir_override=KIT_ROOT / "subjects/exams/fix_result",
            )
            self.assertFalse(rep_fr.passed)
            self.assertIn("Stderr", rep_fr.reason)

            # stderr_trap leaking to stderr must fail shell evaluator
            st_dir = Path(td) / "stderr_trap"
            st_dir.mkdir()
            (st_dir / "stderr_trap.sh").write_text(
                "#!/bin/sh\necho err >&2\necho captured\n", encoding="utf-8"
            )
            rep_st = grade_subject(
                KIT_ROOT,
                "stderr_trap",
                st_dir,
                is_exam=True,
                subj_dir_override=KIT_ROOT / "subjects/exams/stderr_trap",
            )
            self.assertFalse(rep_st.passed)
            self.assertIn("Diff KO", rep_st.status)

    def test_extraneous_turnin_files_rejected_while_o_and_subject_h_allowed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            # Extra main.c in C turn-in rejected
            c_dir = Path(td) / "ft_putchar"
            shutil.copytree(KIT_ROOT / "corrections/piscine/c00/ft_putchar", c_dir)
            (c_dir / "main.c").write_text(
                "int main(void) { return 0; }\n", encoding="utf-8"
            )
            rep_c = grade_subject(
                KIT_ROOT,
                "ft_putchar",
                c_dir,
                strict=True,
                subj_dir_override=KIT_ROOT / "subjects/piscine/c00/ft_putchar",
            )
            self.assertFalse(rep_c.passed)
            self.assertEqual(rep_c.status, "Extraneous file(s) in turn-in directory")

            # Stale .o is still ignored and passes
            (c_dir / "main.c").unlink()
            (c_dir / "ft_putchar.o").write_text("stale obj", encoding="utf-8")
            rep_o = grade_subject(
                KIT_ROOT,
                "ft_putchar",
                c_dir,
                strict=True,
                subj_dir_override=KIT_ROOT / "subjects/piscine/c00/ft_putchar",
            )
            self.assertTrue(rep_o.passed, rep_o.trace)

            # Subject header ft_stock_str.h in ft_strs_to_tab is allowed
            rep_h = grade_subject(
                KIT_ROOT,
                "ft_strs_to_tab",
                KIT_ROOT / "corrections/piscine/c08/ft_strs_to_tab",
                strict=True,
                subj_dir_override=KIT_ROOT / "subjects/piscine/c08/ft_strs_to_tab",
            )
            self.assertTrue(rep_h.passed, rep_h.trace)

            # Extra helper file in C++ turn-in rejected
            cpp_dir = Path(td) / "mini_db"
            shutil.copytree(KIT_ROOT / "corrections/exams/mini_db", cpp_dir)
            (cpp_dir / "scratch.txt").write_text("leftover", encoding="utf-8")
            rep_cpp = grade_subject(
                KIT_ROOT,
                "mini_db",
                cpp_dir,
                is_exam=True,
                subj_dir_override=KIT_ROOT / "subjects/exams/mini_db",
            )
            self.assertFalse(rep_cpp.passed)
            self.assertEqual(rep_cpp.status, "Extraneous file(s) in turn-in directory")

    def test_real42_hidden_trace_defaults_and_helpful_switches(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home_dir = Path(td) / "home"
            home_dir.mkdir()
            env = {**os.environ, "HOME": str(home_dir), "NO_COLOR": "1"}
            sub = Path(td) / "ft_atoi"
            sub.mkdir()
            (sub / "ft_atoi.c").write_text(
                "int ft_atoi(const char *str) { (void)str; return (999); }\n",
                encoding="utf-8",
            )

            # Library default is hidden (real 42); reveal_tests=True shows unified diff
            rep_real = grade_subject(
                KIT_ROOT, "ft_atoi", sub, is_exam=True, strict=True
            )
            rep_help = grade_subject(
                KIT_ROOT, "ft_atoi", sub, is_exam=True, strict=True, reveal_tests=True
            )
            self.assertFalse(rep_real.passed)
            self.assertIn("$> ./user_exe 1", rep_real.trace)
            self.assertNotIn("@@", rep_real.trace)
            self.assertNotIn("subj_ex_zero", rep_real.trace)
            self.assertEqual(rep_real.expected_cat_e, "")
            self.assertEqual(rep_real.actual_cat_e, "")
            self.assertIn("@@", rep_help.trace)
            self.assertIn("subj_ex_zero", rep_help.trace)
            self.assertIn("0$", rep_help.expected_cat_e)

            # bin/deepthought defaults to real (hidden), --helpful reveals diff
            dt_real_trace = Path(td) / "dt_real.trace"
            dt_help_trace = Path(td) / "dt_help.trace"
            subprocess.run(
                [
                    sys.executable,
                    str(KIT_ROOT / "bin/deepthought"),
                    "grade",
                    "exams/ft_atoi",
                    "--dir",
                    str(sub),
                    "--trace-out",
                    str(dt_real_trace),
                    "--no-color",
                ],
                cwd=KIT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertNotIn("@@", dt_real_trace.read_text(encoding="utf-8"))
            subprocess.run(
                [
                    sys.executable,
                    str(KIT_ROOT / "bin/deepthought"),
                    "grade",
                    "exams/ft_atoi",
                    "--dir",
                    str(sub),
                    "--helpful",
                    "--trace-out",
                    str(dt_help_trace),
                    "--no-color",
                ],
                cwd=KIT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertIn("@@", dt_help_trace.read_text(encoding="utf-8"))

            # bin/moulinette defaults to real (hidden), --trace-mode helpful reveals diff
            ledger = Path(td) / "xp.json"
            p_m_real = subprocess.run(
                [
                    sys.executable,
                    str(KIT_ROOT / "bin/moulinette"),
                    "ft_atoi",
                    "--exam",
                    "--dir",
                    str(sub),
                    "--xp-ledger",
                    str(ledger),
                    "--no-color",
                ],
                cwd=KIT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotIn("@@", p_m_real.stdout)
            p_m_help = subprocess.run(
                [
                    sys.executable,
                    str(KIT_ROOT / "bin/moulinette"),
                    "ft_atoi",
                    "--exam",
                    "--dir",
                    str(sub),
                    "--trace-mode",
                    "helpful",
                    "--xp-ledger",
                    str(ledger),
                    "--no-color",
                ],
                cwd=KIT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertIn("@@", p_m_help.stdout)

            # c_program continues showing diff -U 3 even when reveal_tests=False
            cprog = Path(td) / "aff_a"
            cprog.mkdir()
            (cprog / "aff_a.c").write_text(
                '#include <unistd.h>\nint main(void) { write(1, "x\\n", 2); return 0; }\n',
                encoding="utf-8",
            )
            rep_cp = grade_subject(
                KIT_ROOT, "aff_a", cprog, is_exam=True, reveal_tests=False
            )
            self.assertFalse(rep_cp.passed)
            self.assertIn("diff -U 3", rep_cp.trace)
            self.assertIn("@@", rep_cp.trace)

    def test_examshell_strict_and_real42_cooldown_and_mode_switchers(self) -> None:
        es_mod = _load_script(KIT_ROOT / "bin/examshell", "examshell_batch4_test")
        with tempfile.TemporaryDirectory() as td:
            home_dir = Path(td) / "home"
            home_dir.mkdir()
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = str(home_dir)
            try:
                now_box = [1_700_000_000.0]
                basedir = Path(td) / "exam"
                import datetime as _dt
                from unittest import mock

                shell = es_mod.ExamShell(
                    pool="rank02",
                    level=0,
                    seed=2,
                    practice=True,
                    basedir=basedir,
                    login="student42",
                    clock_fn=lambda: _dt.datetime.fromtimestamp(
                        now_box[0], tz=_dt.timezone.utc
                    ),
                    fresh_confirmed=True,
                )
                self.assertEqual(shell.trace_mode, "real")
                self.assertEqual(shell.cooldown_mode, "real")
                self.assertEqual(shell._cooldown_penalty_for_attempt(1), 60)
                self.assertEqual(shell._cooldown_penalty_for_attempt(2), 120)
                self.assertEqual(shell._cooldown_penalty_for_attempt(3), 240)

                # Test interactive trace-mode & cooldown mode switching + persistence
                shell.onecmd("trace-mode helpful")
                shell.onecmd("cooldown mode linear")
                self.assertEqual(shell.trace_mode, "helpful")
                self.assertEqual(shell.cooldown_mode, "linear")
                self.assertEqual(shell._cooldown_penalty_for_attempt(1), 30)
                self.assertEqual(shell._cooldown_penalty_for_attempt(2), 60)
                saved = json.loads(
                    (basedir / ".session.json").read_text(encoding="utf-8")
                )
                self.assertEqual(saved["trace_mode"], "helpful")
                self.assertEqual(saved["cooldown_mode"], "linear")

                # Switch back to real & push a leaking solution -> check strict=True catches Leak KO
                shell.onecmd("trace-mode real")
                shell.onecmd("cooldown mode real")
                slug = shell.current_assignment
                self.assertEqual(slug, "ft_range")
                sub_dir = basedir / "rendu" / slug
                sub_dir.mkdir(parents=True, exist_ok=True)
                src_file = sub_dir / f"{slug}.c"
                shutil.copytree(
                    KIT_ROOT / "corrections/exams" / slug, sub_dir, dirs_exist_ok=True
                )
                src_txt = src_file.read_text(encoding="utf-8")
                src_file.write_text(
                    src_txt.replace("return (res);", "return ((void)malloc(16), res);"),
                    encoding="utf-8",
                )
                shell.onecmd("push")
                with mock.patch("builtins.input", return_value="y"):
                    shell.onecmd("grademe")
                self.assertEqual(shell.attempts, 1)
                self.assertEqual(shell.last_penalty_sec, 60)
                tr_text = next(shell.traces_dir.glob("*.trace")).read_text(
                    encoding="utf-8"
                )
                self.assertIn("Leak", tr_text)

                # Second failure with --now doubles cooldown to 120s in real mode
                now_box[0] += 5.0
                with mock.patch("builtins.input", return_value="y"):
                    shell.onecmd("grademe --now")
                self.assertEqual(shell.attempts, 2)
                self.assertEqual(shell.last_penalty_sec, 120)
            finally:
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home


class TestShellEvaluatorHardening01Edu(unittest.TestCase):
    def test_forbidden_commands_and_patterns_on_shell_scripts(self) -> None:
        from deepthought.shell_evaluator import evaluate_shell_exercise

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subj_dir = root / "subj"
            subj_dir.mkdir()
            (subj_dir / "tests.yml").write_text(
                yaml.safe_dump(
                    {
                        "forbidden_commands": ["echo"],
                        "forbidden_patterns": ["cat <<", r"re:printf\s+\"hardcoded\""],
                        "fixed_tests": [{"args": [], "stdout": "ok\n"}],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            meta = {"id": "custom_shell", "type": "shell", "expected_files": ["run.sh"]}

            clean_dir = root / "clean"
            clean_dir.mkdir()
            (clean_dir / "run.sh").write_text(
                '#!/bin/sh\n# echo "commented out"\nmsg="echo"\nprintf "ok\\n"\n',
                encoding="utf-8",
            )
            res_ok = evaluate_shell_exercise(
                KIT_ROOT, "custom_shell", clean_dir, meta, subj_dir=subj_dir
            )
            self.assertTrue(res_ok.ok, res_ok.trace_lines)

            for idx, bad_code in enumerate(
                [
                    "#!/bin/sh\necho ok\n",
                    "#!/bin/sh\n/bin/echo ok\n",
                    "#!/bin/sh\ncat <<EOF\nok\nEOF\n",
                    '#!/bin/sh\nprintf "hardcoded"\n',
                ],
                start=1,
            ):
                bad_dir = root / f"bad_{idx}"
                bad_dir.mkdir()
                (bad_dir / "run.sh").write_text(bad_code, encoding="utf-8")
                res_bad = evaluate_shell_exercise(
                    KIT_ROOT, "custom_shell", bad_dir, meta, subj_dir=subj_dir
                )
                self.assertFalse(res_bad.ok)
                self.assertEqual(res_bad.reason, "Cheating (-42)", bad_code)

    def test_declarative_file_assertions_modes_symlinks_oracle_and_cleanup(
        self,
    ) -> None:
        from deepthought.shell_evaluator import evaluate_shell_exercise

        oracle_code = (
            "#!/bin/sh\n"
            "mkdir -p out_dir\n"
            "chmod 0750 out_dir\n"
            "printf 'hello' > out_dir/res.txt\n"
            "chmod 0640 out_dir/res.txt\n"
            "ln -s link_src.txt out_link\n"
            "rm -f sub/tmp.bak\n"
        )
        tests_cfg = {
            "fixed_tests": [
                {
                    "args": [],
                    "expect_empty": True,
                    "files": {
                        "ro_dir": {"dir": True},
                        "ro_dir/keep.txt": {"content": "keep\n", "mode": "0444"},
                        "locked": {"dir": True},
                        "locked/inside.txt": {"content": "x"},
                        "sub/tmp.bak": "stale",
                        "link_src.txt": {"content": "payload\n", "mode": "0640"},
                    },
                    "file_modes": {"ro_dir": "0504", "locked": "0303"},
                    "absent_files": ["sub/tmp.bak"],
                    "file_assertions": [
                        {"path": "out_dir", "type": "dir", "mode": "0750"},
                        {
                            "path": "out_dir/res.txt",
                            "type": "file",
                            "mode": "0640",
                            "size": 5,
                            "content": "hello",
                            "content_contains": ["ell"],
                            "matches_oracle": True,
                        },
                        {
                            "path": "out_link",
                            "type": "symlink",
                            "symlink_target": "link_src.txt",
                            "matches_oracle": True,
                        },
                    ],
                }
            ]
        }
        meta = {
            "id": "fs_side_effects",
            "type": "shell",
            "expected_files": ["setup.sh"],
            "golden_oracle": oracle_code,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subj_dir = root / "subj"
            subj_dir.mkdir()
            (subj_dir / "tests.yml").write_text(
                yaml.safe_dump(tests_cfg, sort_keys=False), encoding="utf-8"
            )

            ok_dir = root / "ok_sub"
            ok_dir.mkdir()
            (ok_dir / "setup.sh").write_text(oracle_code, encoding="utf-8")
            res_ok = evaluate_shell_exercise(
                KIT_ROOT, "fs_side_effects", ok_dir, meta, subj_dir=subj_dir
            )
            self.assertTrue(res_ok.ok, res_ok.trace_lines)

            bad_perm_dir = root / "bad_perm"
            bad_perm_dir.mkdir()
            (bad_perm_dir / "setup.sh").write_text(
                oracle_code.replace("chmod 0640", "chmod 0600"), encoding="utf-8"
            )
            res_perm = evaluate_shell_exercise(
                KIT_ROOT, "fs_side_effects", bad_perm_dir, meta, subj_dir=subj_dir
            )
            self.assertFalse(res_perm.ok)
            self.assertEqual(res_perm.reason, "Wrong permissions")

            bad_link_dir = root / "bad_link"
            bad_link_dir.mkdir()
            (bad_link_dir / "setup.sh").write_text(
                oracle_code.replace(
                    "ln -s link_src.txt out_link", "ln -s wrong.txt out_link"
                ),
                encoding="utf-8",
            )
            res_link = evaluate_shell_exercise(
                KIT_ROOT, "fs_side_effects", bad_link_dir, meta, subj_dir=subj_dir
            )
            self.assertFalse(res_link.ok)
            self.assertEqual(res_link.reason, "Wrong symlink")

            leftover_dir = root / "leftover"
            leftover_dir.mkdir()
            (leftover_dir / "setup.sh").write_text(
                oracle_code.replace("rm -f sub/tmp.bak\n", ""), encoding="utf-8"
            )
            res_left = evaluate_shell_exercise(
                KIT_ROOT, "fs_side_effects", leftover_dir, meta, subj_dir=subj_dir
            )
            self.assertFalse(res_left.ok)
            self.assertEqual(res_left.reason, "Diff KO :(")

    def test_offline_http_fixtures_server(self) -> None:
        from deepthought.shell_evaluator import evaluate_shell_exercise

        tests_cfg = {
            "fixed_tests": [
                {
                    "args": [],
                    "http_routes": {
                        "/api/status": {
                            "status": 200,
                            "content_type": "application/json",
                            "body": '{"status":"up"}',
                        },
                        "plain": "pong",
                    },
                    "stdout": '{"status":"up"}|pong|404\n',
                }
            ]
        }
        meta = {"id": "http_probe", "type": "shell", "expected_files": ["probe.sh"]}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subj_dir = root / "subj"
            subj_dir.mkdir()
            (subj_dir / "tests.yml").write_text(
                yaml.safe_dump(tests_cfg, sort_keys=False), encoding="utf-8"
            )

            sub_dir = root / "sub"
            sub_dir.mkdir()
            (sub_dir / "probe.sh").write_text(
                "#!/bin/sh\n"
                "python3 - <<'PY'\n"
                "import os, urllib.error, urllib.request\n"
                'base = os.environ["DT_HTTP_URL"]\n'
                'assert base.endswith(":" + os.environ["DT_HTTP_PORT"])\n'
                'a = urllib.request.urlopen(base + "/api/status?q=1").read().decode()\n'
                'b = urllib.request.urlopen(base + "/plain").read().decode()\n'
                "try:\n"
                '    urllib.request.urlopen(base + "/missing")\n'
                "    c = 200\n"
                "except urllib.error.HTTPError as exc:\n"
                "    c = exc.code\n"
                'print(f"{a}|{b}|{c}")\n'
                "PY\n",
                encoding="utf-8",
            )
            res = evaluate_shell_exercise(
                KIT_ROOT, "http_probe", sub_dir, meta, subj_dir=subj_dir
            )
            self.assertTrue(res.ok, res.trace_lines)

    def test_junk_dotfiles_rejected_in_c_and_shell_submissions(self) -> None:
        from deepthought.shell_evaluator import evaluate_shell_exercise, is_junk_dotfile

        self.assertTrue(is_junk_dotfile(".DS_Store"))
        self.assertTrue(is_junk_dotfile("._ft_putchar.c"))
        self.assertTrue(is_junk_dotfile(".#ft_putchar.c"))
        self.assertTrue(is_junk_dotfile(".ft_putchar.c.swp"))
        self.assertFalse(is_junk_dotfile(".gitignore"))
        self.assertFalse(is_junk_dotfile(".git"))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c_sub = root / "c_sub"
            shutil.copytree(KIT_ROOT / "corrections/piscine/c00/ft_putchar", c_sub)
            (c_sub / ".git").mkdir()
            (c_sub / ".git/HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (c_sub / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1")
            (c_sub / "._ft_putchar.c").write_bytes(b"appledouble")
            (c_sub / ".ft_putchar.c.swp").write_bytes(b"vimswap")

            res_bad = grade_subject(
                KIT_ROOT, "piscine/c00/ft_putchar", c_sub, strict=False
            )
            self.assertFalse(res_bad.passed)
            self.assertEqual(res_bad.status, "Extraneous file(s) in turn-in directory")
            self.assertIn(".DS_Store", res_bad.trace)
            self.assertIn("._ft_putchar.c", res_bad.trace)
            self.assertIn(".ft_putchar.c.swp", res_bad.trace)
            self.assertNotIn(".git/HEAD", res_bad.trace)

            for junk in (".DS_Store", "._ft_putchar.c", ".ft_putchar.c.swp"):
                (c_sub / junk).unlink()
            res_ok = grade_subject(
                KIT_ROOT, "piscine/c00/ft_putchar", c_sub, strict=False
            )
            self.assertTrue(res_ok.passed, res_ok.trace)

            sh_sub = root / "sh_sub"
            shutil.copytree(KIT_ROOT / "corrections/piscine/shell00/z", sh_sub)
            (sh_sub / ".DS_Store").write_bytes(b"junk")
            z_meta = yaml.safe_load(
                (KIT_ROOT / "subjects/piscine/shell00/z/meta.yml").read_text(
                    encoding="utf-8"
                )
            )
            res_sh = evaluate_shell_exercise(KIT_ROOT, "z", sh_sub, z_meta)
            self.assertFalse(res_sh.ok)
            self.assertEqual(res_sh.reason, "Extraneous file(s) in turn-in directory")


class TestBatchASubjectFixes(unittest.TestCase):
    def test_no_placeholder_error_boilerplate_remains(self):
        offenders = [
            str(p.relative_to(KIT_ROOT))
            for p in sorted((KIT_ROOT / "subjects").rglob("*.txt"))
            if "or the specified error message"
            in p.read_text(encoding="utf-8", errors="ignore")
        ]
        self.assertEqual(offenders, [])

    def test_batch_a_subject_and_example_text_fixes(self):
        naahio_txt = (KIT_ROOT / "subjects/exams/naahio/subject.en.txt").read_text(
            encoding="utf-8"
        )
        naahio_ex = (KIT_ROOT / "subjects/exams/naahio/examples.txt").read_text(
            encoding="utf-8"
        )
        naahio_tests = yaml.safe_load(
            (KIT_ROOT / "subjects/exams/naahio/tests.yml").read_text(encoding="utf-8")
        )
        for blob in (naahio_txt, naahio_ex):
            self.assertIn("Reversed: cool is AI Open Hello$", blob)
            self.assertIn("Vowel count: 9$", blob)
            self.assertNotIn("> Reversed:", blob)
            self.assertNotIn("Vowel count: 10$", blob)
        self.assertEqual(
            naahio_tests["subject_examples"][0]["expected"],
            "Reversed: cool is AI Open Hello\nVowel count: 9\n",
        )

        for prog, ch in (("only_a", "a"), ("only_z", "z")):
            for fname in ("subject.en.txt", "examples.txt"):
                txt = (KIT_ROOT / "subjects/exams" / prog / fname).read_text(
                    encoding="utf-8"
                )
                self.assertTrue(txt.rstrip("\n").endswith(f"\n{ch}"), f"{prog}/{fname}")
                self.assertNotIn(f"{ch}$", txt)
            tdata = yaml.safe_load(
                (KIT_ROOT / "subjects/exams" / prog / "tests.yml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(tdata["subject_examples"][0]["expected"], ch)
            self.assertEqual(tdata["folder_examples"][0]["expected"], ch)

        spy_txt = (KIT_ROOT / "subjects/exams/spy/subject.en.txt").read_text(
            encoding="utf-8"
        )
        spy_ex = (KIT_ROOT / "subjects/exams/spy/examples.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("nothing is displayed", spy_txt)
        self.assertNotIn('./spy "hello" "world" | cat -e\n$', spy_txt)
        self.assertNotIn('./spy "hello" "world" | cat -e\n$', spy_ex)

        cap_ex = (KIT_ROOT / "subjects/exams/capitalize/examples.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("  Abc\tDef  $", cap_ex)

        bf_ex = (KIT_ROOT / "subjects/exams/brainfuck/examples.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++.>++++++++++.",
            bf_ex,
        )

        for name in ("ft_rev_params", "ft_sort_params"):
            sub = (
                KIT_ROOT / "subjects/piscine/c06" / name / "subject.en.txt"
            ).read_text(encoding="utf-8")
            ex = (KIT_ROOT / "subjects/piscine/c06" / name / "examples.txt").read_text(
                encoding="utf-8"
            )
            ty = yaml.safe_load(
                (KIT_ROOT / "subjects/piscine/c06" / name / "tests.yml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotIn("Examples:", sub)
            self.assertIn("man ", ex)
            self.assertEqual(ty["subject_examples"][2]["expected"], "")
            self.assertEqual(ty["folder_examples"][2]["expected"], "")

        fix_txt = (KIT_ROOT / "subjects/exams/fix_parser/subject.en.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("else if (str[i] == ' ')", fix_txt)
        self.assertNotIn("str[i] == ''", fix_txt)

        tail_txt = (KIT_ROOT / "subjects/piscine/c10/tail/subject.en.txt").read_text(
            encoding="utf-8"
        )
        tail_ex = (KIT_ROOT / "subjects/piscine/c10/tail/examples.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("ft_tail", tail_txt)
        self.assertNotIn("Examples:", tail_txt)
        self.assertIn("man 1 tail", tail_ex)
        for blob in (tail_txt, tail_ex):
            self.assertNotIn("./tail ", blob)
            self.assertNotIn("Requirements:", blob)

        hex_txt = (KIT_ROOT / "subjects/piscine/c10/hexdump/subject.en.txt").read_text(
            encoding="utf-8"
        )
        hex_tests = yaml.safe_load(
            (KIT_ROOT / "subjects/piscine/c10/hexdump/tests.yml").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("Requirements:", hex_txt)
        self.assertEqual(
            hex_tests["subject_examples"][0]["command"],
            './ft_hexdump "-C" "a.txt" | cat -e',
        )
        self.assertIn(
            "00000000  48 65 6c 6c 6f", hex_tests["subject_examples"][0]["expected"]
        )

        sudoku_txt = (
            KIT_ROOT / "subjects/piscine/rush_bsq/sudoku/subject.en.txt"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Rush 01 Legacy", sudoku_txt)
        self.assertIn("duplicates in a row, column, or 3x3 subgrid", sudoku_txt)
        self.assertIn("Error$", sudoku_txt)

        tsp_meta = yaml.safe_load(
            (KIT_ROOT / "subjects/exams/tsp/meta.yml").read_text(encoding="utf-8")
        )
        for banned in ("printf", "scanf", "sqrt"):
            self.assertNotIn(banned, tsp_meta["allowed_functions"])
        self.assertEqual(
            set(tsp_meta["allowed_functions"]),
            {
                "write",
                "sqrtf",
                "getline",
                "fseek",
                "fscanf",
                "ferror",
                "feof",
                "fabsf",
                "memcpy",
                "fprintf",
                "fclose",
                "malloc",
                "calloc",
                "realloc",
                "free",
                "fopen",
                "errno",
                "stderr",
                "stdin",
                "stdout",
            },
        )

    def test_batch_a_examples_execute_against_reference_solutions(self):
        cases = [
            (
                "exams/naahio",
                ["Hello_Open_AI_is_cool"],
                "",
                "Reversed: cool is AI Open Hello\nVowel count: 9\n",
            ),
            ("exams/only_a", [], "", "a"),
            ("exams/only_z", [], "", "z"),
            ("exams/spy", ["hello", "world"], "", ""),
            ("exams/capitalize", ["  aBC\tdEF  "], "", "  Abc\tDef  \n"),
            (
                "exams/brainfuck",
                [
                    "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++.>++++++++++."
                ],
                "",
                "A\n",
            ),
            ("piscine/c06/ft_rev_params", [], "", ""),
            ("piscine/c06/ft_sort_params", [], "", ""),
            ("exams/tsp", [], "0, 0\n1, 0\n1, 1\n0, 1\n", "4.00\n"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            for rel, args, stdin, expected in cases:
                cfiles = sorted((KIT_ROOT / "corrections" / rel).rglob("*.c"))
                exe = td / Path(rel).name
                comp = subprocess.run(
                    [
                        "cc",
                        "-Wall",
                        "-Wextra",
                        "-Werror",
                        *(str(f) for f in cfiles),
                        "-lm",
                        "-o",
                        str(exe),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertEqual(comp.returncode, 0)
                run = subprocess.run(
                    [str(exe), *args],
                    input=stdin,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertEqual(run.stdout, expected, rel)

            tsp_sub = td / "tsp_sub"
            shutil.copytree(KIT_ROOT / "corrections/exams/tsp", tsp_sub)
            res = grade_subject(
                KIT_ROOT, "exams/tsp", tsp_sub, is_exam=True, strict=True
            )
            self.assertTrue(res.passed, res.trace)


class TestBatchBSubjectAndProvisioning(unittest.TestCase):
    """Verify Batch B starter-file honesty, examples parity, and companion provisioning."""

    def test_starter_files_and_subject_wording(self) -> None:
        expected_starters = [
            "subjects/exams/tsp/tsp.c",
            "subjects/exams/tsp/square.txt",
            "subjects/exams/vbc/vbc.c",
            "subjects/exams/vbc (without tree)/vbc.c",
            "subjects/exams/mini_serv/main.c",
            "subjects/exams/mini_db/socket.hpp",
            "subjects/exams/picoshell/main.c",
            "subjects/exams/ft_scanf/ft_scanf.c",
            "subjects/exams/bigint/main.cpp",
            "subjects/exams/vect2/main.cpp",
            "subjects/exams/filter/filter.sh",
        ]
        for rel in expected_starters:
            p = KIT_ROOT / rel
            self.assertTrue(
                p.is_file() and p.stat().st_size > 0, f"Missing starter file: {rel}"
            )

        nq_subj = (KIT_ROOT / "subjects/exams/n_queens/subject.en.txt").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("attached to this subject", nq_subj)

        ms_subj = (KIT_ROOT / "subjects/exams/mini_serv/subject.en.txt").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("executable in the subject folder", ms_subj)
        self.assertIn("main.c", ms_subj)
        self.assertIn("127.0.0.1", ms_subj)

        mdb_subj = (KIT_ROOT / "subjects/exams/mini_db/subject.en.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("socket.hpp", mdb_subj)

        filt_subj = (KIT_ROOT / "subjects/exams/filter/subject.en.txt").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("sed's", filt_subj)
        self.assertIn("sed 's", filt_subj)
        self.assertNotIn("\n$>\n", filt_subj)

    def test_examples_parity_and_french_duplicate_cleanup(self) -> None:
        ms_ex = (KIT_ROOT / "subjects/exams/mini_serv/examples.txt").read_text(
            encoding="utf-8"
        )
        self.assertFalse(ms_ex.strip().startswith("See subject.en.txt"))
        self.assertIn("$>", ms_ex)

        filt_ex = (KIT_ROOT / "subjects/exams/filter/examples.txt").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("echo -n", filt_ex)
        self.assertNotIn("ababcababqc", filt_ex)

        for slug in ("exams/epur_str", "exams/expand_str"):
            sdir = KIT_ROOT / "subjects" / slug
            subj_txt = (sdir / "subject.en.txt").read_text(encoding="utf-8")
            ex_txt = (sdir / "examples.txt").read_text(encoding="utf-8")
            tests_yml_raw = (sdir / "tests.yml").read_text(encoding="utf-8")
            for label, content in (
                ("subject.en.txt", subj_txt),
                ("examples.txt", ex_txt),
                ("tests.yml", tests_yml_raw),
            ):
                for french_marker in (
                    "Exemples",
                    "quel est le",
                    "Comment ça",
                    "l'ordre",
                ):
                    self.assertNotIn(
                        french_marker,
                        content,
                        f"{slug}/{label} still contains {french_marker!r}",
                    )
                self.assertIsNone(
                    re.search(r"(?m)^\$>\s*$", content),
                    f"{slug}/{label} has bare '$>' line",
                )

            parsed = yaml.safe_load(tests_yml_raw)
            for section in ("fixed_tests", "subject_examples", "folder_examples"):
                self.assertTrue(
                    parsed.get(section), f"{slug}/tests.yml missing {section}"
                )

    def test_starters_compile_whitelists_and_filter_sh(self) -> None:
        from deepthought.compiler_and_symbols import verify_symbol_whitelist

        shnorm_proc = subprocess.run(
            [
                sys.executable,
                str(KIT_ROOT / "bin/shnorm"),
                str(KIT_ROOT / "subjects/exams/filter/filter.sh"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            shnorm_proc.returncode, 0, shnorm_proc.stdout + shnorm_proc.stderr
        )

        filter_sh = KIT_ROOT / "subjects/exams/filter/filter.sh"
        ftests = yaml.safe_load(
            (KIT_ROOT / "subjects/exams/filter/tests.yml").read_text(encoding="utf-8")
        )
        cases = ftests.get("tests", []) or ftests.get("fixed_tests", [])
        self.assertTrue(cases)
        for case in cases:
            args = [str(a) for a in case.get("args", [])]
            run = subprocess.run(
                [str(filter_sh), *args],
                input=case.get("stdin", ""),
                text=True,
                capture_output=True,
            )
            self.assertEqual(
                run.returncode,
                case.get("expected_returncode", case.get("returncode", 0)),
            )
            self.assertEqual(
                run.stdout, case.get("expected_stdout", case.get("stdout", ""))
            )
        for bad_args in ([], [""]):
            bad = subprocess.run(
                [str(filter_sh), *bad_args], input="abc", text=True, capture_output=True
            )
            self.assertNotEqual(bad.returncode, 0)

        with tempfile.TemporaryDirectory() as td_raw:
            td = Path(td_raw)

            # C starters + symbol whitelists (tsp, vbc, vbc without tree)
            for slug, src_name in (
                ("exams/tsp", "tsp.c"),
                ("exams/vbc", "vbc.c"),
                ("exams/vbc (without tree)", "vbc.c"),
            ):
                sdir = KIT_ROOT / "subjects" / slug
                meta = yaml.safe_load((sdir / "meta.yml").read_text(encoding="utf-8"))
                wdir = td / slug.replace("/", "_").replace(" ", "_")
                wdir.mkdir(parents=True)
                src_copy = wdir / src_name
                shutil.copy2(sdir / src_name, src_copy)
                comp, sym = verify_symbol_whitelist(
                    [src_copy],
                    list(meta.get("allowed_functions", [])),
                    work_dir=wdir,
                )
                self.assertTrue(comp.ok, f"{slug} compile failed: {comp.stderr}")
                self.assertTrue(
                    sym.ok,
                    f"{slug} symbol violation: {sym.forbidden_called} ({sym.reason})",
                )

            tsp_bin = td / "tsp_starter"
            subprocess.run(
                [
                    "cc",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    str(KIT_ROOT / "subjects/exams/tsp/tsp.c"),
                    "-lm",
                    "-o",
                    str(tsp_bin),
                ],
                check=True,
            )
            with (KIT_ROOT / "subjects/exams/tsp/square.txt").open(
                "r", encoding="utf-8"
            ) as f_sq:
                tsp_run = subprocess.run(
                    [str(tsp_bin)],
                    stdin=f_sq,
                    text=True,
                    capture_output=True,
                    check=True,
                )
            self.assertEqual(tsp_run.stdout, "0.00\n")

            subprocess.run(
                [
                    "cc",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    str(KIT_ROOT / "subjects/exams/mini_serv/main.c"),
                    "-o",
                    str(td / "mini_serv_starter"),
                ],
                check=True,
            )

            pico_bin = td / "picoshell_test"
            subprocess.run(
                [
                    "cc",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    str(KIT_ROOT / "subjects/exams/picoshell/main.c"),
                    str(KIT_ROOT / "corrections/exams/picoshell/picoshell.c"),
                    "-o",
                    str(pico_bin),
                ],
                check=True,
            )
            self.assertEqual(
                subprocess.run(
                    [str(pico_bin)], text=True, capture_output=True, check=True
                ).stdout,
                "squblblb\n",
            )
            self.assertEqual(
                subprocess.run(
                    [str(pico_bin), "echo", "hello", "|", "tr", "a-z", "A-Z"],
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout,
                "HELLO\n",
            )

            inc_cpp = td / "mini_db_inc.cpp"
            inc_cpp.write_text(
                '#include "socket.hpp"\nint main() { return 0; }\n', encoding="utf-8"
            )
            subprocess.run(
                [
                    "g++",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-std=c++98",
                    "-I",
                    str(KIT_ROOT / "subjects/exams/mini_db"),
                    str(inc_cpp),
                    "-o",
                    str(td / "mini_db_inc"),
                ],
                check=True,
            )

            big_bin = td / "bigint_test"
            subprocess.run(
                [
                    "g++",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-std=c++98",
                    "-I",
                    str(KIT_ROOT / "corrections/exams/bigint"),
                    str(KIT_ROOT / "subjects/exams/bigint/main.cpp"),
                    str(KIT_ROOT / "corrections/exams/bigint/bigint.cpp"),
                    "-o",
                    str(big_bin),
                ],
                check=True,
            )
            self.assertIn(
                "a + b = 63\n",
                subprocess.run(
                    [str(big_bin)], text=True, capture_output=True, check=True
                ).stdout,
            )

            vec_bin = td / "vect2_test"
            subprocess.run(
                [
                    "g++",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-std=c++98",
                    "-I",
                    str(KIT_ROOT / "corrections/exams/vect2"),
                    str(KIT_ROOT / "subjects/exams/vect2/main.cpp"),
                    str(KIT_ROOT / "corrections/exams/vect2/vect2.cpp"),
                    "-o",
                    str(vec_bin),
                ],
                check=True,
            )
            self.assertIn(
                "v1: {0, 0}\n",
                subprocess.run(
                    [str(vec_bin)], text=True, capture_output=True, check=True
                ).stdout,
            )

    def test_companion_file_provisioning_and_display(self) -> None:
        import contextlib
        import io

        examshell_mod = _load_script(KIT_ROOT / "bin/examshell", "examshell_batch_b")
        with tempfile.TemporaryDirectory() as td_raw:
            tmp = Path(td_raw)
            home_dir = tmp / "home"
            home_dir.mkdir()
            orig_home = os.environ.get("HOME")
            orig_skip = os.environ.get("DT_SKIP_HOME_SYMLINKS")
            os.environ["HOME"] = str(home_dir)
            os.environ["DT_SKIP_HOME_SYMLINKS"] = "1"
            try:
                for pool_id, slug, expected_files in (
                    ("rank03", "tsp", {"tsp.c", "square.txt"}),
                    ("rank03", "filter", {"filter.sh"}),
                    ("rank06", "mini_db", {"socket.hpp"}),
                ):
                    sub_base = tmp / f"exam_{slug}"
                    shell = examshell_mod.ExamShell(
                        pool_id,
                        basedir=sub_base,
                        fresh_confirmed=True,
                        no_color=True,
                    )
                    subj_file = shell._provision_subject_files(slug)
                    dest = subj_file.parent
                    self.assertEqual(dest, shell.subjects_dir / slug)
                    for fname in expected_files:
                        self.assertTrue(
                            (dest / fname).is_file(),
                            f"Missing provisioned {fname} for {slug}",
                        )
                    for internal in (
                        "meta.yml",
                        "tests.yml",
                        "scale.yml",
                        "examples.txt",
                    ):
                        self.assertFalse(
                            (dest / internal).exists(),
                            f"Internal file {internal} should not be copied for {slug}",
                        )

                    if slug == "tsp":
                        shell.current_assignment = "tsp"
                        buf = io.StringIO()
                        with contextlib.redirect_stdout(buf):
                            shell.do_subject("")
                        out = buf.getvalue()
                        self.assertIn("Given / subject files in ", out)
                        self.assertIn("square.txt", out)
                        self.assertIn("tsp.c", out)
            finally:
                if orig_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = orig_home
                if orig_skip is None:
                    os.environ.pop("DT_SKIP_HOME_SYMLINKS", None)
                else:
                    os.environ["DT_SKIP_HOME_SYMLINKS"] = orig_skip

        moul = subprocess.run(
            [
                sys.executable,
                str(KIT_ROOT / "bin/moulinette"),
                "subject",
                "exams/tsp",
                "--no-color",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("given   :", moul.stdout)
        self.assertIn("square.txt, tsp.c", moul.stdout)


class TestPiscinePdfFidelity(unittest.TestCase):
    """Ensure Piscine subjects strictly reflect official PDFs and point missing examples to `man`."""

    PDF_WITH_EXAMPLES = {
        "shell00/z",
        "shell00/testShell00",
        "shell00/exo2",
        "shell00/git_commit.sh",
        "shell00/git_ignore.sh",
        "shell00/diff",
        "shell01/print_groups.sh",
        "shell01/find_sh.sh",
        "shell01/count_files.sh",
        "shell01/special_filename_MaRViN",
        "shell01/skip.sh",
        "shell01/r_dwssap.sh",
        "shell01/add_chelou.sh",
        "c00/ft_print_comb",
        "c00/ft_print_comb2",
        "c00/ft_putnbr",
        "c00/ft_print_combn",
        "c02/ft_strcapitalize",
        "c02/ft_putstr_non_printable",
        "c02/ft_print_memory",
        "c04/ft_putnbr",
        "c04/ft_atoi",
        "c05/ft_ten_queens_puzzle",
        "c06/ft_print_program_name",
        "c06/ft_print_params",
        "c08/ft_boolean.h",
        "c08/ft_point.h",
        "c11/ft_foreach",
        "c11/do-op",
        "rush_bsq/bsq",
        "rush_bsq/rush00",
        "rush_bsq/rush01",
        "rush_bsq/rush02",
        "rush_bsq/colle02",
        "rush_bsq/sudoku",
    }

    SINGLE_DECL_PROTOTYPES = {
        "c02/ft_str_is_alpha",
        "c03/ft_strcat",
        "c03/ft_strstr",
        "c07/ft_split_whitespaces",
        "c07/ft_strjoin",
        "rush_bsq/match_n_match",
        "rush_bsq/sastantua",
    }

    def test_all_piscine_subjects_strict_pdf_and_man_examples(self) -> None:
        piscine_root = KIT_ROOT / "subjects/piscine"
        ex_dirs = sorted(p for p in piscine_root.glob("*/*") if p.is_dir())
        self.assertEqual(len(ex_dirs), 136)

        for ex_dir in ex_dirs:
            rel = str(ex_dir.relative_to(piscine_root))
            subj = (ex_dir / "subject.en.txt").read_text(encoding="utf-8")
            ex = (ex_dir / "examples.txt").read_text(encoding="utf-8")
            meta = yaml.safe_load((ex_dir / "meta.yml").read_text(encoding="utf-8"))

            hdr, body = subj.split("-" * 80 + "\n", 1)
            self.assertNotIn(
                "Module           :", body, f"{rel}: duplicate Module header"
            )
            self.assertNotIn(
                "Turn-in directory:",
                body,
                f"{rel}: duplicate Turn-in directory in body",
            )
            self.assertNotIn(
                "Files to turn in", body, f"{rel}: duplicate Files to turn in in body"
            )
            self.assertNotIn(
                "Toolchain Gate", subj, f"{rel}: synthetic Toolchain Gate header"
            )
            self.assertIsNone(
                re.search(r"(?im)^Prototype:\s*$", body),
                f"{rel}: duplicate Prototype header",
            )
            if rel not in self.SINGLE_DECL_PROTOTYPES:
                self.assertNotIn(
                    "Your function must be declared as follows:",
                    body,
                    f"{rel}: duplicate declaration header",
                )
            for joke in (
                "Did you check with your neighbor on the right?",
                "Get inspired by others",
                "Google is your friend.",
            ):
                self.assertNotIn(joke, subj, f"{rel}: leaked PDF callout joke")

            if meta.get("type") == "c_function":
                fn = (
                    meta["id"].split("_", 1)[1]
                    if meta["id"].startswith(("c01_", "c09_"))
                    else meta["id"]
                )
                if rel != "rush_bsq/match_n_match":
                    self.assertIn(
                        fn, body, f"{rel}: missing prototype signature for {fn}"
                    )

            if rel not in self.PDF_WITH_EXAMPLES:
                self.assertIsNone(
                    re.search(r"(?im)^Examples?:\s*$", body),
                    f"{rel}: subject.en.txt should not contain synthesized Examples",
                )
                self.assertIn(
                    "No examples in official PDF",
                    ex,
                    f"{rel}: examples.txt missing PDF note",
                )
                self.assertIn(
                    "man ", ex, f"{rel}: examples.txt should direct students to man"
                )
                self.assertNotIn(
                    "tests.yml", ex, f"{rel}: examples.txt must not reference tests.yml"
                )

        # Spot-check key official PDF contents preserved cleanly
        z_txt = (piscine_root / "shell00/z/subject.en.txt").read_text(encoding="utf-8")
        self.assertIn("?> cat z\nZ", z_txt)
        self.assertNotIn("Requirements:", z_txt)

        ft_putnbr_txt = (piscine_root / "c00/ft_putnbr/subject.en.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("ft_putnbr(42)", ft_putnbr_txt)
        self.assertNotIn("-2147483648\n", ft_putnbr_txt)

        ft_nums_txt = (piscine_root / "c00/ft_print_numbers/subject.en.txt").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("01234567899", ft_nums_txt)

    def test_subject_examples_builder_respects_append_to_subject_false(self) -> None:
        from deepthought.subject_examples import (
            build_clean_examples_block_and_append_to_subject,
        )

        base_subj = (
            "Assignment name  : ft_putchar\n"
            "Turn-in directory: ex00/\n"
            "Expected files   : ft_putchar.c\n"
            "Allowed functions: write\n" + "-" * 80 + "\n\n"
            "• Write a function that displays the character passed as a parameter.\n"
        )
        enriched, _ = build_clean_examples_block_and_append_to_subject(
            "ft_putchar",
            base_subj,
            "",
            [{"name": "t1", "call": "ft_putchar('a')", "stdout": "a"}],
            append_to_subject=False,
        )
        self.assertNotIn("Examples:", enriched)
        self.assertEqual(enriched, base_subj)


class TestBatchCMetadataHygiene(unittest.TestCase):
    def test_no_near_arg_placeholders_across_all_subjects_and_builder(self) -> None:
        from deepthought.subject_examples import build_near_examples

        subjects_root = KIT_ROOT / "subjects"
        meta_files = sorted(subjects_root.rglob("meta.yml"))
        self.assertEqual(len(meta_files), 439)

        offenders: list[str] = []
        bad_folder_perts: list[str] = []
        for meta_p in meta_files:
            tp = meta_p.parent / "tests.yml"
            if not tp.exists():
                continue
            rel = meta_p.parent.relative_to(subjects_root).as_posix()
            raw = tp.read_text(encoding="utf-8")
            if "near_arg" in raw:
                offenders.append(rel)
            data = yaml.safe_load(raw) or {}
            for ne in data.get("near_examples") or []:
                nid = str(ne.get("id", ""))
                orig = str(ne.get("original_input", ""))
                pert = str(ne.get("perturbed_input", ""))
                if nid.startswith("near_folder_") and (
                    orig in ("tests.yml", "examples.txt")
                    or "Dynamic generation" in orig
                    or pert == "uests.yml"
                    or pert.startswith(("bctive_", "./bff_", "./bdd_", "GT_"))
                ):
                    bad_folder_perts.append(f"{rel}:{nid}:{orig!r}->{pert!r}")

        self.assertEqual(offenders, [], f"Remaining near_arg placeholders: {offenders}")
        self.assertEqual(
            bad_folder_perts,
            [],
            f"Corrupted near_folder perturbations: {bad_folder_perts}",
        )

        # Verify builder itself no longer generates fake near_arg or corrupted metadata perturbations
        empty_near = build_near_examples(
            "ft_putchar",
            "c_function",
            [{"id": "subj_ex_01", "command": "eval ft_putchar", "args": []}],
            [
                {
                    "id": "folder_ex_01",
                    "origin": "subject_folder/examples.txt",
                    "input": "tests.yml",
                }
            ],
        )
        self.assertEqual(empty_near, [])

        fn_near = build_near_examples(
            "active_bits",
            "c_function",
            [],
            [
                {
                    "id": "e1",
                    "origin": "subject_folder/examples.txt",
                    "input": "active_bits(42) -> 3",
                }
            ],
        )
        self.assertEqual(len(fn_near), 1)
        self.assertEqual(fn_near[0]["perturbed_input"], "active_bits(43)")

    def test_no_mismatched_templated_edge_cases(self) -> None:
        subjects_root = KIT_ROOT / "subjects"
        actual_edge_case_rels: set[str] = set()
        for tp in sorted(subjects_root.rglob("tests.yml")):
            data = yaml.safe_load(tp.read_text(encoding="utf-8")) or {}
            if "edge_cases" in data:
                actual_edge_case_rels.add(
                    tp.parent.relative_to(subjects_root).as_posix()
                )

        expected_accurate = {
            "exams/ft_div",
            "exams/ft_mod",
            "exams/ft_pow",
            "exams/microshell",
        }
        self.assertEqual(actual_edge_case_rels, expected_accurate)

        for bogus in (
            "exams/vbc",
            "exams/equation",
            "exams/broken_gnl",
            "exams/ft_printf",
            "exams/write_string",
            "exams/zigzag",
            "exams/active_bits",
            "exams/fix_parser",
            "exams/count_alen",
        ):
            data = yaml.safe_load(
                (subjects_root / bogus / "tests.yml").read_text(encoding="utf-8")
            )
            self.assertNotIn("edge_cases", data)

    def test_scale_yml_tailored_by_subject_type_and_track(self) -> None:
        subjects_root = KIT_ROOT / "subjects"
        meta_files = sorted(subjects_root.rglob("meta.yml"))
        self.assertEqual(len(meta_files), 439)

        for meta_p in meta_files:
            ex_dir = meta_p.parent
            rel = ex_dir.relative_to(subjects_root).as_posix()
            meta = yaml.safe_load(meta_p.read_text(encoding="utf-8")) or {}
            scale_raw = (ex_dir / "scale.yml").read_text(encoding="utf-8")
            scale = yaml.safe_load(scale_raw) or {}

            ex_type = str(meta.get("type", ""))
            is_normed = bool(meta.get("norminette"))
            gates = list(scale.get("zero_tolerance_gates") or [])

            self.assertEqual(scale.get("project"), meta.get("id"), rel)
            self.assertEqual(sum(int(s["points"]) for s in scale["sections"]), 100, rel)

            if not is_normed:
                self.assertNotIn("norme_error", gates, rel)
            if ex_type in ("shell", "shell_file"):
                self.assertNotIn("segfault", gates, rel)
                self.assertNotIn("memory_leak", gates, rel)
                self.assertNotIn("-Wall -Wextra -Werror", scale_raw, rel)
            if ex_type == "shell_file":
                self.assertIn("missing_deliverable", gates, rel)
                self.assertNotIn("norme_error", gates, rel)
            elif ex_type == "makefile":
                self.assertIn("relink_on_second_make", gates, rel)
            elif ex_type == "cpp":
                self.assertIn("c++ -Wall -Wextra -Werror", scale_raw, rel)
                self.assertIn("compile_error", gates, rel)
            elif ex_type == "c_header" and meta.get("norminette_rule") == "CheckDefine":
                self.assertIn("-R CheckDefine", scale_raw, rel)
            elif ex_type in ("c_function", "c_program") and is_normed:
                self.assertIn("norme_error", gates, rel)
                self.assertIn("cc -Wall -Wextra -Werror", scale_raw, rel)


if __name__ == "__main__":
    unittest.main()
