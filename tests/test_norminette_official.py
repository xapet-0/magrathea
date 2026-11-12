"""The norm check is the official 42 norminette, shipped in third_party/norminette/.

What these tests pin:
- the shipped copy is the wheel published by 42school, file for file (RECORD sha256)
- bin/norminette is that tool, and the grader's "Norme error" comes from it
- it rejects what the former built-in checker let through (spaces for tabs, 'if(c)', ...)
- nothing in the student's directory or environment can stand in for the tool
- when the official tool cannot run (Python older than 3.10), the built-in checker is used and
  every trace says so
- every Piscine reference solution, and every file 'init' writes, passes the official norm;
  run this file after `python3 third_party/update_norminette.py <version>`
- a subject that names '-R CheckDefine' (C 08 macros) is graded with that rule

Run with: python3 tests/test_norminette_official.py
"""
from __future__ import annotations

import base64
import hashlib
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
NORMINETTE = KIT_ROOT / "bin" / "norminette"
MOULINETTE = KIT_ROOT / "bin" / "moulinette"
SHIPPED = KIT_ROOT / "third_party" / "norminette"
if str(KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(KIT_ROOT))

import yaml  # noqa: E402  (the kit's own pure-Python copy)


def _load(path: Path, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


norm = _load(NORMINETTE, "norminette_under_test")
moul = _load(MOULINETTE, "moulinette_for_norm_test")
OFFICIAL_RUNS = norm.official_command()[0] is not None

HEADER = moul.build_42_header("sample.c", login="tester")
CLEAN_C = HEADER + "\n#include <unistd.h>\n\nvoid\tft_putchar(char c)\n{\n\twrite(1, &c, 1);\n}\n"
# Three faults the former built-in checker accepted: a space before the function name, spaces for
# the indentation, no space after 'if'.
SLOPPY_C = HEADER + "\n#include <unistd.h>\n\nvoid ft_putchar(char c)\n{\n    if(c)\n        write(1, &c, 1);\n}\n"


class ShippedCopyTest(unittest.TestCase):
    def test_shipped_copy_is_the_published_wheel_file_for_file(self) -> None:
        infos = sorted(SHIPPED.glob("norminette-*.dist-info"))
        self.assertEqual(len(infos), 1, "exactly one norminette version is shipped")
        self.assertIn(f"version : {norm.official_version()}", (SHIPPED / "SOURCE.txt").read_text(encoding="utf-8"))
        self.assertTrue((infos[0] / "licenses" / "LICENSE").is_file(), "the MIT licence travels with the code")
        checked = 0
        for row in (infos[0] / "RECORD").read_text(encoding="utf-8").splitlines():
            name, digest, _size = row.rsplit(",", 2)
            if not digest:
                continue
            algo, _, expected = digest.partition("=")
            self.assertEqual(algo, "sha256", name)
            got = base64.urlsafe_b64encode(hashlib.sha256((SHIPPED / name).read_bytes()).digest()).rstrip(b"=").decode()
            self.assertEqual(got, expected, f"{name} differs from the published wheel")
            checked += 1
        self.assertGreater(checked, 50)

    def test_falls_back_to_the_builtin_checker_when_python_is_too_old(self) -> None:
        saved_min, saved_cache = norm.OFFICIAL_MIN_PYTHON, list(norm._PYTHON_FOR_OFFICIAL)
        try:
            norm.OFFICIAL_MIN_PYTHON = (99, 0)
            norm._PYTHON_FOR_OFFICIAL.clear()
            cmd, why = norm.official_command()
            self.assertIsNone(cmd)
            self.assertIn("Python 99.0", why)
            self.assertIsNone(norm.run_official([Path("whatever.c")]))
        finally:
            norm.OFFICIAL_MIN_PYTHON = saved_min
            norm._PYTHON_FOR_OFFICIAL[:] = saved_cache

    def test_subject_that_names_checkdefine_is_graded_with_it(self) -> None:
        named = []
        for subject in sorted((KIT_ROOT / "subjects" / "piscine").glob("*/*/subject.en.txt")):
            if "-R CheckDefine" in subject.read_text(encoding="utf-8", errors="replace"):
                meta = yaml.safe_load((subject.parent / "meta.yml").read_text(encoding="utf-8"))
                self.assertEqual(meta.get("norminette_rule"), "CheckDefine", subject.parent.name)
                named.append(subject.parent.name)
        self.assertIn("ft_abs.h", named)


@unittest.skipUnless(OFFICIAL_RUNS, f"official norminette cannot run here: {norm.official_command()[1]}")
class OfficialNorminetteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="norminette_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()

    def env(self, **extra: str) -> dict[str, str]:
        env = dict(os.environ, HOME=str(self.home), NO_COLOR="1", DT_SKIP_HOME_SYMLINKS="1")
        for key in ("MAGRATHEA_NORMINETTE", "FORCE_COLOR", "FT_STUDENT_PROFILE", "PYTHONPATH"):
            env.pop(key, None)
        env.update(extra)
        return env

    def run_tool(self, tool: Path, *argv: str, cwd: Path | None = None, **extra_env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(tool), *argv], cwd=str(cwd or self.tmp), env=self.env(**extra_env),
            capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL,
        )

    def write(self, name: str, text: str) -> Path:
        path = self.tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    # ------------------------------------------------------------------ the command
    def test_bin_norminette_is_the_official_tool(self) -> None:
        proc = self.run_tool(NORMINETTE, "--version")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.startswith(f"norminette {norm.official_version()},"), proc.stdout)

    def test_official_rejects_what_the_builtin_checker_accepts(self) -> None:
        clean, sloppy = self.write("clean.c", CLEAN_C), self.write("sloppy.c", SLOPPY_C)
        self.assertEqual(self.run_tool(NORMINETTE, str(clean)).returncode, 0)
        official = self.run_tool(NORMINETTE, str(sloppy))
        self.assertEqual(official.returncode, 1, official.stdout)
        for rule in ("SPACE_BEFORE_FUNC", "SPACE_REPLACE_TAB", "SPACE_AFTER_KW"):
            self.assertIn(rule, official.stdout)
        builtin = self.run_tool(NORMINETTE, str(sloppy), MAGRATHEA_NORMINETTE="builtin")
        self.assertEqual(builtin.returncode, 0, builtin.stdout)
        self.assertIn("built-in checker", builtin.stderr)

    def test_student_directory_and_environment_cannot_stand_in_for_the_tool(self) -> None:
        self.write("clean.c", CLEAN_C)
        self.write("norminette.py", "print('clean.c: OK!  (not the real tool)')\n")
        self.write("norminette/__init__.py", "raise SystemExit('hijacked')\n")
        self.write("norminette/__main__.py", "print('hijacked')\n")
        proc = self.run_tool(NORMINETTE, "clean.c", cwd=self.tmp, PYTHONPATH=str(self.tmp))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout.strip(), "clean.c: OK!")

    # ------------------------------------------------------------------ the grader
    def test_grader_norm_verdict_is_the_official_one(self) -> None:
        turnin = self.tmp / "turnin"
        turnin.mkdir()
        (turnin / "ft_putchar.c").write_text(SLOPPY_C.replace("    if(c)\n        write", "    write"), encoding="utf-8")
        ledger = str(self.tmp / "ledger.json")
        official = self.run_tool(MOULINETTE, "ft_putchar", "--dir", str(turnin), "--xp-ledger", ledger, cwd=KIT_ROOT)
        self.assertEqual(official.returncode, 1, official.stdout)
        self.assertIn("Norme error", official.stdout)
        self.assertIn("SPACE_REPLACE_TAB", official.stdout)
        self.assertNotIn("built-in checker", official.stdout)
        builtin = self.run_tool(
            MOULINETTE, "ft_putchar", "--dir", str(turnin), "--xp-ledger", ledger, cwd=KIT_ROOT, MAGRATHEA_NORMINETTE="builtin",
        )
        self.assertEqual(builtin.returncode, 0, builtin.stdout)
        self.assertIn("built-in checker, a part of the Norm only", builtin.stdout)

    def test_macro_header_passes_with_the_rule_its_subject_names(self) -> None:
        header = KIT_ROOT / "corrections" / "piscine" / "c08" / "ft_abs.h" / "ft_abs.h"
        plain = norm.run_official([header])
        self.assertIsNotNone(plain)
        self.assertFalse(plain[0], "a macro with arguments is refused without -R CheckDefine")
        self.assertEqual(norm.run_official([header], rule="CheckDefine"), (True, "ft_abs.h: OK!"))
        proc = self.run_tool(MOULINETTE, "piscine/c08/ft_abs.h", "--self-test", "--json", cwd=KIT_ROOT)
        self.assertIn('"passed": true', proc.stdout, proc.stdout + proc.stderr)

    # ------------------------------------------------------------------ what the kit itself ships
    def test_every_piscine_reference_solution_passes_the_official_norm(self) -> None:
        by_rule: dict[str, list[Path]] = {}
        for meta_file in sorted((KIT_ROOT / "subjects" / "piscine").glob("*/*/meta.yml")):
            meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
            reference = KIT_ROOT / "corrections" / "piscine" / meta_file.parent.parent.name / meta_file.parent.name
            sources = [p for p in sorted(reference.rglob("*")) if p.suffix in {".c", ".h"} and p.is_file()]
            by_rule.setdefault(str(meta.get("norminette_rule") or "CheckForbiddenSourceHeader"), []).extend(sources)
        self.assertGreater(sum(len(v) for v in by_rule.values()), 150)
        for rule, sources in by_rule.items():
            ok, out = norm.run_official(sources, rule=rule)
            failing = [line for line in out.splitlines() if "Error" in line]
            self.assertTrue(ok, f"-R {rule}:\n" + "\n".join(failing[:20]))

    def test_files_written_by_init_pass_the_official_norm(self) -> None:
        stubs: list[Path] = []
        for meta_file in sorted((KIT_ROOT / "subjects" / "piscine").glob("*/*/meta.yml")):
            meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
            proto = str(meta.get("prototype") or "")
            if meta.get("type") != "c_function" or not proto or "main(" in proto or "(" not in proto:
                continue
            name = f"{meta_file.parent.parent.name}_{meta_file.parent.name}.c"
            # A login longer than the header has room for must not push a line past 80 columns.
            text = moul.build_42_header(name, login="averyveryverylonglogin") + "\n" + moul.norm_function_stubs(proto)
            stubs.append(self.write(f"stubs/{name}", text))
        self.assertGreater(len(stubs), 80)
        ok, out = norm.run_official(stubs)
        self.assertTrue(ok, "\n".join(line for line in out.splitlines() if "Error" in line)[:2000])
        two = moul.norm_function_stubs("int match(char *s1, char *s2); int nmatch(char *s1, char *s2);")
        self.assertEqual(two, "int\tmatch(char *s1, char *s2)\n{\n}\n\nint\tnmatch(char *s1, char *s2)\n{\n}\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
