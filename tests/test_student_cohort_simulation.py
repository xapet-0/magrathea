"""End-to-end simulation of first-time students, GitHub imports, and differential oracles."""

from __future__ import annotations

import ctypes
import datetime as dt
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

import yaml

KIT_ROOT = Path(__file__).resolve().parents[1]


def _load_script_module(name: str, script_path: Path) -> types.ModuleType:
    """Load an extensionless executable Python CLI script as a module."""
    loader = importlib.machinery.SourceFileLoader(name, str(script_path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


def _load_ui_theme() -> types.ModuleType:
    """Load deepthought.ui_theme directly via file path."""
    path = KIT_ROOT / "deepthought" / "ui_theme.py"
    spec = importlib.util.spec_from_file_location("deepthought.ui_theme", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["deepthought.ui_theme"] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_cli(
    args: list[str],
    *,
    env_extra: dict[str, str] | None = None,
    stdin_text: str | None = None,
    cwd: Path | None = None,
    timeout: float = 20.0,
) -> subprocess.CompletedProcess[str]:
    """Run a CLI command in an isolated clean environment."""
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env.setdefault("HOME", "/tmp")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        args,
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=str(cwd or KIT_ROOT),
        env=env,
        timeout=timeout,
    )


def _norm_cmd_line(line: str) -> str:
    """Normalize shell prompt spacing and outer quotes for example comparison."""
    text = re.sub(r"^\$>\s*", "$> ", line.strip())
    text = text.replace("'", '"')
    return re.sub(r"\s+", " ", text)


def _find_compiler() -> str:
    """Return an available C compiler binary path."""
    for cand in ("cc", "gcc", "clang"):
        found = subprocess.run(
            ["which", cand],
            capture_output=True,
            text=True,
        )
        if found.returncode == 0 and found.stdout.strip():
            return found.stdout.strip()
    raise RuntimeError("No C compiler found on PATH")


# Student C implementations modeled on public 42 GitHub repos and common pitfalls.
_FT_STRLEN_OK = """\
int\tft_strlen(char *str)
{
\tint\ti;

\ti = 0;
\twhile (str[i])
\t\ti++;
\treturn (i);
}
"""

_FT_SWAP_OK = """\
void\tft_swap(int *a, int *b)
{
\tint\ttmp;

\ttmp = *a;
\t*a = *b;
\t*b = tmp;
}
"""

# Glagan-style ft_strcmp uses unsigned char casting to match glibc strcmp(3).
_FT_STRCMP_OK = """\
int\tft_strcmp(char *s1, char *s2)
{
\tunsigned int\ti;

\ti = 0;
\twhile (s1[i] && s1[i] == s2[i])
\t\ti++;
\treturn ((unsigned char)s1[i] - (unsigned char)s2[i]);
}
"""

# GitHub pitfall (e.g. alexhiguera-style): signed char subtraction fails >= 0x80.
_FT_STRCMP_SIGNED_BUG = """\
int\tft_strcmp(char *s1, char *s2)
{
\tint\ti;

\ti = 0;
\twhile (s1[i] && s1[i] == s2[i])
\t\ti++;
\treturn (s1[i] - s2[i]);
}
"""

# 42-compliant ft_atoi using negative accumulator so INT_MIN never UB-overflows.
_FT_ATOI_OK = """\
int\tft_atoi(const char *str)
{
\tlong\tacc;
\tint\tsign;

\tacc = 0;
\tsign = 1;
\twhile (*str == ' ' || (*str >= 9 && *str <= 13))
\t\tstr++;
\tif (*str == '-' || *str == '+')
\t{
\t\tif (*str == '-')
\t\t\tsign = -1;
\t\tstr++;
\t}
\twhile (*str >= '0' && *str <= '9')
\t{
\t\tacc = acc * 10 - (*str - '0');
\t\tstr++;
\t}
\tif (sign > 0)
\t\treturn ((int)(-acc));
\treturn ((int)acc);
}
"""

_FIRST_WORD_OK = """\
#include <unistd.h>

int\tmain(int argc, char **argv)
{
\tint\ti;

\tif (argc == 2)
\t{
\t\ti = 0;
\t\twhile (argv[1][i] == ' ' || argv[1][i] == '\\t')
\t\t\ti++;
\t\twhile (argv[1][i] && argv[1][i] != ' ' && argv[1][i] != '\\t')
\t\t{
\t\t\twrite(1, &argv[1][i], 1);
\t\t\ti++;
\t\t}
\t}
\twrite(1, "\\n", 1);
\treturn (0);
}
"""

# Exam ft_split only allows malloc (no free).
_FT_SPLIT_OK = """\
#include <stdlib.h>

static int\tis_sep(char c)
{
\treturn (c == ' ' || c == '\\t' || c == '\\n');
}

static int\tcount_words(char *s)
{
\tint\tcount;
\tint\tin_word;

\tcount = 0;
\tin_word = 0;
\twhile (*s)
\t{
\t\tif (!is_sep(*s) && !in_word)
\t\t{
\t\t\tin_word = 1;
\t\t\tcount++;
\t\t}
\t\telse if (is_sep(*s))
\t\t\tin_word = 0;
\t\ts++;
\t}
\treturn (count);
}

static char\t*dup_word(char *start, int len)
{
\tchar\t*out;
\tint\ti;

\tout = (char *)malloc((size_t)len + 1);
\tif (!out)
\t\treturn (NULL);
\ti = 0;
\twhile (i < len)
\t{
\t\tout[i] = start[i];
\t\ti++;
\t}
\tout[i] = '\\0';
\treturn (out);
}

char\t**ft_split(char *str)
{
\tchar\t**res;
\tint\tidx;
\tint\tlen;

\tres = (char **)malloc(sizeof(char *) * (size_t)(count_words(str) + 1));
\tif (!res)
\t\treturn (NULL);
\tidx = 0;
\twhile (*str)
\t{
\t\twhile (*str && is_sep(*str))
\t\t\tstr++;
\t\tlen = 0;
\t\twhile (str[len] && !is_sep(str[len]))
\t\t\tlen++;
\t\tif (len > 0)
\t\t{
\t\t\tres[idx++] = dup_word(str, len);
\t\t\tstr += len;
\t\t}
\t}
\tres[idx] = NULL;
\treturn (res);
}
"""

_PICOSHELL_OK = """\
#include <stdlib.h>
#include <sys/wait.h>
#include <unistd.h>

int\tpicoshell(char **cmds[])
{
\tint\ti;
\tint\tprev_fd;
\tint\tfds[2];
\tpid_t\tpid;
\tint\tstatus;
\tint\tret;

\tprev_fd = -1;
\ti = 0;
\tret = 0;
\twhile (cmds && cmds[i])
\t{
\t\tif (cmds[i + 1] && pipe(fds) < 0)
\t\t\treturn (1);
\t\tpid = fork();
\t\tif (pid < 0)
\t\t\treturn (1);
\t\tif (pid == 0)
\t\t{
\t\t\tif (prev_fd != -1)
\t\t\t{
\t\t\t\tdup2(prev_fd, STDIN_FILENO);
\t\t\t\tclose(prev_fd);
\t\t\t}
\t\t\tif (cmds[i + 1])
\t\t\t{
\t\t\t\tclose(fds[0]);
\t\t\t\tdup2(fds[1], STDOUT_FILENO);
\t\t\t\tclose(fds[1]);
\t\t\t}
\t\t\texecvp(cmds[i][0], cmds[i]);
\t\t\texit(1);
\t\t}
\t\tif (prev_fd != -1)
\t\t\tclose(prev_fd);
\t\tif (cmds[i + 1])
\t\t{
\t\t\tclose(fds[1]);
\t\t\tprev_fd = fds[0];
\t\t}
\t\telse
\t\t\tprev_fd = -1;
\t\ti++;
\t}
\twhile (wait(&status) > 0)
\t{
\t\tif (!WIFEXITED(status) || WEXITSTATUS(status) != 0)
\t\t\tret = 1;
\t}
\treturn (ret);
}
"""

# GitHub pitfall (e.g. tigran-sargsyan-w-style): accidental main() in c_function.
_PICOSHELL_WITH_MAIN = (
    _PICOSHELL_OK
    + """
int\tmain(void)
{
\tchar\t*c1[] = {"echo", "ok", NULL};
\tchar\t**cmds[] = {c1, NULL};

\treturn (picoshell(cmds));
}
"""
)

_FT_STRLEN_NORM_BAD = """\
int ft_strlen(char *str) {
\tint i = 0;
\tfor (; str[i]; i++) {}
\treturn i;
}
"""

_FT_STRLEN_CRASH = """\
#include <stdlib.h>

int\tft_strlen(char *str)
{
\t(void)str;
\tabort();
\treturn (0);
}
"""

_FT_STRLEN_TIMEOUT = """\
int\tft_strlen(char *str)
{
\twhile (str)
\t\tcontinue ;
\treturn (0);
}
"""

_FT_PUTCHAR_BODY = """\
#include <unistd.h>

void\tft_putchar(char c)
{
\twrite(1, &c, 1);
}
"""


class StudentCohortSimulationTests(unittest.TestCase):
    """End-to-end simulation of students, catalogs, CLIs, pushes, and C oracles."""

    examshell_mod: types.ModuleType
    ui_theme_mod: types.ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        """Load shared modules needed across cohort simulation tests."""
        cls.ui_theme_mod = _load_ui_theme()
        cls.examshell_mod = _load_script_module(
            "examshell_cohort_sim", KIT_ROOT / "bin" / "examshell"
        )

    def _run_examshell_cmd(self, shell: object, cmd_line: str) -> str:
        """Execute an ExamShell command while capturing stdout and auto-confirming."""
        buf = io.StringIO()
        with (
            mock.patch.object(sys, "stdout", buf),
            mock.patch("builtins.input", lambda _prompt="": "y"),
        ):
            shell.onecmd(cmd_line)
        return buf.getvalue()

    def _assert_all_lines_fit_79(self, text: str, label: str) -> None:
        """Assert every line in CLI output fits strictly within 79 columns."""
        vlen = self.ui_theme_mod.visible_len
        over = [
            (idx + 1, vlen(line), line)
            for idx, line in enumerate(text.splitlines())
            if vlen(line) > 79
        ]
        self.assertEqual(
            over,
            [],
            msg=f"{label} exceeded 79 visible columns: {over[:5]}",
        )

    def test_01_all_subjects_and_examples_consistency_across_both_clis(self) -> None:
        """Audit all 439 subjects, examples, tests, and CLI catalog parity."""
        exam_pool_refs: set[str] = set()
        for pool_file in sorted((KIT_ROOT / "pools" / "exams").glob("*.yml")):
            pdata = yaml.safe_load(pool_file.read_text(encoding="utf-8"))
            self.assertIsInstance(pdata, dict, msg=str(pool_file))
            for lvl in pdata.get("levels", []):
                for slug in lvl.get("candidates", []):
                    exam_pool_refs.add(str(slug))

        piscine_pool_refs: set[str] = set()
        for pool_file in sorted((KIT_ROOT / "pools" / "piscine").glob("*.yml")):
            pdata = yaml.safe_load(pool_file.read_text(encoding="utf-8"))
            self.assertIsInstance(pdata, dict, msg=str(pool_file))
            for ex in pdata.get("exercises", []):
                sid = str(ex["subject_id"]).removeprefix("piscine/")
                piscine_pool_refs.add(sid)

        exam_dirs = {
            p.name for p in (KIT_ROOT / "subjects" / "exams").iterdir() if p.is_dir()
        }
        piscine_root = KIT_ROOT / "subjects" / "piscine"
        piscine_dirs = {
            str(p.parent.relative_to(piscine_root))
            for p in piscine_root.rglob("meta.yml")
        }

        self.assertEqual(exam_pool_refs, exam_dirs)
        self.assertEqual(piscine_pool_refs, piscine_dirs)
        self.assertEqual(len(exam_dirs), 303)
        self.assertEqual(len(piscine_dirs), 136)

        synchronized_exams = {
            "alpha_index_case",
            "biggest_pal",
            "count_island",
            "dup_finder",
            "index_case",
            "n_queens",
            "rip",
            "rostring",
            "rstr_capitalizer",
            "str_capitalizer",
            "vbc",
            "vbc (without tree)",
        }

        all_subject_dirs = [
            KIT_ROOT / "subjects" / "exams" / slug for slug in sorted(exam_dirs)
        ] + [piscine_root / sid for sid in sorted(piscine_dirs)]
        for sdir in all_subject_dirs:
            for fname in ("subject.en.txt", "examples.txt", "tests.yml", "meta.yml"):
                fpath = sdir / fname
                self.assertTrue(fpath.is_file(), msg=f"Missing {fpath}")
                self.assertTrue(
                    fpath.read_text(encoding="utf-8").strip(),
                    msg=f"Empty {fpath}",
                )
            tests_data = yaml.safe_load(
                (sdir / "tests.yml").read_text(encoding="utf-8")
            )
            self.assertIsInstance(
                tests_data, dict, msg=f"Invalid YAML {sdir}/tests.yml"
            )
            meta_data = yaml.safe_load((sdir / "meta.yml").read_text(encoding="utf-8"))
            self.assertIsInstance(meta_data, dict, msg=f"Invalid YAML {sdir}/meta.yml")

        # Verify no duplicate trailing $> blocks across all 303 exams, and synchronized
        # exam examples match their subject.en.txt $> prompts.
        for slug in sorted(exam_dirs):
            sdir = KIT_ROOT / "subjects" / "exams" / slug
            subj_txt = (sdir / "subject.en.txt").read_text(encoding="utf-8")
            ex_txt = (sdir / "examples.txt").read_text(encoding="utf-8")
            blocks = re.split(r"\n(?=\$>)", subj_txt.strip())
            if len(blocks) >= 2:
                self.assertNotEqual(
                    blocks[-1].strip(),
                    blocks[-2].strip(),
                    msg=f"Duplicate trailing example in {slug}/subject.en.txt",
                )
            if slug in synchronized_exams:
                ex_cmds = {
                    _norm_cmd_line(ln)
                    for ln in ex_txt.splitlines()
                    if ln.strip().startswith("$>") and ln.strip() != "$>"
                }
                for ln in subj_txt.splitlines():
                    stripped = ln.strip()
                    if stripped.startswith("$>") and stripped != "$>":
                        self.assertIn(
                            _norm_cmd_line(stripped),
                            ex_cmds,
                            msg=f"{slug}/examples.txt missing subject prompt: {stripped}",
                        )

        # Confirm brainfuck's Hi$ example from subject.en.txt is present in tests.yml.
        bf_tests = yaml.safe_load(
            (KIT_ROOT / "subjects" / "exams" / "brainfuck" / "tests.yml").read_text(
                encoding="utf-8"
            )
        )
        bf_fixed = {t.get("name"): t for t in bf_tests.get("fixed_tests", [])}
        self.assertIn("subj_ex_02", bf_fixed)
        self.assertEqual(bf_fixed["subj_ex_02"]["expected"], "Hi\n")

        # Verify both CLIs expose pools, lists, and matching subjects.
        m_exams = _run_cli([sys.executable, str(KIT_ROOT / "bin/moulinette"), "exams"])
        m_piscine = _run_cli(
            [sys.executable, str(KIT_ROOT / "bin/moulinette"), "piscine"]
        )
        m_list = _run_cli([sys.executable, str(KIT_ROOT / "bin/moulinette"), "list"])
        e_menu = _run_cli(
            [sys.executable, str(KIT_ROOT / "bin/examshell"), "--menu", "--no-color"]
        )
        for label, proc in (
            ("moulinette exams", m_exams),
            ("moulinette piscine", m_piscine),
            ("moulinette list", m_list),
            ("examshell --menu", e_menu),
        ):
            self.assertEqual(proc.returncode, 0, msg=f"{label}: {proc.stderr}")
            self._assert_all_lines_fit_79(proc.stdout, label)

        self.assertIn("rank02", m_exams.stdout)
        self.assertIn("rank02", e_menu.stdout)
        self.assertIn("c00", m_piscine.stdout)

        with tempfile.TemporaryDirectory() as tmp:
            bd = Path(tmp) / "exam-bd"
            shell = self.examshell_mod.ExamShell(
                pool="rank02",
                seed=7,
                practice=True,
                no_color=True,
                basedir=bd,
                login="catalog_chk",
                fresh_confirmed=True,
            )
            for slug in ("ft_strlen", "vbc", "picoshell"):
                m_sub = _run_cli(
                    [sys.executable, str(KIT_ROOT / "bin/moulinette"), "subject", slug]
                )
                self.assertEqual(m_sub.returncode, 0, msg=m_sub.stderr)
                assign_out = self._run_examshell_cmd(shell, f"assign {slug}")
                self.assertIn(slug, assign_out)
                es_subj = (shell.subjects_dir / slug / "subject.en.txt").read_text(
                    encoding="utf-8"
                )
                self.assertIn(slug, es_subj)
                self.assertIn(slug, m_sub.stdout)

    def test_02_first_time_student_onboarding_and_79_col_ux(self) -> None:
        """Simulate a first-time naive student checking onboarding UX across all CLIs."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home_dir = root / "home"
            home_dir.mkdir()
            env_iso = {"HOME": str(home_dir), "NO_COLOR": "1"}

            # 1. Check all discovery/help commands fit strictly within <= 79 columns.
            cli_checks = [
                (
                    "moulinette --help",
                    [sys.executable, str(KIT_ROOT / "bin/moulinette"), "--help"],
                    True,
                ),
                (
                    "moulinette guide",
                    [sys.executable, str(KIT_ROOT / "bin/moulinette"), "guide"],
                    True,
                ),
                (
                    "moulinette guide ft_strlen",
                    [
                        sys.executable,
                        str(KIT_ROOT / "bin/moulinette"),
                        "guide",
                        "ft_strlen",
                    ],
                    True,
                ),
                (
                    "moulinette doctor",
                    [sys.executable, str(KIT_ROOT / "bin/moulinette"), "doctor"],
                    True,
                ),
                (
                    "moulinette c00",
                    [sys.executable, str(KIT_ROOT / "bin/moulinette"), "c00"],
                    False,
                ),
                (
                    "moulinette c_piscine_exam_00",
                    [
                        sys.executable,
                        str(KIT_ROOT / "bin/moulinette"),
                        "c_piscine_exam_00",
                    ],
                    True,
                ),
                (
                    "moulinette xp",
                    [sys.executable, str(KIT_ROOT / "bin/moulinette"), "xp"],
                    True,
                ),
                (
                    "deepthought c00",
                    [
                        sys.executable,
                        str(KIT_ROOT / "bin/deepthought"),
                        "c00",
                        "--dir",
                        str(root / "empty_c00"),
                        "--no-color",
                    ],
                    False,
                ),
                (
                    "examshell --help",
                    [sys.executable, str(KIT_ROOT / "bin/examshell"), "--help"],
                    True,
                ),
                (
                    "examshell --menu",
                    [
                        sys.executable,
                        str(KIT_ROOT / "bin/examshell"),
                        "--menu",
                        "--no-color",
                    ],
                    True,
                ),
            ]
            for label, cmd, expect_zero in cli_checks:
                proc = _run_cli(cmd, env_extra=env_iso)
                if expect_zero:
                    self.assertEqual(proc.returncode, 0, msg=f"{label}: {proc.stderr}")
                self._assert_all_lines_fit_79(proc.stdout + proc.stderr, label)

            # 2. Naive student initializes starter files via moulinette init (C + vbc starter).
            ws_vbc = root / "ws_vbc"
            p_init_vbc = _run_cli(
                [
                    sys.executable,
                    str(KIT_ROOT / "bin/moulinette"),
                    "init",
                    "vbc",
                    "--dir",
                    str(ws_vbc),
                ],
                env_extra=env_iso,
            )
            self.assertEqual(p_init_vbc.returncode, 0, msg=p_init_vbc.stderr)
            self.assertEqual(list(ws_vbc.iterdir()), [ws_vbc / "vbc.c"])
            self.assertIn("subject.en.txt", p_init_vbc.stdout)
            self._assert_all_lines_fit_79(p_init_vbc.stdout, "moulinette init vbc")
            self.assertIn("parse_expr", (ws_vbc / "vbc.c").read_text(encoding="utf-8"))

            # 3. Verify bin/bc -V compatibility shim.
            p_bc_v = _run_cli(
                [sys.executable, str(KIT_ROOT / "bin/bc"), "-V"],
                env_extra={"FT_BC_INTERNAL": "1", **env_iso},
            )
            self.assertEqual(p_bc_v.returncode, 0, msg=p_bc_v.stderr)
            self.assertTrue(p_bc_v.stdout.strip())

            # Verify Classic 42 Bocal / ExamShell UX and module catalog layout.
            c00_proc = _run_cli(
                [sys.executable, str(KIT_ROOT / "bin/moulinette"), "list", "c00"],
                env_extra=env_iso,
            )
            self.assertEqual(c00_proc.returncode, 0, msg=c00_proc.stderr)
            self._assert_all_lines_fit_79(c00_proc.stdout, "moulinette list c00")
            self.assertIn("= piscine module: c00", c00_proc.stdout)
            self.assertIn("subjects/piscine/c00/<name>/subject.en.txt", c00_proc.stdout)
            self.assertIn("workspace/piscine/c00/<ex>/", c00_proc.stdout)
            self.assertIn("ex00..ex08", c00_proc.stdout)
            self.assertNotIn("ft_putchar/subject.en.txt", c00_proc.stdout)
            self.assertNotIn("workspace/piscine/c00/ex00/", c00_proc.stdout)

            palette_42 = self.ui_theme_mod.PALETTES["42-cluster"]
            self.assertNotEqual(palette_42.secondary, palette_42.muted)

            t_plain = self.ui_theme_mod.ThemeEngine("plain")
            self.assertFalse(hasattr(t_plain, "stats_block"))
            status_samples = [
                (t_plain.status("good", "Ready"), "OK: Ready"),
                (t_plain.status("error", "Locked"), "Error: Locked"),
                (t_plain.status("warning", "Slow"), "Warning: Slow"),
                (t_plain.status("status", "Info line"), "  Info line"),
            ]
            for rendered, expected in status_samples:
                self.assertEqual(rendered, expected)
            tbl_text = "\n".join(
                t_plain.table("EXAMS", ["#", "Pool"], [["1", "rank02"]])
            )
            self._assert_all_lines_fit_79(tbl_text, "ThemeEngine.table")
            combined_ui = "\n".join([*(r for r, _ in status_samples), tbl_text])
            for msf_tok in ("[*]", "[+]", "[-]", "[!]", "+ -- --=["):
                self.assertNotIn(msf_tok, combined_ui)

            # 4. Naive student launches ExamShell for the first time in real vs practice mode.
            real_bd = root / "exam-real"
            real_shell = self.examshell_mod.ExamShell(
                pool="c_piscine_exam_00",
                level=0,
                seed=1,
                practice=False,
                no_color=True,
                basedir=real_bd,
                login="newbie42",
                fresh_confirmed=True,
            )
            assign_denied = self._run_examshell_cmd(real_shell, "assign ft_strlen")
            self.assertEqual(real_shell.last_exit_code, 2)
            self.assertIn("restricted", assign_denied.lower())

            prac_bd = root / "exam-practice"
            shell = self.examshell_mod.ExamShell(
                pool="rank02",
                level=0,
                seed=2,
                practice=True,
                no_color=True,
                basedir=prac_bd,
                login="newbie42",
                fresh_confirmed=True,
            )
            help_out = self._run_examshell_cmd(shell, "help")
            self.assertIn("init", help_out)
            self.assertIn("grademe", help_out)
            status_out = self._run_examshell_cmd(shell, "status")
            self.assertIn(shell.current_assignment, status_out)

            # Trying grademe before pushing must fail cleanly without crashing.
            pre_push_grade = self._run_examshell_cmd(shell, "grademe --now")
            self.assertNotEqual(shell.grade, 100)
            self.assertTrue(len(pre_push_grade.strip()) > 0)

            # Switch to first_word, scaffold with init, check before/after edit, and run locally.
            self._run_examshell_cmd(shell, "assign first_word")
            self._run_examshell_cmd(shell, "init")
            target_c = shell.rendu_dir / "first_word" / "first_word.c"
            self.assertTrue(target_c.is_file())
            target_c.write_text(_FIRST_WORD_OK, encoding="utf-8")
            check_out = self._run_examshell_cmd(shell, "check")
            self.assertIn("first_word", check_out)
            self.assertIn("[PRE-FLIGHT OK]", check_out)
            run_out = self._run_examshell_cmd(shell, 'run "  hello   world"')
            self.assertIn("hello", run_out)

    def test_03_student_cohort_vogsphere_push_and_5_gate_grading(self) -> None:
        """Simulate multiple students pushing GitHub solutions and triggering all 5 gates."""
        now_box = [1_700_000_000.0]

        def fake_clock() -> dt.datetime:
            return dt.datetime.fromtimestamp(now_box[0], tz=dt.timezone.utc)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "xp_ledger.json"

            # === Student A: Strong cohort pushing GitHub-modeled solutions ===
            shell_a = self.examshell_mod.ExamShell(
                pool="rank02",
                level=0,
                seed=2,
                practice=True,
                no_color=True,
                basedir=root / "student_a",
                login="alice_ok",
                clock_fn=fake_clock,
                fresh_confirmed=True,
            )
            shell_a2 = self.examshell_mod.ExamShell(
                pool="rank04",
                level=0,
                seed=2,
                practice=True,
                no_color=True,
                basedir=root / "student_a_rank04",
                login="alice_ok",
                clock_fn=fake_clock,
                fresh_confirmed=True,
            )

            rank02_solutions = [
                ("ft_strlen", "ft_strlen.c", _FT_STRLEN_OK),
                ("ft_swap", "ft_swap.c", _FT_SWAP_OK),
                ("ft_strcmp", "ft_strcmp.c", _FT_STRCMP_OK),
                ("ft_atoi", "ft_atoi.c", _FT_ATOI_OK),
                ("first_word", "first_word.c", _FIRST_WORD_OK),
            ]
            followup_solutions = [
                ("ft_split", "ft_split.c", _FT_SPLIT_OK),
                ("picoshell", "picoshell.c", _PICOSHELL_OK),
            ]

            for active_shell, batch, expect_full_pass in (
                (shell_a, rank02_solutions, True),
                (shell_a2, followup_solutions, False),
            ):
                for slug, fname, code in batch:
                    self._run_examshell_cmd(active_shell, f"assign {slug}")
                    self._run_examshell_cmd(active_shell, "init")
                    sub_dir = active_shell.rendu_dir / slug
                    (sub_dir / fname).write_text(code, encoding="utf-8")
                    # Plant an unrelated file to verify grader isolates the current assignment.
                    (active_shell.rendu_dir / "distractor.c").write_text(
                        "int broken( {\n", encoding="utf-8"
                    )
                    prev_grade = active_shell.grade
                    push_out = self._run_examshell_cmd(active_shell, "push")
                    self.assertIn("push", push_out.lower())

                    # Verify the file is actually committed in bare vogsphere.git.
                    ls_proc = _run_cli(
                        [
                            "git",
                            "--git-dir",
                            str(active_shell.vogsphere_dir),
                            "ls-tree",
                            "-r",
                            "--name-only",
                            "HEAD",
                        ]
                    )
                    self.assertEqual(ls_proc.returncode, 0, msg=ls_proc.stderr)
                    self.assertIn(f"{slug}/{fname}", ls_proc.stdout.splitlines())

                    grade_out = self._run_examshell_cmd(active_shell, "grademe --now")
                    self.assertIn("OK", grade_out)
                    self.assertGreater(
                        active_shell.grade,
                        prev_grade,
                        msg=f"{slug} did not increase grade",
                    )
                    traces = sorted(active_shell.traces_dir.glob(f"*{slug}*"))
                    self.assertTrue(traces, msg=f"Missing trace for {slug}")
                    now_box[0] += 300.0
                if expect_full_pass:
                    self.assertEqual(active_shell.grade, 100)
                    self.assertEqual(active_shell.lifecycle_state, "passed")

            # Also verify Student A Piscine strict + Norminette grading + isolated XP ledger.
            c00_ex00 = root / "c00" / "ex00"
            p_init = _run_cli(
                [
                    sys.executable,
                    str(KIT_ROOT / "bin/moulinette"),
                    "init",
                    "c00/ft_putchar",
                    "--dir",
                    str(c00_ex00),
                ]
            )
            self.assertEqual(p_init.returncode, 0, msg=p_init.stderr)
            hdr_lines = (
                (c00_ex00 / "ft_putchar.c")
                .read_text(encoding="utf-8")
                .splitlines()[:11]
            )
            (c00_ex00 / "ft_putchar.c").write_text(
                "\n".join(hdr_lines) + "\n\n" + _FT_PUTCHAR_BODY,
                encoding="utf-8",
            )
            p_strict = _run_cli(
                [
                    sys.executable,
                    str(KIT_ROOT / "bin/moulinette"),
                    "c00/ft_putchar",
                    "--strict",
                    "--dir",
                    str(c00_ex00),
                    "--xp-ledger",
                    str(ledger),
                    "--no-color",
                ]
            )
            self.assertEqual(
                p_strict.returncode, 0, msg=p_strict.stdout + p_strict.stderr
            )
            self.assertTrue(ledger.is_file())
            ledger_data = json.loads(ledger.read_text(encoding="utf-8"))
            self.assertGreater(int(ledger_data.get("total_xp", 0)), 0)

            # === Student B: Faulty cohort hitting all 5 Deepthought gates ===
            bd_b = root / "student_b"
            shell_b = self.examshell_mod.ExamShell(
                pool="rank02",
                level=0,
                seed=2,
                practice=True,
                no_color=True,
                basedir=bd_b,
                login="bob_fail",
                clock_fn=fake_clock,
                fresh_confirmed=True,
            )

            # Gate 1: Turn-in wrong filename in rendu/
            self._run_examshell_cmd(shell_b, "assign ft_strlen")
            (shell_b.rendu_dir / "ft_strlen").mkdir(parents=True, exist_ok=True)
            (shell_b.rendu_dir / "ft_strlen" / "wrong_name.c").write_text(
                _FT_STRLEN_OK, encoding="utf-8"
            )
            self._run_examshell_cmd(shell_b, "push")
            g1_out = self._run_examshell_cmd(shell_b, "grademe --now")
            self.assertEqual(shell_b.grade, 0)
            self.assertNotIn("OK :)", g1_out)

            # Gate 2a: Compilation error — GitHub picoshell with main() in c_function
            self._run_examshell_cmd(shell_b, "assign picoshell")
            p_picoshell_dir = root / "bad_picoshell"
            p_picoshell_dir.mkdir()
            (p_picoshell_dir / "picoshell.c").write_text(
                _PICOSHELL_WITH_MAIN, encoding="utf-8"
            )
            g2a = _run_cli(
                [
                    sys.executable,
                    str(KIT_ROOT / "bin/moulinette"),
                    "picoshell",
                    "--exam",
                    "--dir",
                    str(p_picoshell_dir),
                    "--json",
                ]
            )
            self.assertNotEqual(g2a.returncode, 0)
            g2a_json = json.loads(g2a.stdout)
            self.assertFalse(g2a_json.get("passed", True))

            # Gate 2b: Norminette rejection with --norm on non-42 code
            bad_norm_dir = root / "bad_norm"
            bad_norm_dir.mkdir()
            (bad_norm_dir / "ft_strlen.c").write_text(
                _FT_STRLEN_NORM_BAD, encoding="utf-8"
            )
            g2b = _run_cli(
                [
                    sys.executable,
                    str(KIT_ROOT / "bin/moulinette"),
                    "ft_strlen",
                    "--exam",
                    "--norm",
                    "--dir",
                    str(bad_norm_dir),
                    "--json",
                ]
            )
            self.assertNotEqual(g2b.returncode, 0)
            g2b_json = json.loads(g2b.stdout)
            self.assertFalse(g2b_json.get("passed", True))

            # Gate 3: Diff KO — alexhiguera-style signed char ft_strcmp bug
            bad_strcmp_dir = root / "bad_strcmp"
            bad_strcmp_dir.mkdir()
            (bad_strcmp_dir / "ft_strcmp.c").write_text(
                _FT_STRCMP_SIGNED_BUG, encoding="utf-8"
            )
            g3 = _run_cli(
                [
                    sys.executable,
                    str(KIT_ROOT / "bin/moulinette"),
                    "ft_strcmp",
                    "--exam",
                    "--dir",
                    str(bad_strcmp_dir),
                    "--json",
                ]
            )
            self.assertNotEqual(g3.returncode, 0)
            g3_json = json.loads(g3.stdout)
            self.assertFalse(g3_json.get("passed", True))

            # Gate 4: Runtime Crash (SIGABRT) via examshell push + grademe
            now_box[0] += 1000.0
            self._run_examshell_cmd(shell_b, "assign ft_strlen")
            (shell_b.rendu_dir / "ft_strlen" / "ft_strlen.c").write_text(
                _FT_STRLEN_CRASH, encoding="utf-8"
            )
            self._run_examshell_cmd(shell_b, "push")
            g4_out = self._run_examshell_cmd(shell_b, "grademe --now")
            self.assertEqual(shell_b.grade, 0)
            self.assertNotIn("OK :)", g4_out)

            # Gate 5: Timeout (infinite loop) cleanly caught without hanging
            bad_to_dir = root / "bad_timeout"
            bad_to_dir.mkdir()
            (bad_to_dir / "ft_strlen.c").write_text(
                _FT_STRLEN_TIMEOUT, encoding="utf-8"
            )
            g5 = _run_cli(
                [
                    sys.executable,
                    str(KIT_ROOT / "bin/moulinette"),
                    "ft_strlen",
                    "--exam",
                    "--dir",
                    str(bad_to_dir),
                    "--json",
                ],
                timeout=15.0,
            )
            self.assertNotEqual(g5.returncode, 0)
            g5_json = json.loads(g5.stdout)
            self.assertFalse(g5_json.get("passed", True))

    def test_04_differential_oracle_against_glibc_and_system_bc(self) -> None:
        """Compare student C implementations directly against glibc and bin/bc against /usr/bin/bc."""
        cc = _find_compiler()
        libc = ctypes.CDLL("libc.so.6")
        libc.strlen.argtypes = [ctypes.c_char_p]
        libc.strlen.restype = ctypes.c_size_t
        libc.strcmp.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        libc.strcmp.restype = ctypes.c_int
        libc.atoi.argtypes = [ctypes.c_char_p]
        libc.atoi.restype = ctypes.c_int

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ok_c = root / "student_ok.c"
            ok_so = root / "student_ok.so"
            ok_c.write_text(
                "\n".join((_FT_STRLEN_OK, _FT_STRCMP_OK, _FT_ATOI_OK)),
                encoding="utf-8",
            )
            comp_ok = _run_cli(
                [
                    cc,
                    "-shared",
                    "-fPIC",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    str(ok_c),
                    "-o",
                    str(ok_so),
                ]
            )
            self.assertEqual(comp_ok.returncode, 0, msg=comp_ok.stderr)

            student_lib = ctypes.CDLL(str(ok_so))
            student_lib.ft_strlen.argtypes = [ctypes.c_char_p]
            student_lib.ft_strlen.restype = ctypes.c_int
            student_lib.ft_strcmp.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
            student_lib.ft_strcmp.restype = ctypes.c_int
            student_lib.ft_atoi.argtypes = [ctypes.c_char_p]
            student_lib.ft_atoi.restype = ctypes.c_int

            # Differential check 1: ft_strlen vs glibc strlen(3).
            for sample in (b"", b"a", b"Hello 42!", b"\xff\xfeabc", b"x" * 256):
                self.assertEqual(student_lib.ft_strlen(sample), libc.strlen(sample))

            # Differential check 2: ft_strcmp vs glibc strcmp(3) including unsigned char >= 0x80.
            cmp_pairs = [
                (b"", b""),
                (b"abc", b"abc"),
                (b"abc", b"abd"),
                (b"ab", b"abc"),
                (b"\x80", b"a"),
                (b"a", b"\xff"),
            ]
            for s1, s2 in cmp_pairs:
                got = student_lib.ft_strcmp(s1, s2)
                exp = libc.strcmp(s1, s2)
                got_sign = (got > 0) - (got < 0)
                exp_sign = (exp > 0) - (exp < 0)
                self.assertEqual(
                    got_sign, exp_sign, msg=f"strcmp mismatch on {s1!r}, {s2!r}"
                )

            # Prove signed-char GitHub bug diverges from glibc strcmp(3) on 0x80 vs 'a'.
            bug_c = root / "student_bug.c"
            bug_so = root / "student_bug.so"
            bug_c.write_text(_FT_STRCMP_SIGNED_BUG, encoding="utf-8")
            comp_bug = _run_cli([cc, "-shared", "-fPIC", str(bug_c), "-o", str(bug_so)])
            self.assertEqual(comp_bug.returncode, 0, msg=comp_bug.stderr)
            bug_lib = ctypes.CDLL(str(bug_so))
            bug_lib.ft_strcmp.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
            bug_lib.ft_strcmp.restype = ctypes.c_int
            # On platforms with signed char (x86_64 Linux), '\x80' - 'a' is negative vs glibc > 0.
            if ctypes.c_char(b"\x80").value != b"\x80" or ctypes.c_int8(-128).value < 0:
                self.assertLess(bug_lib.ft_strcmp(b"\x80", b"a"), 0)
                self.assertGreater(libc.strcmp(b"\x80", b"a"), 0)

            # Differential check 3: ft_atoi vs glibc atoi(3).
            atoi_samples = [
                b"0",
                b"42",
                b"   \t\n\v\f\r  -42",
                b"  +43abc",
                b"   --42",
                b"2147483647",
                b"-2147483648",
                b"",
            ]
            for raw in atoi_samples:
                self.assertEqual(
                    student_lib.ft_atoi(raw),
                    libc.atoi(raw),
                    msg=f"atoi mismatch on {raw!r}",
                )

            # Differential check 4: FT_BC_INTERNAL=1 bin/bc vs /usr/bin/bc.
            bc_script = (
                "\n".join(
                    [
                        "2 + 3 * 4",
                        "scale = 4; 22 / 7",
                        "scale = 0; obase = 16; 255",
                        "obase = 10; ibase = 2; 101010",
                        "ibase = A; a = 6; b = 7; a * b",
                        "sqrt(1764)",
                        "if (b > a) 42",
                        "quit",
                    ]
                )
                + "\n"
            )
            internal_bc = _run_cli(
                [sys.executable, str(KIT_ROOT / "bin/bc"), "-q"],
                env_extra={"FT_BC_INTERNAL": "1"},
                stdin_text=bc_script,
            )
            self.assertEqual(internal_bc.returncode, 0, msg=internal_bc.stderr)
            sys_bc = Path("/usr/bin/bc")
            if sys_bc.is_file():
                ref_bc = _run_cli([str(sys_bc), "-q"], stdin_text=bc_script)
                self.assertEqual(ref_bc.returncode, 0, msg=ref_bc.stderr)
                self.assertEqual(internal_bc.stdout, ref_bc.stdout)


if __name__ == "__main__":
    unittest.main()
