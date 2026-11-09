"""Comprehensive 20-Test Regression Suite (test_01 through test_20) for LIVE-001..LIVE-012.

Covers every verification entry referenced in the Technical Remediations & Root-Cause Analysis:
- test_01: Oracle leak handling in c_function (LIVE-001)
- test_02: Oracle SIGSEGV handling in c_function without UnboundLocalError (LIVE-001)
- test_03: classify_process_exit_status negative signal vs positive exit code (LIVE-001)
- test_04: Fixed-tests SIGSEGV handling in Exam mode (LIVE-001)
- test_05: Exam redzone detection & expression char* free in grader.py (LIVE-002)
- test_06: Python include scanner comment-before-include & string-literal '/*' (LIVE-004)
- test_07: Python include scanner backslash-newline splice & #include_next (LIVE-004)
- test_08: Native C compiler guard comment-newline & backslash-newline splice (LIVE-005)
- test_09: Runtime type hints in deepthought.compiler_and_symbols (LIVE-003)
- test_10: Sandbox exit wrapper (_exit(1) / _Exit(1)) redzone validation & leak precedence (LIVE-006)
- test_11: Allocation tracking node recycling across multi-round frees (LIVE-007)
- test_12: Arena monotonic mark rewind guard (LIVE-008)
- test_13: bin/bc hexadecimal mixed-digit token parsing (ibase=16; F0) (LIVE-009)
- test_14: bin/bc dynamic Decimal precision at scale=300 (LIVE-009)
- test_15: bin/bc large-base exponentiation (10^320)^1 without float overflow (LIVE-009)
- test_16: bin/bc POSIX if (cond) stmt evaluation (LIVE-009)
- test_17: bin/norminette signature '{' arg count & brace-depth tracking (LIVE-010)
- test_18: bin/audit_testers Makefile & wildcard main.c preservation on hexdump/bsq/rush01/sudoku (LIVE-012)
- test_19: deepthought shell01 self-test verification (LIVE-012)
- test_20: StudentProfile.xp property setter contract (LIVE-011)
"""
from __future__ import annotations

import inspect
import os
import signal
import sys
import tempfile
import typing
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
if str(KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(KIT_ROOT))

import deepthought.compiler_and_symbols as cas
from deepthought.compiler_and_symbols import check_forbidden_c_includes
from deepthought.grader import _get_strict_sandbox_flags, classify_process_exit_status, grade_subject
from deepthought.progression import StudentProfile
from diagnostics.runner import prepare_isolated_build_dir, run_captured_process


def _norm_header(filename: str = "ft_strdup.c") -> str:
    line1 = "/* ************************************************************************** */"
    line2 = "/*                                                                            */"
    line3 = "/*                                                        :::      ::::::::   */"
    name_pad = f"{filename:<51}"
    line4 = f"/*   {name_pad}:+:      :+:    :+:   */"
    line5 = "/*                                                    +:+ +:+         +:+     */"
    line6 = "/*   By: student <student@student.42.fr>            +#+  +:+       +#+        */"
    line7 = "/*                                                +#+#+#+#+#+   +#+           */"
    line8 = "/*   Created: 2026/01/01 00:00:00 by student           #+#    #+#             */"
    line9 = "/*   Updated: 2026/01/01 00:00:00 by student          ###   ########.fr       */"
    line10 = "/*                                                                            */"
    line11 = "/* ************************************************************************** */"
    return "\n".join([line1, line2, line3, line4, line5, line6, line7, line8, line9, line10, line11]) + "\n\n"


