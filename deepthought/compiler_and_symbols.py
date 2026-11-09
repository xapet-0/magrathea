"""
deepthought.compiler_and_symbols
Implements:
1. Official `cc -Wall -Wextra -Werror` compilation + Dual-Compiler Gate (`gcc` + `clang` in `--strict` mode).
2. Binary ELF/Mach-O symbol table verification via `nm -u` against `Allowed functions` (`white_list`).
   Uses `-fno-builtin` during `.o` inspection so `gcc`/`clang` never secretly replaces `printf("\n")`
   with `putchar` or `puts`, and permits compiler-emitted helpers when `printf` is allowed.
   Explicitly checks ABI intrinsics (`ABI_INTRINSICS`) and maps glibc internal symbols (`__ctype_b_loc`,
   `__isoc99_scanf`, `__libc_*`) back to canonical function names (`GRD-007`, `GRD-008`, `MUT-D07`).
3. Detection of forbidden `#include "*.c"` and forbidden `main()` in function exercises.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# NOTE: memcpy, memmove, memset, and *scanf are intentionally EXCLUDED from
# INTRINSIC_SYMBOLS so that calling them without permission is caught (GRD-007).
INTRINSIC_SYMBOLS = {
    "stdin", "stdout", "stderr", "__stdin", "__stdout", "__stderr",
    "___stack_chk_fail", "__stack_chk_fail", "_stack_chk_fail",
    "stack_chk_fail",
    "___stack_chk_guard", "__stack_chk_guard", "_stack_chk_guard",
    "stack_chk_guard",
    "__gmon_start__",
    "gmon_start__",
    "_ITM_deregisterTMCloneTable",
    "ITM_deregisterTMCloneTable",
    "_ITM_registerTMCloneTable",
    "ITM_registerTMCloneTable",
    "__cxa_finalize",
    "cxa_finalize",
    "__cxa_atexit",
    "cxa_atexit",
    "__libc_start_main",
    "libc_start_main",
    "dyld_stub_binder",
    "_GLOBAL_OFFSET_TABLE_",
    "GLOBAL_OFFSET_TABLE_",
    "mcount",
    "__fentry__",
    "fentry__",
    "___darwin_check_fd_set_overflow",
    "__darwin_check_fd_set_overflow",
    "__dso_handle",
    "__TMC_END__",
    "__data_start",
    "__bss_start",
    # GCC -ftrapv signed integer overflow runtime helpers
    "__addvsi3",
    "__subvsi3",
    "__mulvsi3",
    "__negvsi2",
    "__absvsi2",
    "__addvdi3",
    "__subvdi3",
    "__mulvdi3",
    "__negvdi2",
    "__absvdi2",
}

# Map glibc internal / macro-expanded symbols to canonical C function names (GRD-008, MUT-D07)
GLIBC_ALIAS_MAP = {
    "__ctype_b_loc": "isdigit",
    "__ctype_tolower_loc": "tolower",
    "__ctype_toupper_loc": "toupper",
    "__isoc99_scanf": "scanf",
    "isoc99_scanf": "scanf",
    "__isoc23_scanf": "scanf",
    "isoc23_scanf": "scanf",
    "__isoc99_fscanf": "fscanf",
    "isoc99_fscanf": "fscanf",
    "__isoc23_fscanf": "fscanf",
    "isoc23_fscanf": "fscanf",
    "__isoc99_sscanf": "sscanf",
    "isoc99_sscanf": "sscanf",
    "__isoc23_sscanf": "sscanf",
    "isoc23_sscanf": "sscanf",
    "__printf_chk": "printf",
    "__fprintf_chk": "fprintf",
    "__sprintf_chk": "sprintf",
    "__snprintf_chk": "snprintf",
    "__memcpy_chk": "memcpy",
    "__memmove_chk": "memmove",
    "__memset_chk": "memset",
    "__strcpy_chk": "strcpy",
    "__strncpy_chk": "strncpy",
    "__strcat_chk": "strcat",
    "__strncat_chk": "strncat",
    "__libc_malloc": "malloc",
    "__libc_free": "free",
    "__libc_calloc": "calloc",
    "__libc_realloc": "realloc",
    "__libc_write": "write",
    "__libc_read": "read",
    "__libc_open": "open",
    "__libc_close": "close",
    "__write": "write",
    "__read": "read",
    "__open": "open",
    "__close": "close",
    "__errno_location": "errno",
    "__error": "errno",
    "__xpg_basename": "basename",
    "xpg_basename": "basename",
}

FLAGS_DEFAULT = ["-Wall", "-Wextra", "-Werror"]
FLAGS_COMPILE_SAFE = ["-Wall", "-Wextra", "-Werror", "-Wno-builtin-declaration-mismatch", "-fno-builtin"]


@dataclass
class SymbolCheckResult:
    ok: bool
    undefined_symbols: list[str] = field(default_factory=list)
    forbidden_called: list[str] = field(default_factory=list)
    raw_nm_output: str = ""
    reason: str = ""


@dataclass
class CompileResult:
    ok: bool
    command: str
    returncode: int
    stdout: str
    stderr: str
    dual_compiler_warnings: list[str] = field(default_factory=list)


def _strip_c_comments_only(text: str) -> str:
    """Join C backslash-newline splices and strip comments without wiping #include directives or string literals."""
    joined = re.sub(r"\\\r?\n", "", text)
    pattern = re.compile(
        r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|(//.*?$|/\*.*?\*/)',
        re.DOTALL | re.MULTILINE,
    )
    return pattern.sub(lambda m: m.group(1) if m.group(1) else " ", joined)


def check_forbidden_c_includes(files: list[Path], submit_root: Optional[Path] = None, allowed_root: Optional[Path] = None) -> list[str]:
    """Reject any #include of a source file (.c/.cpp/.cc/.cxx/.inc), any absolute or parent-traversal #include escaping submit_root, or computed macro #include."""
    violations: list[str] = []
    inc_any_re = re.compile(r'^\s*#\s*include(?:_next)?\s*[<"]([^>"]+)[>"]', re.MULTILINE)
    inc_macro_re = re.compile(r'^\s*#\s*include(?:_next)?\s+([A-Za-z_]\w*)', re.MULTILINE)
    valid_suffixes = {".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".inc"}
    forbidden_src_exts = (".c", ".cpp", ".cc", ".cxx", ".inc")
    root_val = submit_root if submit_root is not None else allowed_root
    root_resolved = root_val.resolve() if root_val is not None else None
    for f in files:
        if f.suffix.lower() in valid_suffixes and f.exists():
            raw_txt = f.read_text(encoding="utf-8", errors="ignore")
            txt = _strip_c_comments_only(raw_txt)
            for m in inc_any_re.finditer(txt):
                target = m.group(1).strip()
                parts = [p for p in re.split(r'[/\\]+', target) if p]
                if target.lower().endswith(forbidden_src_exts):
                    violations.append(f"{f.name}: forbidden #include of source file '{target}'")
                if target.startswith(("/", "\\")):
                    violations.append(f"{f.name}: forbidden absolute #include '{target}'")
                elif ".." in parts:
                    if root_resolved is not None:
                        try:
                            resolved_cand = (f.resolve().parent / target).resolve()
                            if not resolved_cand.is_relative_to(root_resolved):
                                violations.append(f"{f.name}: forbidden parent-traversal #include '{target}'")
                        except (ValueError, RuntimeError):
                            violations.append(f"{f.name}: forbidden parent-traversal #include '{target}'")
                    else:
                        violations.append(f"{f.name}: forbidden parent-traversal #include '{target}'")
            for m in inc_macro_re.finditer(txt):
                violations.append(f"{f.name}: forbidden macro-computed #include '{m.group(1)}'")
    return violations


def strip_c_comments_and_strings(text: str) -> str:
    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE,
    )
    return pattern.sub(" ", text)


def has_main_definition(file_path: Path) -> bool:
    if not file_path.exists() or file_path.suffix != ".c":
        return False
    raw_txt = file_path.read_text(encoding="utf-8", errors="ignore")
    cleaned = strip_c_comments_and_strings(raw_txt)
    if bool(re.search(r"\bmain\s*\(", cleaned)):
        return True
    if "##" in cleaned or "#define" in cleaned:
        try:
            res = subprocess.run(
                ["cc", "-E", "-P", str(file_path)],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=2,
            )
            if res.returncode == 0:
                expanded = strip_c_comments_and_strings(res.stdout)
                if re.search(r"\bmain\s*\(", expanded):
                    return True
        except Exception:
            pass
    return False


def _normalize_symbol(raw_token: str) -> tuple[str, bool]:
    """
    Normalize an `nm` symbol token and determine if it is an explicit compiler/ABI intrinsic.
    Returns `(normalized_name, is_intrinsic)`.
    """
    raw_sym = raw_token.split("@", 1)[0]
    if (
        raw_sym in INTRINSIC_SYMBOLS
        or raw_sym.startswith("_GLOBAL_")
        or raw_sym.startswith("_ITM_")
        or raw_sym.startswith("dyld_")
    ):
        return raw_sym, True
    if raw_sym in GLIBC_ALIAS_MAP:
        return GLIBC_ALIAS_MAP[raw_sym], False
    # Strip at most one leading underscore for macOS Mach-O (`_write` -> `write`),
    # but do NOT strip double underscores unless in GLIBC_ALIAS_MAP or INTRINSIC_SYMBOLS.
    sym_name = raw_sym[1:] if (raw_sym.startswith("_") and not raw_sym.startswith("__")) else raw_sym
    if sym_name in INTRINSIC_SYMBOLS:
        return sym_name, True
    if sym_name in GLIBC_ALIAS_MAP:
        return GLIBC_ALIAS_MAP[sym_name], False
    return sym_name, False


def extract_defined_and_undefined_symbols(obj_files: list[Path]) -> tuple[set[str], set[str], str]:
    """Run `nm` on compiled `.o` files to extract defined symbols (T/t/D/B) and undefined external symbols (U)."""
    defined: set[str] = set()
    undefined: set[str] = set()
    raw_lines: list[str] = []

    if shutil.which("nm") is None:
        return defined, undefined, "nm not available"

    for obj in obj_files:
        proc = subprocess.run(["nm", str(obj)], capture_output=True, text=True, errors="replace")
        raw_lines.append(f"$> nm -u {obj.name}")
        for line in proc.stdout.splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            sym_type = parts[-2] if len(parts) >= 2 else ""
            sym_name, is_intrinsic = _normalize_symbol(parts[-1])
            if is_intrinsic:
                continue
            if sym_type == "U":
                raw_lines.append(f"                 U {sym_name}")
                undefined.add(sym_name)
            elif sym_type in {"T", "t", "D", "d", "B", "b", "R", "r"}:
                defined.add(sym_name)
    return defined, undefined, "\n".join(raw_lines)


def verify_symbol_whitelist(
    user_c_files: list[Path],
    allowed_functions: list[str] | None,
    *,
    work_dir: Path,
    include_dirs: list[Path] | None = None,
    strict_dual_compiler: bool = False,
) -> tuple[CompileResult, SymbolCheckResult]:
    for cfile in user_c_files:
        if cfile.suffix in {".c", ".h"} and cfile.exists():
            raw_code = cfile.read_text(encoding="utf-8", errors="replace")
            clean_code = strip_c_comments_and_strings(raw_code)
            if re.search(r"\b(__asm__|__asm|asm)\b", clean_code):
                return (
                    CompileResult(True, "", 0, "", ""),
                    SymbolCheckResult(
                        False,
                        reason="Cheating (-42): Inline assembly is strictly forbidden",
                    ),
                )

    inc_flags: list[str] = []
    for d in include_dirs or [work_dir]:
        inc_flags.extend(["-I", str(d)])

    obj_files: list[Path] = []
    cmds_run: list[str] = []
    dual_warnings: list[str] = []

    for cfile in user_c_files:
        if cfile.suffix != ".c":
            continue
        obj = work_dir / f"{cfile.stem}.o"
        cmd = [
            "cc",
            *FLAGS_COMPILE_SAFE,
            "-fno-builtin",
            "-fno-stack-protector",
            *inc_flags,
            "-c",
            str(cfile),
            "-o",
            str(obj),
        ]
        from .grader import _run_isolated
        cmds_run.append(" ".join(["cc", *FLAGS_DEFAULT, "-c", cfile.name, "-o", obj.name]))
        proc = _run_isolated(cmd, cwd=work_dir, timeout=5.0)
        if proc.returncode != 0:
            return (
                CompileResult(False, "\n".join(cmds_run), proc.returncode, proc.stdout, proc.stderr),
                SymbolCheckResult(False, reason="Does not compile"),
            )
        obj_files.append(obj)

        if strict_dual_compiler:
            for alt_cc in ["gcc", "clang"]:
                if not shutil.which(alt_cc):
                    dual_warnings.append(f"[Dual-Compiler Gate]: {alt_cc} not found in PATH — skipped")
                else:
                    cc_flags = [
                        f for f in FLAGS_COMPILE_SAFE
                        if not (alt_cc == "clang" and f == "-Wno-builtin-declaration-mismatch")
                        and not (alt_cc == "gcc" and f == "-Wno-unknown-warning-option")
                    ]
                    alt_proc = subprocess.run(
                        [alt_cc, *cc_flags, *inc_flags, "-fsyntax-only", str(cfile)],
                        cwd=work_dir,
                        capture_output=True,
                        text=True,
                        errors="replace",
                    )
                    if alt_proc.returncode != 0:
                        return (
                            CompileResult(
                                False,
                                f"{alt_cc} {' '.join(FLAGS_DEFAULT)} -c {cfile.name}",
                                alt_proc.returncode,
                                alt_proc.stdout,
                                f"[Dual-Compiler Gate: {alt_cc} rejected code under -Werror]\n{alt_proc.stderr}",
                            ),
                            SymbolCheckResult(False, reason=f"Does not compile under {alt_cc} -Werror"),
                        )

    compile_res = CompileResult(True, "\n".join(cmds_run), 0, "", "", dual_warnings)

    # Fail closed if nm is unavailable (GRD-006)
    if shutil.which("nm") is None:
        return (
            compile_res,
            SymbolCheckResult(
                ok=False,
                reason="Configuration Error: nm binary not available for symbol verification",
            ),
        )

    defined, undefined, raw_nm = extract_defined_and_undefined_symbols(obj_files)
    external_calls = sorted(undefined - defined - INTRINSIC_SYMBOLS)

    # Universal Anti-Cheat Gate: dlopen/dlsym dynamic resolution & __real_* linker bypass are strictly forbidden even if unrestricted
    cheat_symbols = {"dlopen", "dlsym", "dlvsym", "dlmopen"}
    cheating_hits = [sym for sym in external_calls if sym in cheat_symbols or sym.startswith("__real_")]
    if cheating_hits:
        return (
            compile_res,
            SymbolCheckResult(
                ok=False,
                undefined_symbols=external_calls,
                forbidden_called=cheating_hits,
                raw_nm_output=raw_nm,
                reason=f"Cheating (-42): Forbidden function(s) called: {', '.join(cheating_hits)} (Dynamic linking bypass detected)",
            ),
        )

    if allowed_functions is None or any(str(fn).lower() in {"anything", "all", "*"} for fn in allowed_functions):
        return compile_res, SymbolCheckResult(True, reason="Unrestricted")

    whitelist = {str(fn).strip().lstrip("_") for fn in allowed_functions if fn and str(fn).lower() != "none"}
    if "printf" in whitelist:
        whitelist.update({"putchar", "puts"})
    if "socket" in whitelist or "bind" in whitelist:
        whitelist.update({"htonl", "htons", "ntohl", "ntohs"})
    if "isspace" in whitelist or "isdigit" in whitelist:
        whitelist.update({"isdigit", "isspace"})
    if "strerror" in whitelist or "perror" in whitelist or "errno" in whitelist:
        whitelist.add("errno")

    forbidden_hits = [sym for sym in external_calls if sym not in whitelist]

    if forbidden_hits:
        return (
            compile_res,
            SymbolCheckResult(
                ok=False,
                undefined_symbols=external_calls,
                forbidden_called=forbidden_hits,
                raw_nm_output=raw_nm,
                reason=f"Cheating (-42): Forbidden function(s) called: {', '.join(forbidden_hits)} (Allowed: {', '.join(sorted(whitelist)) or 'None'})",
            ),
        )

    return (
        compile_res,
        SymbolCheckResult(
            ok=True,
            undefined_symbols=external_calls,
            forbidden_called=[],
            raw_nm_output=raw_nm,
            reason="OK",
        ),
    )
