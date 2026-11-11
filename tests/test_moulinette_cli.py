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

Run with: python3 tests/test_moulinette_cli.py
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