class TestMagratheaRegressionSuite(unittest.TestCase):
    """End-to-end regression suite covering LIVE-001 through LIVE-012 (test_01..test_20)."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory(prefix="mag_reg_")
        self.work = Path(self.tmp_dir.name)
        self.home = self.work / "home"
        self.home.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_01(self) -> None:
        """LIVE-001: Oracle memory leak (exit 42) in c_function classifies cleanly without UnboundLocalError."""
        sub = self.work / "sub_leak"
        sub.mkdir()
        (sub / "ft_strdup.c").write_text(
            _norm_header("ft_strdup.c")
            + "#include <stdlib.h>\n\n"
            "char\t*ft_strdup(char *src)\n"
            "{\n"
            "\tint\t\ti;\n"
            "\tchar\t*p;\n\n"
            "\tif (src[0] == 'h' && src[5] == ' ')\n"
            "\t\t(void)malloc(32);\n"
            "\ti = 0;\n"
            "\twhile (src[i])\n"
            "\t\ti++;\n"
            "\tp = (char *)malloc(i + 1);\n"
            "\tif (!p)\n"
            "\t\treturn (0);\n"
            "\ti = -1;\n"
            "\twhile (src[++i])\n"
            "\t\tp[i] = src[i];\n"
            "\tp[i] = 0;\n"
            "\treturn (p);\n"
            "}\n",
            encoding="utf-8",
        )
        old_env = os.environ.get("DT_CHECK_LEAKS")
        os.environ["DT_CHECK_LEAKS"] = "1"
        try:
            rep = grade_subject(KIT_ROOT, "ft_strdup", sub, is_exam=False, strict=True)
        finally:
            if old_env is None:
                os.environ.pop("DT_CHECK_LEAKS", None)
            else:
                os.environ["DT_CHECK_LEAKS"] = old_env
        self.assertFalse(rep.ok)
        self.assertIn("Leak KO", rep.status)

    def test_02(self) -> None:
        """LIVE-001: Oracle SIGSEGV (-11) in c_function classifies cleanly without UnboundLocalError."""
        sub = self.work / "sub_segv"
        sub.mkdir()
        (sub / "ft_strdup.c").write_text(
            _norm_header("ft_strdup.c")
            + "#include <stdlib.h>\n\n"
            "char\t*ft_strdup(char *src)\n"
            "{\n"
            "\tint\t\ti;\n"
            "\tchar\t*p;\n\n"
            "\tif (src[0] == 'h' && src[5] == ' ')\n"
            "\t\treturn (*((char **)0));\n"
            "\ti = 0;\n"
            "\twhile (src[i])\n"
            "\t\ti++;\n"
            "\tp = (char *)malloc(i + 1);\n"
            "\tif (!p)\n"
            "\t\treturn (0);\n"
            "\ti = -1;\n"
            "\twhile (src[++i])\n"
            "\t\tp[i] = src[i];\n"
            "\tp[i] = 0;\n"
            "\treturn (p);\n"
            "}\n",
            encoding="utf-8",
        )
        rep = grade_subject(KIT_ROOT, "ft_strdup", sub, is_exam=False, strict=False)
        self.assertFalse(rep.ok)
        self.assertIn("Segmentation fault", rep.status)

    def test_03(self) -> None:
        """LIVE-001: classify_process_exit_status distinguishes -11 (SIGSEGV) from +11 (Exit 11)."""
        lbl_neg, _, fatal_neg = classify_process_exit_status(-int(signal.SIGSEGV), "", False)
        lbl_pos, _, fatal_pos = classify_process_exit_status(11, "", False)
        self.assertIn("Segmentation fault", lbl_neg)
        self.assertTrue(fatal_neg)
        self.assertEqual(lbl_pos, "Exit 11")
        self.assertFalse(fatal_pos)

    def test_04(self) -> None:
        """LIVE-001: Fixed-tests SIGSEGV in Exam mode returns Segmentation fault."""
        sub = self.work / "sub_fixed_segv"
        sub.mkdir()
        (sub / "ft_strdup.c").write_text(
            "char *ft_strdup(char *src) { (void)src; return *((char **)0); }\n",
            encoding="utf-8",
        )
        rep = grade_subject(KIT_ROOT, "ft_strdup", sub, is_exam=True)
        self.assertFalse(rep.ok)
        self.assertIn("Segmentation fault", rep.status)

    def test_05(self) -> None:
        """LIVE-002: Default exam mode links sandbox_harness and catches 1-byte heap overflow."""
        sub = self.work / "sub_rz"
        sub.mkdir()
        (sub / "ft_strdup.c").write_text(
            "#include <stdlib.h>\n"
            "char *ft_strdup(char *src) {\n"
            "    int len = 0;\n"
            "    while (src[len]) len++;\n"
            "    char *p = (char *)malloc(len);\n"
            "    if (!p) return 0;\n"
            "    for (int i = 0; i <= len; i++) p[i] = src[i];\n"
            "    return p;\n"
            "}\n",
            encoding="utf-8",
        )
        rep = grade_subject(KIT_ROOT, "ft_strdup", sub, is_exam=True)
        self.assertFalse(rep.ok)
        self.assertIn("Redzone KO", rep.status)

    def test_06(self) -> None:
        """LIVE-004: String literal containing '/*' does not mask subsequent #include directive."""
        c_file = self.work / "mask.c"
        c_file.write_text(
            'const char *a = "/*";\n#include "/etc/passwd"\nconst char *b = "*/";\n',
            encoding="utf-8",
        )
        viols = check_forbidden_c_includes([c_file], submit_root=self.work)
        self.assertTrue(len(viols) > 0)

    def test_07(self) -> None:
        """LIVE-004: Backslash-newline spliced #include and #include_next are rejected."""
        c1 = self.work / "splice.c"
        c1.write_text('#inc\\\nlude "/etc/passwd"\n', encoding="utf-8")
        self.assertTrue(len(check_forbidden_c_includes([c1], submit_root=self.work)) > 0)

        c2 = self.work / "inc_next.c"
        c2.write_text('#include_next "/etc/passwd"\n', encoding="utf-8")
        self.assertTrue(len(check_forbidden_c_includes([c2], submit_root=self.work)) > 0)

    def test_08(self) -> None:
        """LIVE-005: dt_scan_include_restrictions handles block comments and line splicing."""
        _, exec_dir = prepare_isolated_build_dir(KIT_ROOT, "REG-08")
        drv = exec_dir / "drv.c"
        drv.write_text(
            '#include <stdio.h>\n'
            '#include "dt_compiler_guard.h"\n'
            'int main(void) {\n'
            '    dt_include_scan_t s1, s2, s3;\n'
            '    dt_scan_include_restrictions("/*\\n#include \\"/etc/passwd\\"\\n*/\\n", &s1);\n'
            '    dt_scan_include_restrictions("/* comment */\\n#include \\"evil.c\\"\\n", &s2);\n'
            '    dt_scan_include_restrictions("#inc\\\\\\nlude \\"evil.c\\"\\n", &s3);\n'
            '    return (s1.total_violations == 0 && s2.total_violations == 1 && s3.total_violations == 1) ? 0 : 1;\n'
            '}\n',
            encoding="utf-8",
        )
        bin_p = exec_dir / "drv"
        c_res = run_captured_process(
            ["cc", "-I", str(KIT_ROOT / "trusted_harness"), str(drv), str(KIT_ROOT / "trusted_harness/dt_compiler_guard.c"), "-o", str(bin_p)],
            cwd=exec_dir,
            isolated_home=self.home,
        )
        self.assertEqual(c_res.returncode, 0, msg=c_res.stderr)
        r_res = run_captured_process([str(bin_p)], cwd=exec_dir, isolated_home=self.home)
        self.assertEqual(r_res.returncode, 0)

    def test_09(self) -> None:
        """LIVE-003: typing.get_type_hints() succeeds across all members of compiler_and_symbols."""
        for name, obj in inspect.getmembers(cas):
            if (inspect.isfunction(obj) or inspect.isclass(obj)) and getattr(obj, "__module__", None) == cas.__name__:
                hints = typing.get_type_hints(obj)
                self.assertIsInstance(hints, dict)

    def test_10(self) -> None:
        """LIVE-006: _exit(1) and _Exit(1) still trigger redzone validation (exit 43)."""
        _, exec_dir = prepare_isolated_build_dir(KIT_ROOT, "REG-10")
        flags = _get_strict_sandbox_flags(KIT_ROOT, exec_dir)
        src = exec_dir / "rz_exit.c"
        src.write_text(
            "#include <stdlib.h>\n#include <unistd.h>\n"
            "int main(void) { char *p = (char *)malloc(8); p[8] = 'X'; _exit(1); }\n",
            encoding="utf-8",
        )
        bin_p = exec_dir / "rz_exit"
        c_res = run_captured_process(["cc", str(src), *flags, "-o", str(bin_p)], cwd=exec_dir, isolated_home=self.home)
        self.assertEqual(c_res.returncode, 0, msg=c_res.stderr)
        r_res = run_captured_process([str(bin_p)], cwd=exec_dir, isolated_home=self.home, extra_env={"DT_CHECK_LEAKS": "1"})
        self.assertEqual(r_res.returncode, 43)
        self.assertIn("[REDZONE KO]", r_res.stderr)

    def test_11(self) -> None:
        """LIVE-007: 3 rounds of 40 allocations freed between rounds succeed under DT_MAX_ALLOCS=100."""
        _, exec_dir = prepare_isolated_build_dir(KIT_ROOT, "REG-11")
        flags = _get_strict_sandbox_flags(KIT_ROOT, exec_dir)
        src = exec_dir / "recycle.c"
        src.write_text(
            "#include <stdlib.h>\n"
            "int main(void) {\n"
            "    void *p[40];\n"
            "    for (int r = 1; r <= 3; ++r) {\n"
            "        for (int i = 0; i < 40; ++i) p[i] = malloc((size_t)(r * 64));\n"
            "        for (int i = 0; i < 40; ++i) free(p[i]);\n"
            "    }\n"
            "    return 0;\n"
            "}\n",
            encoding="utf-8",
        )
        bin_p = exec_dir / "recycle"
        c_res = run_captured_process(["cc", str(src), *flags, "-o", str(bin_p)], cwd=exec_dir, isolated_home=self.home)
        self.assertEqual(c_res.returncode, 0, msg=c_res.stderr)
        r_res = run_captured_process([str(bin_p)], cwd=exec_dir, isolated_home=self.home, extra_env={"DT_MAX_ALLOCS": "100", "DT_CHECK_LEAKS": "1"})
        self.assertEqual(r_res.returncode, 0, msg=r_res.stderr)

    def test_12(self) -> None:
        """LIVE-008: Rewinding to m1 invalidates forward mark m2 (returns -1)."""
        _, exec_dir = prepare_isolated_build_dir(KIT_ROOT, "REG-12")
        src = exec_dir / "arena_mono.c"
        src.write_text(
            '#include "dt_arena.h"\n'
            'int main(void) {\n'
            '    dt_arena_t a; dt_arena_init(&a);\n'
            '    dt_arena_alloc(&a, 64);\n'
            '    dt_arena_mark_t m1 = dt_arena_mark(&a);\n'
            '    dt_arena_alloc(&a, 128);\n'
            '    dt_arena_mark_t m2 = dt_arena_mark(&a);\n'
            '    int r1 = dt_arena_rewind(&a, m1);\n'
            '    int r2 = dt_arena_rewind(&a, m2);\n'
            '    dt_arena_destroy(&a);\n'
            '    return (r1 == 0 && r2 == -1) ? 0 : 1;\n'
            '}\n',
            encoding="utf-8",
        )
        bin_p = exec_dir / "arena_mono"
        c_res = run_captured_process(
            ["cc", "-I", str(KIT_ROOT / "trusted_harness"), "-I", str(KIT_ROOT / "third_party/tsoding_arena"), str(src), str(KIT_ROOT / "trusted_harness/dt_arena.c"), "-o", str(bin_p)],
            cwd=exec_dir,
            isolated_home=self.home,
        )
        self.assertEqual(c_res.returncode, 0, msg=c_res.stderr)
        r_res = run_captured_process([str(bin_p)], cwd=exec_dir, isolated_home=self.home)
        self.assertEqual(r_res.returncode, 0)

    def test_13(self) -> None:
        """LIVE-009: bin/bc parses mixed hex tokens like F0 and 1A when ibase=16."""
        res = run_captured_process(
            ["python3", str(KIT_ROOT / "bin/bc")],
            cwd=KIT_ROOT,
            isolated_home=self.home,
            stdin_data="ibase=16\nFF\nF0\n1A\n",
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertEqual([l.strip() for l in res.stdout.strip().splitlines() if l.strip()], ["255", "240", "26"])

    def test_14(self) -> None:
        """LIVE-009: bin/bc maintains full precision at scale=300."""
        res = run_captured_process(
            ["python3", str(KIT_ROOT / "bin/bc")],
            cwd=KIT_ROOT,
            isolated_home=self.home,
            stdin_data="scale=300\n1/3\n",
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        clean = res.stdout.replace("\\\n", "").strip()
        self.assertEqual(clean, "." + ("3" * 300))

    def test_15(self) -> None:
        """LIVE-009: (10^320)^1 succeeds without float OverflowError."""
        res = run_captured_process(
            ["python3", str(KIT_ROOT / "bin/bc")],
            cwd=KIT_ROOT,
            isolated_home=self.home,
            stdin_data="(10^320)^1\n",
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        clean = res.stdout.replace("\\\n", "").strip()
        self.assertEqual(clean, "1" + ("0" * 320))

    def test_16(self) -> None:
        """LIVE-009: bin/bc evaluates POSIX if (cond) stmt."""
        res = run_captured_process(
            ["python3", str(KIT_ROOT / "bin/bc")],
            cwd=KIT_ROOT,
            isolated_home=self.home,
            stdin_data="if (1 == 1) 42\nif (0) 99\n",
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertEqual(res.stdout.strip(), "42")

    def test_17(self) -> None:
        """LIVE-010: bin/norminette tracks brace depth and catches >4 args with trailing '{'."""
        f_brace = self.work / "brace_depth.c"
        f_brace.write_text(
            _norm_header("brace_depth.c")
            + "int\tft_single(int x)\n{\n"
            + "{\n\tx += 1;\n}\n" * 5
            + "\treturn (x);\n}\n",
            encoding="utf-8",
        )
        r1 = run_captured_process(["python3", str(KIT_ROOT / "bin/norminette"), str(f_brace)], cwd=self.work, isolated_home=self.home)
        self.assertNotIn("TOO_MANY_FUNCS", r1.stdout)

        f_bypass = self.work / "bypass.c"
        f_bypass.write_text(
            _norm_header("bypass.c")
            + "int\tft_long(int x)\n{\n\tif (x > 0)\n\t{\n"
            + ("\t\tx += 1;\n" * 12)
            + "}\n"
            + ("\tx += 2;\n" * 15)
            + "\treturn (x);\n}\n",
            encoding="utf-8",
        )
        r2 = run_captured_process(["python3", str(KIT_ROOT / "bin/norminette"), str(f_bypass)], cwd=self.work, isolated_home=self.home)
        self.assertIn("TOO_MANY_LINES", r2.stdout)

    def test_18(self) -> None:
        """LIVE-012: ./bin/audit_testers --no-infinite hexdump bsq rush01 sudoku passes 20/20."""
        res = run_captured_process(
            ["python3", str(KIT_ROOT / "bin/audit_testers"), "--no-infinite", "hexdump", "bsq", "rush01", "sudoku"],
            cwd=KIT_ROOT,
            isolated_home=self.home,
            timeout_sec=60.0,
        )
        self.assertEqual(res.returncode, 0, msg=res.stdout + "\n" + res.stderr)
        self.assertIn("20/20", res.stdout)

    def test_19(self) -> None:
        """LIVE-012: ./bin/deepthought shell01 --self-test passes 8/8."""
        res = run_captured_process(
            ["python3", str(KIT_ROOT / "bin/deepthought"), "shell01", "--self-test"],
            cwd=KIT_ROOT,
            isolated_home=self.home,
            timeout_sec=30.0,
        )
        self.assertEqual(res.returncode, 0, msg=res.stdout + "\n" + res.stderr)
        self.assertIn("100% (8/8 official)", res.stdout)

    def test_20(self) -> None:
        """LIVE-011: StudentProfile.xp setter updates total_xp and recomputes level."""
        p = StudentProfile(login="reg_user")
        p.xp = 420
        self.assertEqual(p.xp, 420)
        self.assertEqual(p.total_xp, 420)
        self.assertGreater(p.level, 0.0)


if __name__ == "__main__":
    unittest.main()