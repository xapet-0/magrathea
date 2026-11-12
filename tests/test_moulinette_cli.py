"""Regression tests for bin/moulinette (exercise resolution, XP integrity, CLI contract).

Each test pins one defect that was reproduced on the previous version:
- names are literal and whole: no partial match, no wildcard, no '..'
- a bare name shared by two modules with an equal claim is refused, not guessed
- module grading works when colours are off (pipe, NO_COLOR, --no-color)
- --json never ends in a traceback and refuses flags it cannot honour
- an alternative --xp-ledger never credits the student profile
- an option value named 'solution' / 'hint' is not mistaken for the locked command
- every 'Does not compile (...)' status is reported on the compilation gate
- the current directory is never graded wholesale
- the turn-in is laid out as at 42, <module>/<exNN>/<file>, in folders the student makes by hand:
  grading creates no folder, and a file left in another exNN is not turned in

Run with: python3 tests/test_moulinette_cli.py
"""
from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

KIT_ROOT = Path(__file__).resolve().parents[1]
MOULINETTE = KIT_ROOT / "bin" / "moulinette"
if str(KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(KIT_ROOT))


def _load_moulinette_module():
    loader = importlib.machinery.SourceFileLoader("moulinette_under_test", str(MOULINETTE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


moul = _load_moulinette_module()


class MoulinetteCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="moulinette_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()

    def run_cli(self, *argv: str, cwd: Path | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ, HOME=str(self.home), NO_COLOR="1", DT_SKIP_HOME_SYMLINKS="1")
        env.pop("FORCE_COLOR", None)
        env.pop("FT_STUDENT_PROFILE", None)
        return subprocess.run(
            [sys.executable, str(MOULINETTE), *argv],
            cwd=str(cwd or KIT_ROOT), env=env, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
        )

    def reference_copy(self, subject: str, dirname: str = "turnin") -> Path:
        dest = self.tmp / dirname
        shutil.copytree(KIT_ROOT / "corrections" / subject, dest)
        return dest

    # ------------------------------------------------------------------ resolution
    def test_names_are_matched_whole(self) -> None:
        resolve = moul.resolve_piscine_or_exam_subject
        for partial in ("strlen", "base", "size"):
            resolved, _ = resolve(partial)
            self.assertFalse(moul._is_exercise_dir(KIT_ROOT / "subjects" / resolved), partial)
        self.assertEqual(resolve("atoi_base"), ("exams/atoi_base", True))
        self.assertEqual(resolve("c01/ft_strlen"), ("piscine/c01/c01_ft_strlen", False))
        self.assertEqual(resolve("piscine//c04/ft_strlen/"), ("piscine/c04/ft_strlen", False))
        self.assertEqual(resolve("ft_split"), ("piscine/c07/ft_split", False))
        self.assertEqual(resolve("ft_atoi", prefer_exam=True), ("exams/ft_atoi", True))

    def test_wildcards_and_dotdot_are_refused(self) -> None:
        for bad in ("*", "ft_*", "?", "[a-z]*", "..", "piscine/../../corrections/piscine/c04/ft_strlen", " ", ""):
            with self.assertRaises(moul.ExerciseLookupError, msg=repr(bad)):
                moul.resolve_piscine_or_exam_subject(bad)

    def test_equal_claims_on_a_bare_name_are_refused(self) -> None:
        with self.assertRaises(moul.ExerciseLookupError) as ctx:
            moul.resolve_piscine_or_exam_subject("ft_putnbr")
        self.assertIn("c00/ft_putnbr", str(ctx.exception))
        self.assertIn("c04/ft_putnbr", str(ctx.exception))
        self.assertEqual(moul.resolve_piscine_or_exam_subject("c04/ft_putnbr"), ("piscine/c04/ft_putnbr", False))

    def test_every_exercise_is_reachable_by_its_explicit_name(self) -> None:
        for meta in (KIT_ROOT / "subjects" / "piscine").glob("*/*/meta.yml"):
            ex_dir = meta.parent
            mod = ex_dir.parent.name
            leaf = moul._MODULE_PREFIX_RE.sub("", ex_dir.name)
            self.assertEqual(moul.resolve_piscine_or_exam_subject(f"{mod}/{leaf}")[0], f"piscine/{mod}/{ex_dir.name}")
        for meta in (KIT_ROOT / "subjects" / "exams").glob("*/meta.yml"):
            name = meta.parent.name
            self.assertEqual(moul.resolve_piscine_or_exam_subject(f"exams/{name}"), (f"exams/{name}", True))

    def test_current_directory_is_not_graded_wholesale(self) -> None:
        empty = self.tmp / "unrelated"
        empty.mkdir()
        (empty / "notes.txt").write_text("x", encoding="utf-8")
        previous = Path.cwd()
        os.chdir(empty)
        try:
            chosen = moul.resolve_submission_dir(None, "ft_putchar", resolved_subject="piscine/c00/ft_putchar")
            self.assertNotEqual(chosen, empty.resolve())
            (empty / "ft_putchar.c").write_text("", encoding="utf-8")
            self.assertEqual(
                moul.resolve_submission_dir(None, "ft_putchar", resolved_subject="piscine/c00/ft_putchar"), empty.resolve()
            )
        finally:
            os.chdir(previous)

    # ------------------------------------------------------------------ scorecard
    def test_compile_variants_are_reported_on_the_compilation_gate(self) -> None:
        theme = moul.ThemeEngine("plain")
        report = SimpleNamespace(status="Does not compile (missing include guard)", passed=False)
        lines = moul.render_five_gate_scorecard(report, theme).splitlines()
        gate3 = next(line for line in lines if "gate 3" in line)
        gate5 = next(line for line in lines if "gate 5" in line)
        self.assertIn("KO", gate3)
        self.assertIn("SKIP", gate5)

    # ------------------------------------------------------------------ CLI contract
    def test_json_unknown_exercise_is_an_error_object_not_a_traceback(self) -> None:
        proc = self.run_cli("no_such_exercise_xyz", "--json")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stdout + proc.stderr)
        self.assertIn("error", json.loads(proc.stdout))

    def test_json_refuses_flags_it_cannot_honour(self) -> None:
        for extra in (("--watch",), ("--module", "c00")):
            proc = self.run_cli("c04/ft_strlen", "--json", *extra)
            self.assertEqual(proc.returncode, 2, extra)
            self.assertIn("--json", proc.stderr)

    def test_unwritable_trace_out_is_refused_before_grading(self) -> None:
        proc = self.run_cli("c04/ft_strlen", "--trace-out", str(self.tmp / "missing_dir" / "x.trace"))
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stdout + proc.stderr)

    def test_option_value_named_solution_is_not_the_locked_command(self) -> None:
        turnin = self.reference_copy("piscine/c04/ft_strlen", dirname="solution")
        proc = self.run_cli("c04/ft_strlen", "--json", "--dir", str(turnin))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["passed"])
        locked = self.run_cli("solution", "ft_strlen")
        self.assertEqual(locked.returncode, 2)
        self.assertIn("locked", locked.stdout)

    def test_module_grading_works_without_colours(self) -> None:
        proc = self.run_cli("c00", "--self-test")
        self.assertNotIn("invalid choice", proc.stdout + proc.stderr)
        self.assertEqual(proc.returncode, 0, (proc.stdout + proc.stderr)[-600:])

    def test_alternative_ledger_never_credits_the_profile(self) -> None:
        turnin = self.reference_copy("piscine/c04/ft_strlen")
        for index in range(2):
            ledger = self.tmp / f"ledger_{index}.json"
            proc = self.run_cli("c04/ft_strlen", "--dir", str(turnin), "--xp-ledger", str(ledger))
            self.assertEqual(proc.returncode, 0, (proc.stdout + proc.stderr)[-600:])
            self.assertIn("piscine/c04/ft_strlen", json.loads(ledger.read_text(encoding="utf-8"))["validated_exercises"])
        profile = self.home / ".42_student_profile.json"
        total = json.loads(profile.read_text(encoding="utf-8")).get("total_xp", 0) if profile.exists() else 0
        self.assertEqual(total, 0)

    def test_one_exercise_has_one_ledger_key_whatever_the_spelling(self) -> None:
        turnin = self.reference_copy("piscine/c04/ft_strlen")
        ledger = self.tmp / "ledger.json"
        for spelling in ("c04/ft_strlen", "piscine//c04/ft_strlen", "piscine/c04/ft_strlen/"):
            proc = self.run_cli(spelling, "--dir", str(turnin), "--xp-ledger", str(ledger))
            self.assertEqual(proc.returncode, 0, spelling)
        self.assertEqual(list(json.loads(ledger.read_text(encoding="utf-8"))["validated_exercises"]), ["piscine/c04/ft_strlen"])

    # ------------------------------------------------------------------ the 42 layout: <module>/<exNN>/<file>
    def hand_made(self, module: str, ex_code: str, exercise: str) -> Path:
        """What a student types: mkdir -p <module>/<exNN>, then the file inside."""
        ex_dir = self.tmp / "repo" / module / ex_code
        ex_dir.mkdir(parents=True, exist_ok=True)
        for src in (KIT_ROOT / "corrections" / "piscine" / module / exercise).iterdir():
            if src.is_file():
                shutil.copy(src, ex_dir / src.name)
        return ex_dir

    def test_every_piscine_exercise_has_one_ex_folder(self) -> None:
        slots = {}
        for subject_dir in sorted((KIT_ROOT / "subjects" / "piscine").glob("*/*")):
            if not moul._is_exercise_dir(subject_dir):
                continue
            resolved = f"piscine/{subject_dir.parent.name}/{subject_dir.name}"
            slot = moul.piscine_exercise_slot(resolved)
            self.assertIsNotNone(slot, resolved)
            self.assertRegex(slot[1], r"^ex\d{2}$", resolved)
            self.assertNotIn(slot, slots, f"{resolved} shares {slot} with {slots.get(slot)}")
            slots[slot] = resolved
        self.assertEqual(moul.piscine_exercise_slot("piscine/c00/ft_putchar"), ("c00", "ex00"))
        self.assertIsNone(moul.piscine_exercise_slot("exams/ft_range"))

    def test_hand_made_ex_folder_is_graded_from_the_repo_the_module_and_the_exercise(self) -> None:
        ex_dir = self.hand_made("c00", "ex01", "ft_print_alphabet")
        ledger = self.tmp / "ledger.json"
        for cwd in (ex_dir.parent.parent, ex_dir.parent, ex_dir):
            proc = self.run_cli("ft_print_alphabet", "--xp-ledger", str(ledger), cwd=cwd)
            self.assertEqual(proc.returncode, 0, f"{cwd}\n{proc.stdout}{proc.stderr}")
            self.assertIn("OK :)", proc.stdout)

    def test_file_in_another_ex_folder_is_not_turned_in(self) -> None:
        wrong = self.hand_made("c00", "ex05", "ft_print_numbers")     # ft_print_numbers belongs in ex03
        for cwd in (wrong.parent, wrong):
            proc = self.run_cli("c00/ft_print_numbers", "--xp-ledger", str(self.tmp / "ledger.json"), cwd=cwd)
            self.assertEqual(proc.returncode, 1, f"{cwd}\n{proc.stdout}{proc.stderr}")
            self.assertIn("Nothing turned in", proc.stdout)
            self.assertIn("c00/ex03/", proc.stdout)

    def test_grading_creates_no_folder_and_names_the_one_to_create(self) -> None:
        module_dir = self.tmp / "repo" / "c00"
        module_dir.mkdir(parents=True)
        single = self.run_cli("ft_putchar", "--xp-ledger", str(self.tmp / "ledger.json"), cwd=module_dir)
        self.assertEqual(single.returncode, 1, single.stdout + single.stderr)
        self.assertIn(f"{module_dir}/ex00/", single.stdout.replace("~", str(self.home)))
        self.assertNotIn("init", single.stdout.split("Summary:")[-1])
        whole = self.run_cli("c00", cwd=module_dir)
        self.assertEqual(whole.returncode, 1, whole.stdout + whole.stderr)
        watched_module = self.tmp / "repo" / "c02"
        self.assertEqual(self.run_cli("c02", cwd=self.tmp / "repo").returncode, 1)
        self.assertEqual(list(module_dir.iterdir()), [])
        self.assertFalse(watched_module.exists())

    def test_module_grading_reads_the_module_folder_the_student_stands_in(self) -> None:
        ex_dir = self.hand_made("c00", "ex01", "ft_print_alphabet")   # no ex00: the folder is still the module
        for cwd in (ex_dir.parent, ex_dir.parent.parent):
            proc = self.run_cli("c00", cwd=cwd)
            rows = {line.split()[0]: line for line in proc.stdout.splitlines() if line.strip().startswith("ex0")}
            self.assertIn("Nothing turned in", rows["ex00"], proc.stdout)
            self.assertIn("OK (100)", rows["ex01"], proc.stdout)

    def test_kit_subjects_and_corrections_are_never_the_turnin(self) -> None:
        workspace_c00 = (KIT_ROOT / "workspace" / "piscine" / "c00").resolve()
        before = os.getcwd()
        try:
            for tree in ("subjects/piscine", "subjects/piscine/c00", "corrections/piscine", "corrections/piscine/c00"):
                os.chdir(KIT_ROOT / tree)
                self.assertEqual(moul.find_module_repo("c00"), workspace_c00, tree)
        finally:
            os.chdir(before)

    # ------------------------------------------------------------------ UX, dual layout, XP, REPL
    def test_guide_doctor_and_suggestions(self) -> None:
        doc = self.run_cli("doctor")
        self.assertEqual(doc.returncode, 0, doc.stdout + doc.stderr)
        self.assertIn("Setup check (doctor)", doc.stdout)
        self.assertIn("42 norminette", doc.stdout)
        self.assertIn("Exercise subjects are present", doc.stdout)

        guide = self.run_cli("guide", "ft_putchar")
        self.assertEqual(guide.returncode, 0, guide.stdout + guide.stderr)
        self.assertIn("How to work with moulinette", guide.stdout)
        self.assertIn("subject.en.txt", guide.stdout)
        self.assertIn("ft_putchar", guide.stdout)

        typo = self.run_cli("ft_putchra")
        self.assertEqual(typo.returncode, 1)
        self.assertIn("Did you mean:", typo.stdout)
        self.assertIn("ft_putchar", typo.stdout)

    def test_dual_workspace_directories_and_symlinks(self) -> None:
        moul.ensure_workspace_directories()
        ws_c00_ex00 = KIT_ROOT / "workspace" / "piscine" / "c00" / "ex00"
        ws_c00_real = KIT_ROOT / "workspace" / "piscine" / "c00" / "ft_putchar"
        self.assertTrue(ws_c00_ex00.is_symlink())
        self.assertEqual(os.readlink(ws_c00_ex00), "ft_putchar")
        self.assertTrue(ws_c00_real.is_dir())
        # Directory stays clean: no unwanted boilerplate .c or subject.en.txt injected automatically
        self.assertFalse((ws_c00_real / "ft_putchar.c").exists())
        self.assertFalse((ws_c00_real / "subject.en.txt").exists())

    def test_xp_not_doubled_when_ledger_is_deleted(self) -> None:
        turnin = self.reference_copy("piscine/c04/ft_strlen")
        ws_ledger = KIT_ROOT / "workspace" / "xp_ledger.json"
        ws_lock = KIT_ROOT / "workspace" / ".xp_ledger.json.lock"
        old_ledger = ws_ledger.read_bytes() if ws_ledger.exists() else None

        def _restore_ws() -> None:
            if old_ledger is not None:
                ws_ledger.write_bytes(old_ledger)
            else:
                ws_ledger.unlink(missing_ok=True)
            ws_lock.unlink(missing_ok=True)

        self.addCleanup(_restore_ws)
        ws_ledger.unlink(missing_ok=True)

        first = self.run_cli("c04/ft_strlen", "--dir", str(turnin))
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        prof_path = self.home / ".42_student_profile.json"
        self.assertTrue(prof_path.is_file())
        prof_after_first = json.loads(prof_path.read_text(encoding="utf-8"))
        xp_first = prof_after_first["total_xp"]
        self.assertGreater(xp_first, 0)
        self.assertIn("piscine/c04/ft_strlen", prof_after_first.get("validated_exercises", []))

        ws_ledger.unlink(missing_ok=True)
        second = self.run_cli("c04/ft_strlen", "--dir", str(turnin))
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        prof_after_second = json.loads(prof_path.read_text(encoding="utf-8"))
        self.assertEqual(prof_after_second["total_xp"], xp_first)

    def test_interactive_repl_guide_doctor_eval_and_errors(self) -> None:
        ex_dir = self.hand_made("c00", "ex01", "ft_print_alphabet")
        ledger = self.tmp / "repl_ledger.json"
        args = SimpleNamespace(
            dir=None,
            exam=False,
            norm=False,
            strict=False,
            watch=False,
            trace_out=None,
            xp_ledger=str(ledger),
        )
        theme = moul.ThemeEngine("plain")
        buf = io.StringIO()
        cmds = iter(
            [
                "guide ft_putchar",
                "doctor",
                "ft_putchra",
                "grade",
                "c00/ft_putchar --self-test",
                "ft_print_alphabet",
                "q",
            ]
        )
        prev_cwd = Path.cwd()
        os.chdir(ex_dir.parent.parent)
        try:
            with (
                mock.patch.dict(os.environ, {"HOME": str(self.home), "NO_COLOR": "1", "DT_SKIP_HOME_SYMLINKS": "1"}),
                mock.patch("builtins.input", side_effect=lambda _prompt="": next(cmds)),
                mock.patch.object(moul, "interactive_terminal_screen", lambda enabled=True: contextlib.nullcontext()),
                contextlib.redirect_stdout(buf),
            ):
                rc = moul.interactive_moulinette_repl(args, theme, is_practice=False)
        finally:
            os.chdir(prev_cwd)

        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("How to work with moulinette", out)
        self.assertIn("Setup check (doctor)", out)
        self.assertIn("Did you mean: ft_putchar", out)
        self.assertIn("Usage: grade <exercise|module>", out)
        self.assertEqual(out.count("Summary: ft_putchar -> OK :)"), 1, out)
        self.assertEqual(out.count("Summary: ft_print_alphabet -> OK :)"), 1, out)

        # Real PTY smoke test verifying sys.stdin.isatty() enters REPL and exits cleanly
        master_fd, slave_fd = pty.openpty()
        proc = None
        try:
            env = dict(os.environ, HOME=str(self.home), NO_COLOR="1", TERM="dumb", DT_SKIP_HOME_SYMLINKS="1")
            proc = subprocess.Popen(
                [sys.executable, str(MOULINETTE), "--no-color"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=str(KIT_ROOT),
                env=env,
                close_fds=True,
            )
            os.close(slave_fd)
            slave_fd = -1
            os.write(master_fd, b"guide\ndoctor\nq\n")
            chunks: list[bytes] = []
            deadline = 15.0
            import time as _time
            end = _time.monotonic() + deadline
            while _time.monotonic() < end:
                rlist, _, _ = select.select([master_fd], [], [], 0.25)
                if rlist:
                    try:
                        data = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if not data:
                        break
                    chunks.append(data)
                elif proc.poll() is not None:
                    break
            proc.wait(timeout=5)
            pty_out = b"".join(chunks).decode("utf-8", errors="replace")
            self.assertEqual(proc.returncode, 0, pty_out)
            self.assertIn("How to work with moulinette", pty_out)
            self.assertIn("Setup check (doctor)", pty_out)
        finally:
            if slave_fd >= 0:
                os.close(slave_fd)
            os.close(master_fd)
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
