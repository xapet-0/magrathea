"""
deepthought.makefile_and_repo
Enforces:
1. Official PDF & Norm v4.1 Section III.11 Makefile rules (not checked by norminette):
   - No wildcards (`*.c`, `*.o`, `$(wildcard ...)`) in Makefile.
   - Mandatory rules: `$(NAME)`, `all`, `clean`, `fclean`, `re` (`all` as default).
   - Must compile with `cc` and `-Wall -Wextra -Werror`.
   - Must NOT relink when `make` is run a second time (`No Relinking`).
2. Repository layout sanity check (detects beginner mistakes from real 1337 logs like `mkdir c00` inside repo root,
   or extra `.c`/`a.out`/`.o`/`.swp` files left at root or inside `exXX/`).
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MakefileAuditResult:
    ok: bool
    reason: str = ""
    steps_log: list[str] = field(default_factory=list)


def check_repo_root_mistakes(repo_dir: Path, module_id: str) -> list[str]:
    """Detect real-world 1337 student repo layout mistakes (like `mkdir c00` inside C00 repo)."""
    warnings: list[str] = []
    if not repo_dir.exists():
        return warnings
    nested_mod = repo_dir / module_id.lower()
    nested_mod_upper = repo_dir / module_id.upper()
    if nested_mod.is_dir() or nested_mod_upper.is_dir():
        bad_name = nested_mod.name if nested_mod.is_dir() else nested_mod_upper.name
        warnings.append(
            f"CRITICAL REPO STRUCTURE ERROR: Found subfolder '{bad_name}/' inside your repository! "
            f"In 1337/42 Vogsphere, ex00/, ex01/... MUST be at the root of the repository, NOT inside '{bad_name}/ex00/'!"
        )
    for item in repo_dir.iterdir():
        if item.name.startswith("."):
            continue
        if item.is_file() and (item.suffix in {".c", ".o", ".out", ".swp"} or item.name == "a.out"):
            warnings.append(
                f"EXTRA FILE AT REPO ROOT: '{item.name}' found outside exXX/ directory. "
                "Always remove stray files at the root of your repository before pushing!"
            )
    return warnings


def audit_makefile(
    work_dir: Path,
    *,
    expected_binary_or_lib: str | None = None,
    sources_to_create: dict[str, str] | None = None,
    timeout: int = 10,
) -> MakefileAuditResult:
    """Perform a full lifecycle audit of a student's Makefile per norm.en.pdf Section III.11 (page 16)."""
    steps: list[str] = []
    makefile = work_dir / "Makefile"
    if not makefile.exists():
        makefile = work_dir / "makefile"
    if not makefile.exists():
        return MakefileAuditResult(False, "Makefile is missing", ["Makefile not found in submission directory."])

    from .compiler_and_symbols import check_forbidden_c_includes
    from .grader import _run_isolated

    c_and_h = [p for p in work_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".c", ".h", ".cpp", ".hpp"}]
    inc_violations = check_forbidden_c_includes(c_and_h, allowed_root=work_dir)
    if inc_violations:
        return MakefileAuditResult(False, f"Cheating (-42): {inc_violations[0]}", inc_violations)

    content = makefile.read_text(encoding="utf-8", errors="ignore")

    # 1. Check forbidden wildcards (*.c, *.h, *.o, $(wildcard ...)) per norm.en.pdf III.11
    cleaned_lines = [
        line.split("#", 1)[0]
        for line in content.splitlines()
        if not line.strip().startswith("#")
    ]
    uncommented = "\n".join(cleaned_lines)
    if re.search(r"\$\(\s*wildcard\b|\$\(\s*shell\s+find\b|\*\.(?:c|h|o)\b", uncommented):
        return MakefileAuditResult(
            False,
            "Norm III.11 violation: Wildcards (*.c, *.h, *.o, $(wildcard)) are strictly forbidden in Makefile; all source files must be explicitly named.",
            steps,
        )

    # 2. Check mandatory targets exist (all, clean, fclean, re)
    for target in ["all", "clean", "fclean", "re"]:
        if not re.search(rf"^\s*{target}\s*:", uncommented, re.MULTILINE):
            return MakefileAuditResult(False, f"Missing mandatory Makefile rule: '{target}'", steps)

    # 3. Check compiler flags (-Wall -Wextra -Werror)
    for flag in ["-Wall", "-Wextra", "-Werror"]:
        if flag not in uncommented:
            return MakefileAuditResult(False, f"Missing mandatory compilation flag '{flag}' in Makefile", steps)

    # Populate dummy sources if testing standalone C09 ex01 Makefile
    if sources_to_create:
        for rel_path, file_txt in sources_to_create.items():
            p = work_dir / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.write_text(file_txt, encoding="utf-8")

    # 4. Run `make` (default rule must be `all` and build target)
    steps.append("$> make")
    p_make = _run_isolated(["make"], cwd=work_dir, timeout=float(timeout))
    steps.append((p_make.stdout + p_make.stderr).strip())
    if p_make.returncode != 0:
        return MakefileAuditResult(False, "`make` failed to build target", steps)

    if expected_binary_or_lib and not (work_dir / expected_binary_or_lib).exists():
        return MakefileAuditResult(
            False,
            f"`make` did not produce expected target '{expected_binary_or_lib}'",
            steps,
        )

    # 5. Check No Relinking: running `make` a second time must NOT recompile/relink
    target_path = (work_dir / expected_binary_or_lib) if expected_binary_or_lib else None
    mtime_before = target_path.stat().st_mtime_ns if (target_path and target_path.exists()) else None

    steps.append("$> make  # Checking for forbidden relinking")
    p_make2 = _run_isolated(["make"], cwd=work_dir, timeout=float(timeout))
    out2 = (p_make2.stdout + p_make2.stderr).strip()
    steps.append(out2)
    if any(cmd_tok in out2 for cmd_tok in ["cc ", "gcc ", "clang ", "ar "]):
        return MakefileAuditResult(
            False,
            "Norm III.11 violation: Makefile relinks when running `make` a second time!",
            steps,
        )
    if mtime_before is not None and target_path and target_path.exists():
        if target_path.stat().st_mtime_ns != mtime_before:
            return MakefileAuditResult(False, "Norm III.11 violation: Target binary/library timestamp changed on second `make` (Relinking)!", steps)

    # 6. Run `make clean` (must remove .o files and keep target binary/library)
    steps.append("$> make clean")
    p_clean = _run_isolated(["make", "clean"], cwd=work_dir, timeout=float(timeout))
    steps.append((p_clean.stdout + p_clean.stderr).strip())
    if p_clean.returncode != 0:
        return MakefileAuditResult(False, "`make clean` failed", steps)
    leftover_objs = list(work_dir.rglob("*.o"))
    if leftover_objs:
        return MakefileAuditResult(False, "`make clean` did not remove all .o object files", steps)
    if target_path and not target_path.exists():
        return MakefileAuditResult(False, "`make clean` wrongly deleted the target binary/library (only `fclean` should delete it)!", steps)

    # 7. Run `make fclean` (must remove target binary/library)
    steps.append("$> make fclean")
    p_fclean = _run_isolated(["make", "fclean"], cwd=work_dir, timeout=float(timeout))
    steps.append((p_fclean.stdout + p_fclean.stderr).strip())
    if p_fclean.returncode != 0:
        return MakefileAuditResult(False, "`make fclean` failed", steps)
    if target_path and target_path.exists():
        return MakefileAuditResult(False, f"`make fclean` did not remove '{expected_binary_or_lib}'", steps)

    # 8. Run `make re` (must rebuild target cleanly)
    steps.append("$> make re")
    p_re = _run_isolated(["make", "re"], cwd=work_dir, timeout=float(timeout))
    steps.append((p_re.stdout + p_re.stderr).strip())
    if p_re.returncode != 0 or (target_path and not target_path.exists()):
        return MakefileAuditResult(False, "`make re` failed to rebuild target", steps)

    return MakefileAuditResult(True, "OK", steps)
