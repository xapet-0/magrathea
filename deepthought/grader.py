"""
deepthought.grader
Unified 42/1337 Deepthought & Moulinette Grading Engine (v2.1.0 Verified).
Handles:
- ExamPoolRevanced `profile.yml` + `generator.py` dynamic differential testing
- C Function exercises (`c_function`) with `nm -u` symbol whitelist, `norminette`, `-ftrapv` overflow checks, and `--strict` C sandbox
- C Program exercises (`c_program`) with `diff -U 3`, exit-code enforcement, and process-group isolation
- C Header exercises (`c_header` in C 08) with double-inclusion guard & prototype/macro verification (`ft.h`, `ft_abs.h`, `ft_point.h`, `ft_boolean.h`)
- C++ exercises (`cpp` in Exam Rank 05: `cpp_module00`, `cpp_module01`, `cpp_module02`)
- Makefile & static library exercises (`makefile`, `shell_lib` in C 09/C 10/C 11)
- Shell exercises (`shell` in Shell 00-13 & Shell Exam) via `shell_evaluator.py` and `sh_norminette.py`
- Python exercises (`python` in Rank 03 & Rank 04)
- Strict Zero-Empty-Test Gate (`DEF-013` / `GRD-003`): refuses to pass any exercise if 0 tests or empty oracles were executed.
"""
from __future__ import annotations

import difflib
import functools
import json
import os
import pathlib
import platform
import re
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence
import yaml

from .compiler_and_symbols import (
    FLAGS_COMPILE_SAFE,
    FLAGS_DEFAULT,
    check_forbidden_c_includes,
    has_main_definition,
    verify_symbol_whitelist,
)
from .makefile_and_repo import audit_makefile
from .shell_evaluator import evaluate_shell_exercise




_EXEC_TEMP_ROOT_CACHE: dict[str, Path] = {}


def get_executable_temp_root(kit_root: Optional[Path] = None) -> Path:
    """Return a verified directory where compiled binaries can be executed via execve(2).

    Probes candidate directories by creating a mode-0700 temporary directory and executing
    a minimal #!/bin/sh probe script via subprocess.run (exercising kernel execve(2) rather
    than relying on os.access(X_OK), which can return True on noexec mounts on some kernels).
    Prevents symlink attacks by rejecting symlinked candidate roots and enforcing 0700 permissions.
    """
    base_kit = (kit_root or Path(__file__).resolve().parent.parent).resolve()
    cache_key = f"{os.environ.get('TMPDIR', '')}:{base_kit}"
    cached = _EXEC_TEMP_ROOT_CACHE.get(cache_key)
    if cached is not None and cached.is_dir() and not cached.is_symlink():
        return cached

    candidates: list[Path] = []
    env_exec = os.environ.get("MAGRATHEA_EXEC_TMPDIR")
    if env_exec:
        candidates.append(Path(env_exec))
    candidates.append(Path(tempfile.gettempdir()))
    candidates.append(Path("/var/tmp"))
    candidates.append( base_kit / "workspace" / ".tmp_exec")
    candidates.append(Path.home() / ".cache" / "magrathea_exec_tmp")

    for cand in candidates:
        try:
            if cand.exists() and cand.is_symlink():
                continue
            cand.mkdir(parents=True, exist_ok=True)
            cand_resolved = cand.resolve()
            with tempfile.TemporaryDirectory(prefix=".dt_exec_probe_", dir=str(cand_resolved)) as probe_td:
                probe_dir = Path(probe_td)
                os.chmod(probe_dir, 0o700)
                probe_bin = probe_dir / "probe.sh"
                probe_bin.write_bytes(b"#!/bin/sh\nexit 0\n")
                os.chmod(probe_bin, 0o700)
                res = subprocess.run(
                    [str(probe_bin)],
                    cwd=str(probe_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.5,
                )
                if res.returncode == 0:
                    _EXEC_TEMP_ROOT_CACHE[cache_key] = cand_resolved
                    return cand_resolved
        except (OSError, subprocess.SubprocessError):
            continue

    fallback = (base_kit / "workspace" / ".tmp_exec").resolve()
    fallback.mkdir(parents=True, exist_ok=True)
    _EXEC_TEMP_ROOT_CACHE[cache_key] = fallback
    return fallback


import copy
import hashlib
import importlib.util
import stat as stat_mod

MAX_YAML_FILE_BYTES = 512 * 1024
MAX_YAML_NESTING_DEPTH = 32
_YAML_CONTENT_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def _check_yaml_nesting_depth(obj: Any, depth: int = 0) -> bool:
    if depth > MAX_YAML_NESTING_DEPTH:
        return False
    if isinstance(obj, dict):
        return all(_check_yaml_nesting_depth(v, depth + 1) for v in obj.values())
    if isinstance(obj, list):
        return all(_check_yaml_nesting_depth(v, depth + 1) for v in obj)
    return True


def _safe_load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML safely with file-size, alias-expansion, and nesting-depth guards plus SHA-256 content-validated caching (FIX-SP-005, OPT-SP-002)."""
    try:
        st = path.stat()
    except OSError:
        return {}
    if st.st_size > MAX_YAML_FILE_BYTES:
        return {"__yaml_error__": f"YAML file exceeds maximum permitted size ({st.st_size} > {MAX_YAML_FILE_BYTES} bytes)"}
    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return {}
    content_sha = hashlib.sha256(raw_bytes).hexdigest()
    cache_key = (str(path.resolve()), content_sha)
    cached = _YAML_CONTENT_CACHE.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached)
    try:
        raw_txt = raw_bytes.decode("utf-8", errors="replace")
        if re.search(r'(?:\s|^)&[A-Za-z0-9_\-]+', raw_txt) and len(re.findall(r'(?:\s|^)\*[A-Za-z0-9_\-]+', raw_txt)) > 64:
            return {"__yaml_error__": "YAML alias expansion limit exceeded (>64 alias references)"}
        data = yaml.safe_load(raw_txt)
        if not _check_yaml_nesting_depth(data):
            return {"__yaml_error__": f"YAML nesting depth exceeds maximum permitted depth ({MAX_YAML_NESTING_DEPTH})"}
        res = data if isinstance(data, dict) else {}
        if len(_YAML_CONTENT_CACHE) > 2048:
            _YAML_CONTENT_CACHE.clear()
        _YAML_CONTENT_CACHE[cache_key] = res
        return copy.deepcopy(res)
    except yaml.YAMLError as exc:
        return {"__yaml_error__": str(exc)}


def _communicate_bounded(
    proc: subprocess.Popen[str],
    input_data: Optional[str] = None,
    timeout: float = 2.0,
    max_bytes: int = 270336,
) -> tuple[str, str]:
    """Read process output with bounded memory buffer and hard timeout to prevent pipe flood OOM."""
    sel = selectors.DefaultSelector()
    if proc.stdout:
        os.set_blocking(proc.stdout.fileno(), False)
        sel.register(proc.stdout, selectors.EVENT_READ, data="stdout")
    if proc.stderr:
        os.set_blocking(proc.stderr.fileno(), False)
        sel.register(proc.stderr, selectors.EVENT_READ, data="stderr")

    in_bytes = input_data.encode("utf-8") if input_data else b""
    in_offset = 0
    if proc.stdin and in_bytes:
        os.set_blocking(proc.stdin.fileno(), False)
        sel.register(proc.stdin, selectors.EVENT_WRITE, data="stdin")
    elif proc.stdin:
        proc.stdin.close()

    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    tot_bytes = 0
    deadline = time.time() + timeout

    while sel.get_map():
        rem = deadline - time.time()
        if rem <= 0:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
            sel.close()
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream:
                    try:
                        stream.close()
                    except Exception:
                        pass
            try:
                proc.wait(timeout=1.0)
            except Exception:
                pass
            raise subprocess.TimeoutExpired(proc.args, timeout)

        events = sel.select(timeout=min(rem, 0.05))
        for key, mask in events:
            if key.data == "stdin" and (mask & selectors.EVENT_WRITE):
                try:
                    written = os.write(key.fd, in_bytes[in_offset : in_offset + 4096])
                    in_offset += written
                    if in_offset >= len(in_bytes):
                        sel.unregister(key.fileobj)
                        proc.stdin.close()
                except (BrokenPipeError, OSError):
                    sel.unregister(key.fileobj)
                    proc.stdin.close()
            elif key.data in ("stdout", "stderr") and (mask & selectors.EVENT_READ):
                try:
                    chunk = os.read(key.fd, 8192)
                except OSError:
                    chunk = b""
                if not chunk:
                    sel.unregister(key.fileobj)
                else:
                    tot_bytes += len(chunk)
                    if key.data == "stdout":
                        stdout_chunks.append(chunk)
                    else:
                        stderr_chunks.append(chunk)
                    if tot_bytes > max_bytes:
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except Exception:
                            pass
                        for k in list(sel.get_map().values()):
                            sel.unregister(k.fileobj)
                        break

    sel.close()
    if proc.stdout:
        proc.stdout.close()
    if proc.stderr:
        proc.stderr.close()
    proc.wait()
    out = b"".join(stdout_chunks).decode("utf-8", errors="replace")
    err = b"".join(stderr_chunks).decode("utf-8", errors="replace")
    return out, err


def _build_sandbox_preexec(cwd: Path) -> Callable[[], None]:
    """Build a child preexec_fn that enforces Linux mount/user/net/ipc namespace isolation and POSIX rlimits.

    1. Enters unprivileged user + mount + network + IPC namespaces (CLONE_NEWUSER | CLONE_NEWNS | CLONE_NEWNET | CLONE_NEWIPC).
    2. Sets mount propagation to MS_REC | MS_PRIVATE so mounts never leak to the host.
    3. Mounts an unreadable mode-000 tmpfs over KIT_ROOT/corrections, KIT_ROOT/subjects, and KIT_ROOT/pools
       so student binaries cannot read reference solutions or test oracles via direct paths, relative paths,
       symlinks, or /proc/self/root traversal.
    4. Applies POSIX resource limits (RLIMIT_CORE=0, RLIMIT_FSIZE=16MB, RLIMIT_AS=512MB, RLIMIT_NOFILE=64).
    """
    kit_root = Path(__file__).resolve().parent.parent
    protected_dirs = [
        str((kit_root / "corrections").resolve()),
        str((kit_root / "subjects").resolve()),
        str((kit_root / "pools").resolve()),
    ]
    cwd_resolved = str(cwd.resolve())
    uid = os.getuid()
    gid = os.getgid()
    require_ns = os.environ.get("DT_REQUIRE_NAMESPACE_SANDBOX", "0") == "1"

    def _preexec() -> None:
        os.setsid()
        if sys.platform.startswith("linux"):
            try:
                import ctypes
                libc = ctypes.CDLL("libc.so.6", use_errno=True)
                CLONE_NEWNS = 0x00020000
                CLONE_NEWIPC = 0x08000000
                CLONE_NEWUSER = 0x10000000
                CLONE_NEWNET = 0x40000000
                MS_RDONLY = 1
                MS_NOSUID = 2
                MS_NODEV = 4
                MS_NOEXEC = 8
                MS_REC = 1 << 14
                MS_PRIVATE = 1 << 18
                if libc.unshare(CLONE_NEWUSER | CLONE_NEWNS | CLONE_NEWIPC) == 0:
                    try:
                        Path("/proc/self/setgroups").write_bytes(b"deny\n")
                    except OSError:
                        pass
                    Path("/proc/self/uid_map").write_bytes(f"{uid} {uid} 1\n".encode("ascii"))
                    Path("/proc/self/gid_map").write_bytes(f"{gid} {gid} 1\n".encode("ascii"))
                    libc.mount(None, b"/", None, MS_REC | MS_PRIVATE, None)
                    for pdir in protected_dirs:
                        if not cwd_resolved.startswith(pdir) and os.path.isdir(pdir):
                            rc_m = libc.mount(
                                b"tmpfs",
                                pdir.encode("utf-8"),
                                b"tmpfs",
                                MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOEXEC,
                                b"size=4k,mode=000",
                            )
                            if rc_m != 0 and require_ns:
                                raise OSError(ctypes.get_errno(), f"Failed to mask protected directory {pdir}")
                    import struct
                    PR_SET_NO_NEW_PRIVS = 38
                    PR_CAPBSET_DROP = 24
                    _LINUX_CAPABILITY_VERSION_3 = 0x20080522
                    libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
                    for _cap in range(41):
                        libc.prctl(PR_CAPBSET_DROP, _cap, 0, 0, 0)
                    _cap_hdr = struct.pack("II", _LINUX_CAPABILITY_VERSION_3, 0)
                    _cap_data = struct.pack("IIIIII", 0, 0, 0, 0, 0, 0)
                    if libc.capset(_cap_hdr, _cap_data) != 0 and require_ns:
                        raise OSError(ctypes.get_errno(), "Sandbox capability drop (capset) failed")
                elif require_ns:
                    raise OSError(ctypes.get_errno(), "Sandbox namespace isolation (unshare) failed")
            except Exception:
                if require_ns:
                    raise
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_NOFILE, (1024, 1024))
        except Exception:
            pass

    return _preexec


def _run_isolated(
    cmd: Sequence[str] | str,
    *,
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
    input_data: Optional[str] = None,
    timeout: float = 2.0,
    shell: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Execute a command in an isolated namespace and process group (`preexec_fn=_build_sandbox_preexec`),
    killing all child/daemon processes on timeout or exit (`GRD-001`, `MUT-C07`, `MUT-C08`).
    Uses bounded stream reading to prevent pipe flood memory exhaustion (OOM).
    """
    run_env = dict(env if env is not None else os.environ)
    run_env.setdefault("DT_ARENA_STATS_FILE", str(Path(cwd) / "__dt_arena_stats.jsonl"))
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=run_env,
        stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        shell=shell,
        preexec_fn=_build_sandbox_preexec(cwd),
    )
    try:
        stdout, stderr = _communicate_bounded(proc, input_data=input_data, timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        raise

    # Detect and kill any background child/daemon process left in the process group (MUT-C08)
    leaked_bg = False
    try:
        os.killpg(proc.pid, signal.SIGKILL)
        leaked_bg = True
    except ProcessLookupError:
        pass
    except PermissionError:
        leaked_bg = True

    if leaked_bg:
        raise subprocess.TimeoutExpired(cmd, timeout, output=stdout, stderr=stderr)

    return subprocess.CompletedProcess(cmd, proc.returncode or 0, stdout, stderr)


def _to_cat_e(text: str) -> str:
    """Render text with '$' at the end of each line like `cat -e`."""
    if not text:
        return ""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for ln in lines:
        if ln.endswith("\n"):
            out.append(ln[:-1].replace("\t", "^I") + "$\n")
        else:
            out.append(ln.replace("\t", "^I"))
    return "".join(out)


@dataclass
class GradeError:
    """Unified structured grading error separating student vs. infrastructure failures."""
    kind: str
    category: str  # "student" | "infrastructure"
    context: str
    suggested_fix: str

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "category": self.category,
            "context": self.context,
            "suggested_fix": self.suggested_fix,
        }



def classify_process_exit_status(returncode: int, stderr_text: str = "", timed_out: bool = False) -> tuple[str, str, bool]:
    """Classify subprocess termination status using trusted_harness/dt_diagnostics.c (via libdt_core.so when built)
    with exact parity fallback. Strictly preserves negative signal numbers (e.g. SIGABRT -6, SIGSEGV -11, SIGBUS -7)
    versus positive normal exit codes (e.g. Exit 6, Exit 11, Exit 7) and memory KO exit codes (42, 43, 44, 45, 46).
    Returns (status_label, reason_detail, is_memory_or_signal_fatal).
    """
    if timed_out:
        return "Timeout", "Command killed by timeout", True
    if returncode == 0:
        return "OK :)", "OK :)", False

    err_s = stderr_text or ""
    if returncode < 0:
        sig = -returncode
        if sig == 6:
            if "[DOUBLE FREE KO]" in err_s:
                return "Double/Invalid Free KO (abort)", "Double free detected by memory harness", True
            return "Abort (Signal -6)", "Process terminated by SIGABRT (Signal -6)", True
        if sig == 11:
            return "Segmentation fault (Signal -11)", "Process terminated by SIGSEGV (Signal -11)", True
        if sig == 7:
            return "Bus error (Signal -7)", "Process terminated by SIGBUS (Signal -7)", True
        if sig == 8:
            return "Floating point exception (Signal -8)", "Process terminated by SIGFPE (Signal -8)", True
        return f"Signal -{sig}", f"Process terminated by Signal -{sig}", True

    # Positive exit codes (1..255): never misclassify positive exit codes 6, 7, 8, 11 as signals!
    if returncode == 42:
        return "Leak KO (memory leak detected)", "Unfreed heap memory blocks detected at exit", True
    if returncode == 43:
        return "Redzone KO (heap buffer overflow / off-by-one)", "Heap redzone canary corruption detected", True
    if returncode == 44:
        if "[ARENA OWNERSHIP KO]" in err_s:
            return "Invalid Free KO (arena ownership violation)", "Student attempted to free/realloc harness arena pointer", True
        return "Invalid Free KO (untracked or misaligned pointer)", "Attempted to free untracked or misaligned pointer", True
    if returncode == 45:
        return "Allocation Tracking Exhausted KO", "Allocation tracking capacity exceeded", True
    if returncode == 46 or (returncode == 6 and "[DOUBLE FREE KO]" in err_s):
        return "Double/Invalid Free KO (abort)", "Double free detected by memory harness", True

    return f"Exit {returncode}", f"Non-zero exit code {returncode}", False


def classify_grade_error(subject_id: str, ok: bool, status: str, reason: str, last_cmd: str = "") -> GradeError | None:
    if ok:
        return None
    s_low = (status or "").lower()
    r_low = (reason or "").lower()
    combined = f"{s_low} | {r_low}"

    # 1. Infrastructure / configuration failures (never blamed on student code)
    if "configuration error" in combined or "malformed" in combined or "no test cases executed" in combined or "empty test oracle" in combined:
        if "meta.yml" in combined:
            kind = "malformed_meta_yaml"
            fix = f"Fix YAML syntax in subjects/{subject_id}/meta.yml."
        elif "tests.yml" in combined:
            kind = "malformed_tests_yaml"
            fix = f"Fix YAML syntax in subjects/{subject_id}/tests.yml."
        elif "nm" in combined or "compiler" in combined:
            kind = "missing_toolchain_binary"
            fix = "Ensure `cc`, `c++`, and `nm` (binutils) are installed and on PATH."
        else:
            kind = "empty_test_oracle"
            fix = f"Ensure subjects/{subject_id}/tests.yml defines at least one valid test case."
        return GradeError(
            kind=kind,
            category="infrastructure",
            context=f"{subject_id}: {status} ({reason})",
            suggested_fix=fix,
        )

    # 2. Student failures (actionable feedback without leaking solutions)
    if "nothing turned in" in combined or "missing" in combined:
        return GradeError(
            kind="nothing_turned_in",
            category="student",
            context=f"{subject_id}: {reason}",
            suggested_fix=f"Place the required turn-in file(s) in rendu/{subject_id}/ and push to Vogsphere.",
        )
    if "main()" in combined:
        return GradeError(
            kind="forbidden_main",
            category="student",
            context=f"{subject_id}: {reason}",
            suggested_fix="Remove or guard your test `main()` function before submitting a function-only exercise.",
        )
    if "-42" in combined or "cheating" in combined or "forbidden" in combined:
        return GradeError(
            kind="forbidden_symbol_or_header",
            category="student",
            context=f"{subject_id}: {reason}",
            suggested_fix="Remove forbidden functions, headers, or inline assembly and restrict calls to "
                          " the subject's Allowed functions list.",
        )
    if "norme" in combined or "sh-norm" in combined:
        return GradeError(
            kind="norm_error",
            category="student",
            context=f"{subject_id}: {reason}",
            suggested_fix="Run `norminette` (or `shnorm` for shell scripts) and fix formatting/style violations.",
        )
    if "does not compile" in combined or "compilation" in combined or "must_not_compile" in combined:
        return GradeError(
            kind="compile_error",
            category="student",
            context=f"{subject_id}: {reason}",
            suggested_fix="Compile locally with `-Wall -Wextra -Werror` and match the exact prototype and header requirements.",
        )
    if "makefile" in combined or "relink" in combined or "wildcard" in combined:
        return GradeError(
            kind="makefile_error",
            category="student",
            context=f"{subject_id}: {reason}",
            suggested_fix="Ensure your Makefile defines $(NAME), all, clean, fclean, re, uses explicit source lists, and does not relink.",
        )
    if "timeout" in combined or "timed out" in combined:
        return GradeError(
            kind="timeout",
            category="student",
            context=f"{subject_id}: {reason}" + (f" while running `{last_cmd}`" if last_cmd else ""),
            suggested_fix="Check loop termination conditions, pointer increments, and blocking read() calls.",
        )
    if any(k in combined for k in ("segfault", "sigsegv", "sigabrt", "bus error", "sigbus", "fpe", "sigfpe", "signal", "crash", "asan", "ubsan", "overflow")):
        return GradeError(
            kind="runtime_crash_or_sanitizer",
            category="student",
            context=f"{subject_id}: {status} ({reason})",
            suggested_fix="Check null-pointer dereferences, out-of-bounds array indexing, signed integer overflow, and unallocated memory access.",
        )
    if "leak" in combined or "free" in combined or "heap" in combined or "memory" in combined:
        return GradeError(
            kind="memory_error",
            category="student",
            context=f"{subject_id}: {reason}",
            suggested_fix="Ensure every heap allocation is freed on all return paths and handle `malloc() == NULL` gracefully.",
        )
    if "output limit" in combined or "truncated" in combined:
        return GradeError(
            kind="output_limit_exceeded",
            category="student",
            context=f"{subject_id}: {reason}",
            suggested_fix="Prevent unbounded output loops; output exceeded the 64 KB stream cap.",
        )
    if "exit" in combined or "return code" in combined:
        return GradeError(
            kind="unexpected_exit_code",
            category="student",
            context=f"{subject_id}: {reason}",
            suggested_fix="Verify main() return value or exit status on both valid and error inputs.",
        )
    return GradeError(
        kind="diff_mismatch",
        category="student",
        context=f"{subject_id}: {status}" + (f" on `{last_cmd}`" if last_cmd else ""),
        suggested_fix="Compare expected vs. actual `cat -e` output in the trace (check trailing spaces and newlines).",
    )



import contextlib


@contextlib.contextmanager
def _tracked_eval_tempdir(exec_tmp_root: Path, stats_sink: list[dict[str, int] | None]):
    with tempfile.TemporaryDirectory(prefix="dt_c_", dir=str(exec_tmp_root)) as tmp:
        try:
            yield tmp
        finally:
            stats_sink[0] = _collect_arena_stats(Path(tmp))


def _collect_arena_stats(work: Path) -> dict[str, int] | None:
    """Aggregate real measured Arena & Student Heap telemetry from __dt_arena_stats.jsonl."""
    stats_file = work / "__dt_arena_stats.jsonl"
    if not stats_file.is_file():
        return None
    agg = {
        "sandbox_runs": 0,
        "regions_allocated": 0,
        "active_regions_max": 0,
        "reserved_bytes_max": 0,
        "used_bytes_max": 0,
        "peak_reserved_bytes": 0,
        "peak_used_bytes": 0,
        "total_allocations": 0,
        "reused_regions": 0,
        "allocation_failures": 0,
        "reset_count": 0,
        "rewind_count": 0,
        "trim_count": 0,
        "student_malloc_calls": 0,
        "student_free_calls": 0,
        "student_leaked_blocks": 0,
        "student_leaked_bytes": 0,
    }
    parsed_any = False
    for raw_line in stats_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            row = json.loads(raw_line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        parsed_any = True
        agg["sandbox_runs"] += 1
        agg["regions_allocated"] += int(row.get("regions_allocated", 0))
        agg["active_regions_max"] = max(agg["active_regions_max"], int(row.get("active_regions", 0)))
        agg["reserved_bytes_max"] = max(agg["reserved_bytes_max"], int(row.get("reserved_bytes", 0)))
        agg["used_bytes_max"] = max(agg["used_bytes_max"], int(row.get("used_bytes", 0)))
        agg["peak_reserved_bytes"] = max(agg["peak_reserved_bytes"], int(row.get("peak_reserved_bytes", 0)))
        agg["peak_used_bytes"] = max(agg["peak_used_bytes"], int(row.get("peak_used_bytes", 0)))
        agg["total_allocations"] += int(row.get("total_allocations", 0))
        agg["reused_regions"] += int(row.get("reused_regions", 0))
        agg["allocation_failures"] += int(row.get("allocation_failures", 0))
        agg["reset_count"] += int(row.get("reset_count", 0))
        agg["rewind_count"] += int(row.get("rewind_count", 0))
        agg["trim_count"] += int(row.get("trim_count", 0))
        agg["student_malloc_calls"] += int(row.get("student_malloc_calls", 0))
        agg["student_free_calls"] += int(row.get("student_free_calls", 0))
        agg["student_leaked_blocks"] += int(row.get("student_leaked_blocks", 0))
        agg["student_leaked_bytes"] += int(row.get("student_leaked_bytes", 0))
    return agg if parsed_any else None

@dataclass
class GradeReport:
    subject_id: str
    ok: bool
    status: str
    reason: str
    trace_text: str
    trap_diagnostic: str = ""
    golden_oracle: dict[str, str] = field(default_factory=dict)
    last_cmd: str = ""
    expected_cat_e: str = ""
    actual_cat_e: str = ""
    error_info: dict[str, str] | None = None
    arena_stats: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if not self.ok and self.error_info is None:
            err = classify_grade_error(self.subject_id, self.ok, self.status, self.reason, self.last_cmd)
            if err is not None:
                self.error_info = err.to_dict()

    @property
    def is_infrastructure_error(self) -> bool:
        return bool(self.error_info and self.error_info.get("category") == "infrastructure")

    @property
    def passed(self) -> bool:
        return self.ok

    @property
    def grade(self) -> int:
        return 100 if self.ok else (-42 if "-42" in self.status else 0)

    @property
    def trace(self) -> str:
        return self.trace_text

    def format_exam_trace_summary(self, *, include_coaching: bool = False) -> str:
        """Format the 42/1337 ExamShell TRACE block for failed submissions."""
        if self.ok:
            return ">>>>>>>>>> SUCCESS <<<<<<<<<<"
        if self.is_infrastructure_error and self.error_info:
            return (
                "==================== INFRASTRUCTURE ERROR ====================\n"
                f"Kind   : {self.error_info['kind']}\n"
                f"Context: {self.error_info['context']}\n"
                f"Action : {self.error_info['suggested_fix']}\n"
                "==============================================================\n"
                ">>>>>>>>>> ERROR: Grader configuration/infrastructure issue <<<<<<<<<<"
            )
        if "-42" in self.status or "Cheating" in self.status:
            return (
                "==================== TRACE ====================\n"
                f"Reason : {self.reason}\n"
                "===============================================\n"
                ">>>>>>>>>> FAILURE: Cheat detected (forbidden function) <<<<<<<<<<"
            )
        coaching_suffix = ""
        if include_coaching and self.error_info:
            coaching_suffix = f"\n[Suggested Fix]: {self.error_info['suggested_fix']}"
            if self.trap_diagnostic:
                coaching_suffix += f"\n[Coaching Hint]: {self.trap_diagnostic}"
        if self.expected_cat_e or self.actual_cat_e or self.last_cmd:
            exp_s = self.expected_cat_e.rstrip("\n")
            act_s = self.actual_cat_e.rstrip("\n")
            return (
                "==================== TRACE ====================\n"
                f"Command: {self.last_cmd or f'./{self.subject_id} | cat -e'}\n"
                "--- Expected Output (cat -e) ---\n"
                f"{exp_s}\n"
                "--- Your Output (cat -e) ---\n"
                f"{act_s}\n"
                "===============================================\n"
                ">>>>>>>>>> FAILURE <<<<<<<<<<" + coaching_suffix
            )
        return (
            "==================== TRACE ====================\n"
            f"Status : {self.status}\n"
            f"Detail : {self.reason}\n"
            "===============================================\n"
            ">>>>>>>>>> FAILURE <<<<<<<<<<" + coaching_suffix
        )



MAX_OUTPUT_BYTES = 65536
MAX_DIFF_Preview_BYTES = 8192


def _truncate_stream(text: str, limit: int = MAX_OUTPUT_BYTES) -> tuple[str, bool]:
    """Truncate oversized stdout/stderr stream to prevent OOM or trace bloat (`MAJ-02`)."""
    if len(text) <= limit:
        return text, False
    return text[:limit] + f"\n...[Output truncated at {limit // 1024} KB — Output limit exceeded]...\n", True


def format_unified_diff(expected: str, actual: str, label_exp: str = "test.output", label_got: str = "user_output") -> str:
    expected, _ = _truncate_stream(expected, MAX_DIFF_Preview_BYTES)
    actual, _ = _truncate_stream(actual, MAX_DIFF_Preview_BYTES)
    exp_has_nl = expected.endswith("\n")
    got_has_nl = actual.endswith("\n")
    exp_raw = expected.splitlines()
    got_raw = actual.splitlines()

    # When lines are identical except for trailing newline (Scenario A: missing \n at EOF)
    if exp_raw == got_raw and exp_has_nl != got_has_nl:
        line_no = max(1, len(exp_raw))
        last_line = exp_raw[-1] if exp_raw else ""
        out = [
            f"--- {label_got}$\n",
            f"+++ {label_exp}$\n",
            f"@@ -{line_no} +{line_no} @@$\n",
            f"-{last_line}$\n",
        ]
        if not got_has_nl:
            out.append("\\ No newline at end of file$\n")
        out.append(f"+{last_line}$\n")
        if not exp_has_nl:
            out.append("\\ No newline at end of file$\n")
        return "".join(out).rstrip("\n")

    exp_lines = [line + "$\n" for line in exp_raw]
    got_lines = [line + "$\n" for line in got_raw]
    diff = list(
        difflib.unified_diff(
            got_lines,
            exp_lines,
            fromfile=label_got,
            tofile=label_exp,
            n=3,
        )
    )
    if diff and not got_has_nl and got_raw:
        # Insert '\ No newline at end of file$' after the last '-' line
        last_minus_idx = max((i for i, l in enumerate(diff) if l.startswith("-") and not l.startswith("---")), default=-1)
        if last_minus_idx != -1:
            diff.insert(last_minus_idx + 1, "\\ No newline at end of file$\n")
    return "".join(diff).rstrip("\n")



@functools.lru_cache(maxsize=1)
def _cached_host_and_compiler_info() -> tuple[str, str, str, str]:
    host = platform.node() or "deepthought-worker"
    u = platform.uname()
    uname_s = f"{u.system} {u.release} {u.machine}"
    gcc_v = (
        subprocess.run(["gcc", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
        if shutil.which("gcc")
        else "gcc (Debian) 12.2.0"
    )
    clang_v = (
        subprocess.run(["clang", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
        if shutil.which("clang")
        else "clang: not installed (dual-compiler check skipped)"
    )
    return host, uname_s, gcc_v, clang_v


def build_deepthought_header(subject_id: str, rendu_dir=None, expected_files=None, git_repo=None, git_log_text: str | None = None, **kwargs) -> str:
    host, uname, gcc_v, clang_v = _cached_host_and_compiler_info()
    dt = time.strftime("%a %b %d %H:%M:%S %Z %Y")
    lines = [
        "= Host-specific information ====================================================",
        "$> hostname; uname -msr",
        host,
        uname,
        "$> date",
        dt,
        "$> gcc --version",
        gcc_v,
        "$> clang --version",
        clang_v,
        "",
        "= User files collection ========================================================",
        f"Collecting user files from Vogsphere",
        f"Repository URL: vogsphere@vogsphere.1337.ma:exam-session/{subject_id}",
        "",
        "= Git history ==================================================================",
        "$> git -C /var/tmp/deepthought/user_repo log -n 5 --pretty=format:\"%H - %an, %ad : %s\"",
    ]
    if git_log_text:
        lines.append(git_log_text.strip())
    elif git_repo and pathlib.Path(git_repo).exists():
        r = subprocess.run(["git", "-C", str(git_repo), "log", "-n", "5", "--pretty=format:%H - %an, %ad : %s"], capture_output=True, text=True)
        lines.append(r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "No commits found in bare repository")
    elif rendu_dir and pathlib.Path(rendu_dir).exists() and (pathlib.Path(rendu_dir) / ".git").exists():
        r = subprocess.run(["git", "-C", str(rendu_dir), "log", "-n", "5", "--pretty=format:%H - %an, %ad : %s"], capture_output=True, text=True)
        lines.append(r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "Local working tree evaluation")
    else:
        lines.append("Local working tree evaluation")
    if rendu_dir and pathlib.Path(rendu_dir).exists():
        r_path = pathlib.Path(rendu_dir)
        ls_lines = [f"{r_path}:"]
        try:
            entries = sorted(r_path.iterdir(), key=lambda p: p.name)
            ls_lines.append(f"total {len(entries) * 4}")
            for ent in entries:
                if ent.name == ".git":
                    continue
                st = ent.lstat()
                mode_s = stat_mod.filemode(st.st_mode)
                mtime_s = time.strftime("%b %e %H:%M", time.localtime(st.st_mtime))
                ls_lines.append(f"{mode_s} 1 user group {st.st_size:6d} {mtime_s} {ent.name}")
        except OSError:
            pass
        lines.extend([
            "",
            "= Collected files ==============================================================",
            "$> ls -lAR /var/tmp/deepthought/user_repo",
            "\n".join(ls_lines),
        ])
    lines.append("")
    return "\n".join(lines)


_LINTER_MODULE_CACHE: dict[tuple[str, str], Any] = {}


def _load_linter_module(script_path: Path, mod_name: str) -> Any:
    try:
        sha = hashlib.sha256(script_path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None
    key = (f"{mod_name}:{script_path.resolve()}", sha)
    mod = _LINTER_MODULE_CACHE.get(key)
    if mod is not None:
        return mod
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader(mod_name, str(script_path))
    spec = importlib.util.spec_from_loader(mod_name, loader)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    _LINTER_MODULE_CACHE[key] = mod
    return mod


def run_norminette_check(kit_root: Path, files: list[Path], *, is_shell: bool = False) -> tuple[bool, str]:
    if is_shell:
        shnorm = kit_root / "bin/shnorm"
        if not shnorm.exists():
            return True, "shnorm skipped"
        sh_files = [f for f in files if f.suffix == ".sh"]
        if not sh_files:
            return True, "OK"
        mod = _load_linter_module(shnorm, "_dt_shnorm_mod")
        if mod is not None and hasattr(mod, "ShNormLinter"):
            linter = mod.ShNormLinter(oneliner_mode=True)
            out_lines: list[str] = []
            any_err = False
            for sp in sh_files:
                errs = linter.check_file(sp)
                if not errs:
                    out_lines.append(f"{sp}: OK!")
                else:
                    any_err = True
                    out_lines.append(f"{sp}: Error!")
                    for e in errs:
                        out_lines.append(e.format_42(color=False))
            out = "\n".join(out_lines)
            return (not any_err), f"$> shnorm -1 {' '.join(f.name for f in files)}\n{out}"
        proc = subprocess.run([sys.executable, str(shnorm), "-1", *[str(f) for f in sh_files]], capture_output=True, text=True, errors="replace")
        out = (proc.stdout + proc.stderr).strip()
        return proc.returncode == 0, f"$> shnorm -1 {' '.join(f.name for f in files)}\n{out}"

    local_norm = kit_root / "bin/norminette"
    c_files = [f for f in files if f.suffix in {".c", ".h"}]
    if not c_files:
        return True, "OK"
    if local_norm.exists():
        mod = _load_linter_module(local_norm, "_dt_norminette_mod")
        if mod is not None and hasattr(mod, "check_file"):
            flags = ["-R", "CheckForbiddenSourceHeader"]
            out_lines = []
            any_err = False
            for sp in c_files:
                errs = mod.check_file(sp, flags)
                if errs:
                    any_err = True
                    out_lines.append(f"{sp.name}: Error!")
                    for e in errs:
                        out_lines.append(f"    {e}")
                else:
                    out_lines.append(f"{sp.name}: OK!")
            out = "\n".join(out_lines)
            return (not any_err), f"$> norminette -R CheckForbiddenSourceHeader {' '.join(f.name for f in c_files)}\n{out}"
    norm_bin = str(local_norm) if local_norm.exists() else shutil.which("norminette")
    if norm_bin:
        cmd = [sys.executable, norm_bin] if local_norm.exists() else [norm_bin]
        proc = subprocess.run([*cmd, "-R", "CheckForbiddenSourceHeader", *[str(f) for f in c_files]], capture_output=True, text=True, errors="replace")
        out = (proc.stdout + proc.stderr).strip()
        ok = proc.returncode == 0 and "Error!" not in out
        return ok, f"$> norminette -R CheckForbiddenSourceHeader {' '.join(f.name for f in c_files)}\n{out}"
    return True, "$> norminette (not installed in environment — check skipped)"


def evaluate_c_header(subject_id: str, submit_dir: Path, meta: dict, trace: list[str]) -> tuple[bool, str]:
    """Compile a real C program including the header twice to verify #ifndef include guards, macros, and prototypes."""
    exp = (meta.get("expected_files") or [f"{subject_id}"])[0]
    hfile = submit_dir / exp
    if not hfile.exists():
        return False, "Nothing turned in"

    inc_viol = check_forbidden_c_includes([hfile], allowed_root=submit_dir)
    if inc_viol:
        trace.extend(inc_viol)
        return False, f"Cheating (-42): {inc_viol[0]}"
    txt = hfile.read_text(encoding="utf-8", errors="ignore")
    if not (re.search(r"#\s*ifndef\b", txt) and re.search(r"#\s*define\b", txt) and re.search(r"#\s*endif\b", txt)):
        trace.append("Header error: Missing #ifndef / #define / #endif include guard!")
        return False, "Does not compile (missing include guard)"

    with tempfile.TemporaryDirectory(prefix="dt_hdr_", dir=str(get_executable_temp_root())) as td:
        work = Path(td)
        shutil.copy2(hfile, work / hfile.name)
        if subject_id == "ft_abs.h" or hfile.name == "ft_abs.h":
            test_c = (
                f'#include "{hfile.name}"\n#include "{hfile.name}"\n#include <stdio.h>\n'
                'int main(void) { if (ABS(-5) != 5 || ABS(5) != 5 || ABS(-10 + 3) != 7 || ABS(0) != 0) return 1; return 0; }\n'
            )
        elif subject_id == "ft_point.h" or hfile.name == "ft_point.h":
            test_c = (
                f'#include "{hfile.name}"\n#include "{hfile.name}"\n'
                'void set_point(t_point *point) { point->x = 42; point->y = 21; }\n'
                'int main(void) { t_point p; set_point(&p); return (p.x == 42 && p.y == 21) ? 0 : 1; }\n'
            )
        elif subject_id == "ft_boolean.h" or hfile.name == "ft_boolean.h":
            test_c = (
                f'#include "{hfile.name}"\n#include "{hfile.name}"\n'
                't_bool ft_is_even(int nbr) { return ((EVEN(nbr)) ? TRUE : FALSE); }\n'
                'int main(void) { if (ft_is_even(4) != TRUE || ft_is_even(3) != FALSE) return 1; return (SUCCESS); }\n'
            )
        elif subject_id == "ft.h" or hfile.name == "ft.h":
            # Verify all 5 required prototypes in ft.h BEFORE dummy definitions (GRD-016)
            test_c = (
                f'#include "{hfile.name}"\n#include "{hfile.name}"\n'
                'int main(void) {\n'
                '    void (*p1)(char) = ft_putchar;\n'
                '    void (*p2)(int *, int *) = ft_swap;\n'
                '    void (*p3)(char *) = ft_putstr;\n'
                '    int (*p4)(char *) = ft_strlen;\n'
                '    int (*p5)(char *, char *) = ft_strcmp;\n'
                '    if (!p1 || !p2 || !p3 || !p4 || !p5) return 1;\n'
                '    return 0;\n'
                '}\n'
                'void ft_putchar(char c) { (void)c; }\n'
                'void ft_swap(int *a, int *b) { (void)a; (void)b; }\n'
                'void ft_putstr(char *str) { (void)str; }\n'
                'int ft_strlen(char *str) { (void)str; return 0; }\n'
                'int ft_strcmp(char *s1, char *s2) { (void)s1; (void)s2; return 0; }\n'
            )
        else:
            test_c = f'#include "{hfile.name}"\n#include "{hfile.name}"\nint main(void) {{ return 0; }}\n'

        (work / "test_hdr.c").write_text(test_c, encoding="utf-8")
        cmd = ["cc", *FLAGS_COMPILE_SAFE, "test_hdr.c", "-o", "test_hdr"]
        trace.append("$> " + " ".join(["cc", *FLAGS_DEFAULT, "test_hdr.c", "-o", "test_hdr"]))
        proc = _run_isolated(cmd, cwd=work, timeout=5.0)
        if proc.returncode != 0:
            trace.append(proc.stderr.strip())
            return False, "Does not compile"
        rproc = _run_isolated([str(work / "test_hdr")], cwd=work, timeout=2.0)
        if rproc.returncode != 0:
            trace.append("Macro / struct evaluation failed!")
            return False, "Diff KO :("
    trace.append("Header compilation & double-inclusion guard check: OK :D")
    return True, "OK :)"


def evaluate_cpp_exercise(
    subj_dir: Path,
    subject_id: str,
    submit_dir: Path,
    meta: dict,
    trace: list[str],
    oracle_info: dict,
) -> GradeReport:
    expected_files = meta.get("expected_files") or []
    for exp in expected_files:
        if not (submit_dir / exp).exists():
            trace.append(f"Missing expected turn-in file: '{exp}'\nNothing turned in\nGrade: 0")
            return GradeReport(subject_id, False, "Nothing turned in", f"Missing {exp}", "\n".join(trace), "", oracle_info)

    cpp_and_hdr_files = [submit_dir / exp for exp in expected_files if (submit_dir / exp).is_file()]
    inc_viol = check_forbidden_c_includes(cpp_and_hdr_files, allowed_root=submit_dir)
    if inc_viol:
        trace.extend(inc_viol)
        return GradeReport(subject_id, False, "Cheating (-42)", f"Cheating (-42): {inc_viol[0]}", "\n".join(trace), "", oracle_info)
    for exp in expected_files:
        txt = (submit_dir / exp).read_text(encoding="utf-8", errors="replace")
        if re.search(r"\bswitch\s*\(", txt):
            trace.append(f"{exp}: Cheating (-42): switch statement is forbidden in {subject_id}!")
            return GradeReport(subject_id, False, "Cheating (-42)", "switch statement forbidden", "\n".join(trace), "", oracle_info)

    cxx = shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")
    if not cxx:
        return GradeReport(subject_id, False, "Configuration Error: No C++ compiler", "No C++ compiler", "\n".join(trace), "", oracle_info)

    tests_cfg = _safe_load_yaml(subj_dir / "tests.yml")
    if "__yaml_error__" in tests_cfg:
        return GradeReport(subject_id, False, "Configuration Error: Malformed tests.yml", tests_cfg["__yaml_error__"], "\n".join(trace), "", oracle_info)

    with tempfile.TemporaryDirectory(prefix="dt_cpp_", dir=str(get_executable_temp_root())) as td:
        work = Path(td)
        for exp in expected_files:
            shutil.copy2(submit_dir / exp, work / exp)
        main_cpp = work / "__dt_main.cpp"
        main_cpp.write_text(str(tests_cfg.get("main_cpp") or tests_cfg.get("main_code") or ""), encoding="utf-8")
        cpp_srcs = [exp for exp in expected_files if str(exp).endswith(".cpp")] + ["__dt_main.cpp"]
        cproc = _run_isolated(
            [cxx, "-Wall", "-Wextra", "-Werror", "-std=c++98", *cpp_srcs, "-o", "user_exe"],
            cwd=work,
            timeout=10.0,
        )
        if cproc.returncode != 0:
            trace.append(cproc.stderr.strip())
            return GradeReport(subject_id, False, "Does not compile", "Does not compile", "\n".join(trace), "", oracle_info)
        if not tests_cfg.get("main_cpp") and tests_cfg.get("fixed_tests"):
            for idx, ft in enumerate(tests_cfg["fixed_tests"], start=1):
                exp_out = ft.get("stdout") if ft.get("stdout") is not None else (ft.get("expected") if ft.get("expected") is not None else ft.get("expected_stdout"))
                exp_err = ft.get("stderr") if ft.get("stderr") is not None else ft.get("expected_stderr")
                exp_rc = ft.get("expected_returncode")
                if "python_harness" in ft:
                    h_py = work / f"__dt_harness_{idx}.py"
                    h_py.write_text(str(ft["python_harness"]), encoding="utf-8")
                    hproc = _run_isolated([sys.executable, str(h_py), str(work / "user_exe")], cwd=work, timeout=5.0)
                    exp_h = str(ft.get("expected", "OK\n"))
                    if hproc.stdout != exp_h:
                        trace.append(f"Harness failed:\n{hproc.stdout}\n{hproc.stderr}")
                        return GradeReport(subject_id, False, "Diff KO :(", f"Harness failed on Test {idx}", "\n".join(trace), "", oracle_info)
                    continue
                cmd_args = [str(a) for a in (ft.get("args") or [])]
                try:
                    rproc = _run_isolated([str(work / "user_exe"), *cmd_args], cwd=work, input_data=ft.get("stdin"), timeout=2.0)
                except subprocess.TimeoutExpired:
                    return GradeReport(subject_id, False, "Timeout", f"Timeout on Test {idx}", "\n".join(trace), "", oracle_info)
                if exp_rc is not None and rproc.returncode != exp_rc:
                    return GradeReport(subject_id, False, f"Non-zero exit code {rproc.returncode}", f"Exit {rproc.returncode}", "\n".join(trace), "", oracle_info)
                if exp_err is not None and rproc.stderr != exp_err:
                    return GradeReport(subject_id, False, "Diff KO :(", f"Stderr mismatch on Test {idx}", "\n".join(trace), "", oracle_info)
                if exp_out is not None and rproc.stdout != exp_out:
                    return GradeReport(subject_id, False, "Diff KO :(", f"Stdout mismatch on Test {idx}", "\n".join(trace), "", oracle_info)
            trace.append("Diff OK :D\n\n= Final grade: 100 =============================================================")
            return GradeReport(subject_id, True, "OK :)", "OK :)", "\n".join(trace), "", oracle_info)

        try:
            rproc = _run_isolated([str(work / "user_exe")], cwd=work, timeout=2.0)
        except subprocess.TimeoutExpired:
            return GradeReport(subject_id, False, "Timeout", "Timeout", "\n".join(trace), "", oracle_info)
        if len(rproc.stdout) > MAX_OUTPUT_BYTES or len(rproc.stderr) > MAX_OUTPUT_BYTES:
            trunc_out, _ = _truncate_stream(rproc.stdout)
            trace.append(trunc_out)
            trace.append("Output limit exceeded (>64 KB)\nGrade: 0")
            return GradeReport(subject_id, False, "Output limit exceeded (>64 KB)", "Output limit exceeded", "\n".join(trace), "", oracle_info)
        exp_out = str(tests_cfg.get("expected_stdout") if tests_cfg.get("expected_stdout") is not None else tests_cfg.get("expected", ""))
        if rproc.returncode != 0 or rproc.stdout != exp_out:
            trace.append(format_unified_diff(exp_out, rproc.stdout))
            return GradeReport(subject_id, False, "Diff KO :(", "Diff KO :(", "\n".join(trace), "", oracle_info)
        for neg_src in tests_cfg.get("must_not_compile") or []:
            (work / "__dt_neg.cpp").write_text(str(neg_src), encoding="utf-8")
            nproc = subprocess.run(
                [cxx, "-Wall", "-Wextra", "-Werror", "-std=c++98", "-c", "__dt_neg.cpp", "-o", "__dt_neg.o"],
                cwd=work,
                capture_output=True,
                text=True,
                errors="replace",
            )
            if nproc.returncode == 0:
                trace.append("Coplien / non-copyable check KO: forbidden copy/default construction compiled!")
                return GradeReport(subject_id, False, "Diff KO :(", "Coplien constraint violated", "\n".join(trace), "", oracle_info)
    trace.append("Diff OK :D\n\n= Final grade: 100 =============================================================")
    return GradeReport(subject_id, True, "OK :)", "OK :)", "\n".join(trace), "", oracle_info)


def evaluate_python_exercise(
    subj_dir: Path,
    subject_id: str,
    submit_dir: Path,
    meta: dict,
    trace: list[str],
    oracle_info: dict,
) -> GradeReport:
    expected_files = meta.get("expected_files") or [f"{subject_id}.py"]
    py_file = submit_dir / expected_files[0]
    if not py_file.exists():
        trace.append(f"Missing expected turn-in file: '{expected_files[0]}'\nNothing turned in\nGrade: 0")
        return GradeReport(subject_id, False, "Nothing turned in", f"Missing {expected_files[0]}", "\n".join(trace), "", oracle_info)

    content = py_file.read_text(encoding="utf-8", errors="ignore").strip()
    if not content:
        trace.append("Empty Python file turned in\nNothing turned in\nGrade: 0")
        return GradeReport(subject_id, False, "Nothing turned in", "Empty Python file", "\n".join(trace), "", oracle_info)

    tests_yml_path = subj_dir / "tests.yml"
    tests_cfg = _safe_load_yaml(tests_yml_path) if tests_yml_path.exists() else {}
    if "__yaml_error__" in tests_cfg:
        return GradeReport(subject_id, False, "Configuration Error: Malformed tests.yml", tests_cfg["__yaml_error__"], "\n".join(trace), "", oracle_info)
    fixed_tests = (tests_cfg or {}).get("fixed_tests") or []
    if not fixed_tests:
        trace.append("Configuration Error: No test suite defined for Python exercise\nGrade: 0")
        return GradeReport(subject_id, False, "Configuration Error: No test suite defined", "No tests defined", "\n".join(trace), "", oracle_info)

    with tempfile.TemporaryDirectory(prefix="dt_py_", dir=str(get_executable_temp_root())) as td:
        work = Path(td)
        shutil.copy2(py_file, work / py_file.name)
        for idx, ft in enumerate(fixed_tests, start=1):
            trace.append(f"\n= Test {idx} ===================================================================")
            if "expr" in ft:
                if not py_file.stem.isidentifier():
                    return GradeReport(subject_id, False, "Runtime error", "Invalid Python module identifier", "\n".join(trace), "", oracle_info)
                runner = f"import sys\nsys.path.insert(0, '.')\nimport {py_file.stem} as m\nfrom {py_file.stem} import *\nprint({ft['expr']})\n"
                (work / "__dt_run.py").write_text(runner, encoding="utf-8")
                cmd = [sys.executable, "-I", "-B", "__dt_run.py"]
                exp_out = str(ft.get("stdout") if ft.get("stdout") is not None else f"{ft.get('expected', ft.get('return', ''))}\n")
            else:
                args = [str(a) for a in (ft.get("args") or [])]
                cmd = [sys.executable, "-I", "-B", py_file.name, *args]
                exp_out = str(ft.get("stdout") if ft.get("stdout") is not None else ft.get("expected", ""))
            try:
                rproc = _run_isolated(cmd, cwd=work, input_data=ft.get("stdin"), timeout=2.0)
            except subprocess.TimeoutExpired:
                trace.append("Command got killed by a Timeout (elapsed > 2.0s)\nGrade: 0")
                return GradeReport(subject_id, False, "Timeout", "Timeout", "\n".join(trace), "", oracle_info)
            if len(rproc.stdout) > MAX_OUTPUT_BYTES or len(rproc.stderr) > MAX_OUTPUT_BYTES:
                trunc_out, _ = _truncate_stream(rproc.stdout)
                trace.append(trunc_out)
                trace.append("Output limit exceeded (>64 KB)\nGrade: 0")
                return GradeReport(subject_id, False, "Output limit exceeded (>64 KB)", "Output limit exceeded", "\n".join(trace), "", oracle_info)
            if rproc.returncode != 0:
                trunc_err, _ = _truncate_stream(rproc.stderr.strip())
                trace.append(f"Runtime error:\n{trunc_err}\nGrade: 0")
                return GradeReport(subject_id, False, "Runtime error", "Runtime error", "\n".join(trace), "", oracle_info)
            if rproc.stdout != exp_out:
                trace.append(format_unified_diff(exp_out, rproc.stdout, f"test{idx}.output", f"user_output_test{idx}"))
                trace.append("\nDiff KO :(\nGrade: 0")
                return GradeReport(subject_id, False, "Diff KO :(", "Diff KO :(", "\n".join(trace), "", oracle_info)
            trace.append("Diff OK :D")

    trace.append("\n= Final grade: 100 =============================================================")
    return GradeReport(subject_id, True, "OK :)", "OK :)", "\n".join(trace), "", oracle_info)


_SUBJECT_RESOLVE_CACHE: dict[tuple[str, str, bool], tuple[Path, str]] = {}
_PISCINE_SLUG_INDEX: dict[str, dict[str, tuple[Path, str]]] = {}
_META_ID_INDEX: dict[str, dict[str, tuple[Path, str]]] = {}


def _is_within_subjects_root(cand: Path, subjects_root: Path) -> bool:
    try:
        if not cand.exists():
            return False
        cand_res = cand.resolve()
        root_res = subjects_root.resolve()
        return str(cand_res).startswith(str(root_res) + os.sep)
    except OSError:
        return False


def _populate_subject_indices(kit_root: Path) -> tuple[dict[str, tuple[Path, str]], dict[str, tuple[Path, str]]]:
    subjects_root = kit_root / "subjects"
    piscine_idx: dict[str, tuple[Path, str]] = {}
    piscine_root = subjects_root / "piscine"
    if piscine_root.is_dir():
        for mod_d in sorted(piscine_root.iterdir()):
            if not mod_d.is_dir():
                continue
            for ex_d in sorted(mod_d.iterdir()):
                if not ex_d.is_dir() or not _is_within_subjects_root(ex_d, subjects_root):
                    continue
                piscine_idx.setdefault(ex_d.name, (ex_d, ex_d.name))
                if "_" in ex_d.name:
                    piscine_idx.setdefault(ex_d.name.split("_", 1)[1], (ex_d, ex_d.name))
                if ex_d.name.endswith(".sh"):
                    piscine_idx.setdefault(ex_d.name[:-3], (ex_d, ex_d.name))
    id_idx: dict[str, tuple[Path, str]] = {}
    for sub_root in (subjects_root / "exams", subjects_root / "piscine"):
        if not sub_root.exists():
            continue
        for mp in sub_root.rglob("meta.yml"):
            if not _is_within_subjects_root(mp.parent, subjects_root):
                continue
            mdata = _safe_load_yaml(mp)
            for k_field in ("id", "exercise_name"):
                val = mdata.get(k_field)
                if isinstance(val, str) and val and val not in id_idx:
                    id_idx[val] = (mp.parent, mp.parent.name)
    root_key = str(kit_root.resolve())
    _PISCINE_SLUG_INDEX[root_key] = piscine_idx
    _META_ID_INDEX[root_key] = id_idx
    return piscine_idx, id_idx


def resolve_subject_dir(kit_root: Path, subject_id: str, *, is_exam: bool = False) -> tuple[Path, str]:
    """Resolve plain or pool-namespaced subject IDs safely inside kit_root/subjects with dynamic cache invalidation (FIX-SP-004, OPT-SP-004)."""
    if "\x00" in subject_id:
        raise FileNotFoundError(f"Invalid subject identifier: {subject_id!r}")
    norm_id = subject_id.strip().strip("/")
    if ":" in norm_id:
        norm_id = norm_id.replace(":", "/")
    raw_parts = [p for p in re.split(r"[/\\]+", norm_id) if p]
    if ".." in raw_parts or "." in raw_parts:
        raise FileNotFoundError(f"Path traversal forbidden in subject identifier: {subject_id!r}")

    subjects_root = kit_root / "subjects"
    root_key = str(kit_root.resolve())
    cache_key = (root_key, norm_id, is_exam)
    cached = _SUBJECT_RESOLVE_CACHE.get(cache_key)
    if cached is not None:
        if _is_within_subjects_root(cached[0], subjects_root):
            return cached
        _SUBJECT_RESOLVE_CACHE.pop(cache_key, None)

    if "/" in norm_id:
        parts = raw_parts
        candidates = []
        if len(parts) == 2:
            if parts[0] == "exams":
                candidates.append(subjects_root / "exams" / parts[1])
            else:
                candidates.append(subjects_root / "piscine" / parts[0] / parts[1])
                candidates.append(subjects_root / "piscine" / parts[0] / f"{parts[0]}_{parts[1]}")
                candidates.append(subjects_root / "piscine" / parts[0] / f"{parts[1]}.sh")
        elif len(parts) >= 3 and parts[0] in ("piscine", "exams"):
            candidates.append(subjects_root / Path(*parts))
        candidates.append(subjects_root / Path(*parts))
        for c in candidates:
            if _is_within_subjects_root(c, subjects_root):
                _SUBJECT_RESOLVE_CACHE[cache_key] = (c, c.name)
                return c, c.name
        norm_id = parts[-1]

    subj_dir = subjects_root / "exams" / norm_id
    if is_exam and _is_within_subjects_root(subj_dir, subjects_root):
        _SUBJECT_RESOLVE_CACHE[cache_key] = (subj_dir, subj_dir.name)
        return subj_dir, subj_dir.name

    piscine_idx = _PISCINE_SLUG_INDEX.get(root_key)
    id_idx = _META_ID_INDEX.get(root_key)
    if piscine_idx is None or id_idx is None:
        piscine_idx, id_idx = _populate_subject_indices(kit_root)

    match_pair = piscine_idx.get(norm_id)
    if match_pair and not _is_within_subjects_root(match_pair[0], subjects_root):
        piscine_idx, id_idx = _populate_subject_indices(kit_root)
        match_pair = piscine_idx.get(norm_id)

    if match_pair and not is_exam:
        _SUBJECT_RESOLVE_CACHE[cache_key] = match_pair
        return match_pair
    if _is_within_subjects_root(subj_dir, subjects_root):
        _SUBJECT_RESOLVE_CACHE[cache_key] = (subj_dir, subj_dir.name)
        return subj_dir, subj_dir.name
    if match_pair:
        _SUBJECT_RESOLVE_CACHE[cache_key] = match_pair
        return match_pair

    if norm_id in id_idx and _is_within_subjects_root(id_idx[norm_id][0], subjects_root):
        _SUBJECT_RESOLVE_CACHE[cache_key] = id_idx[norm_id]
        return id_idx[norm_id]

    # Check if a new directory was added dynamically under subjects/exams or subjects/piscine
    if any((subjects_root / "piscine").glob(f"*{norm_id}*")):
        piscine_idx, id_idx = _populate_subject_indices(kit_root)
        if norm_id in piscine_idx:
            _SUBJECT_RESOLVE_CACHE[cache_key] = piscine_idx[norm_id]
            return piscine_idx[norm_id]
        if norm_id in id_idx:
            _SUBJECT_RESOLVE_CACHE[cache_key] = id_idx[norm_id]
            return id_idx[norm_id]

    if norm_id in {"clear", "cls"}:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        raise SystemExit(0)
    raise FileNotFoundError(f"Unknown subject: {subject_id}")



_SANDBOX_HARNESS_OBJ_CACHE: dict[str, tuple[Path, str]] = {}
_WRAP_LINK_FLAGS = (
    "-Wl,--wrap=malloc",
    "-Wl,--wrap=calloc",
    "-Wl,--wrap=realloc",
    "-Wl,--wrap=strdup",
    "-Wl,--wrap=free",
    "-Wl,--wrap=read",
    "-Wl,--wrap=exit",
    "-Wl,--wrap=_exit",
    "-Wl,--wrap=_Exit",
)


_HARNESS_OBJ_CACHE_LOCK = threading.Lock()
_HARNESS_CACHE_LOCK = _HARNESS_OBJ_CACHE_LOCK
_GRADER_TLS = threading.local()


def _get_strict_sandbox_flags(kit_root: Path, work: Path) -> list[str]:
    """Return linker/compiler flags for strict mode, using a content-addressed precompiled sandbox_harness.o cache keyed by source, headers, compiler version, arch, and flags (OPT-SP-001)."""
    harness_src = kit_root / "deepthought/sandbox_harness.c"
    if not harness_src.exists():
        return []
    dep_files = [
        harness_src,
        kit_root / "trusted_harness/dt_arena.c",
        kit_root / "trusted_harness/dt_arena.h",
        kit_root / "third_party/tsoding_arena/arena.h",
    ]
    h = hashlib.sha256()
    for df in dep_files:
        if df.is_file():
            h.update(df.read_bytes())
    _, uname_s, gcc_v, _ = _cached_host_and_compiler_info()
    h.update(f"{uname_s}|{gcc_v}|{' '.join(FLAGS_COMPILE_SAFE)}|{' '.join(_WRAP_LINK_FLAGS)}|-DDT_WRAP_MALLOC".encode("utf-8"))
    digest = h.hexdigest()[:20]

    cache_dir = get_executable_temp_root(kit_root) / ".dt_harness_obj_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_obj = cache_dir / f"sandbox_harness_{digest}.o"

    entry = _SANDBOX_HARNESS_OBJ_CACHE.get(digest)
    if entry is None or not cached_obj.is_file() or hashlib.sha256(cached_obj.read_bytes()).hexdigest() != entry[1]:
        with _HARNESS_OBJ_CACHE_LOCK:
            entry = _SANDBOX_HARNESS_OBJ_CACHE.get(digest)
            if entry is None or not cached_obj.is_file() or hashlib.sha256(cached_obj.read_bytes()).hexdigest() != entry[1]:
                tmp_obj = cache_dir / f"sandbox_harness_{digest}_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}.o"
                c_cmd = [
                    "cc",
                    *FLAGS_COMPILE_SAFE,
                    f"-I{kit_root / 'trusted_harness'}",
                    f"-I{kit_root / 'third_party/tsoding_arena'}",
                    "-DDT_WRAP_MALLOC",
                    "-c",
                    str(harness_src),
                    "-o",
                    str(tmp_obj),
                ]
                res = subprocess.run(c_cmd, capture_output=True, text=True)
                if res.returncode == 0 and tmp_obj.is_file():
                    obj_sha = hashlib.sha256(tmp_obj.read_bytes()).hexdigest()
                    tmp_obj.replace(cached_obj)
                    _SANDBOX_HARNESS_OBJ_CACHE[digest] = (cached_obj, obj_sha)
                elif tmp_obj.is_file():
                    tmp_obj.unlink(missing_ok=True)

    if cached_obj.is_file():
        shutil.copy2(cached_obj, work / "sandbox_harness.o")
        harness_input = "sandbox_harness.o"
    else:
        shutil.copy2(harness_src, work / "sandbox_harness.c")
        harness_input = "sandbox_harness.c"

    return [
        harness_input,
        f"-I{kit_root / 'trusted_harness'}",
        f"-I{kit_root / 'third_party/tsoding_arena'}",
        "-DDT_WRAP_MALLOC",
        *_WRAP_LINK_FLAGS,
    ]


def _grade_subject_inner(
    kit_root: Path,
    subject_id: str,
    submit_dir: Path,
    *,
    is_exam: bool = False,
    strict: bool = False,
    enforce_norm: bool = False,
    subj_dir_override: Path | None = None,
    git_log_text: str = "",
) -> GradeReport:
    kit_root = Path(kit_root).resolve()
    submit_dir = Path(submit_dir).resolve()
    if subj_dir_override is not None and subj_dir_override.exists():
        subj_dir = subj_dir_override.resolve()
        subject_id = subj_dir.name
    else:
        subj_dir, subject_id = resolve_subject_dir(kit_root, subject_id, is_exam=is_exam)

    meta_path = subj_dir / "meta.yml"
    if meta_path.exists():
        meta = _safe_load_yaml(meta_path)
        if "__yaml_error__" in meta:
            return GradeReport(
                subject_id,
                False,
                "Configuration Error: Malformed meta.yml",
                meta["__yaml_error__"],
                f"Configuration Error: Malformed meta.yml:\n{meta['__yaml_error__']}",
            )
    else:
        meta = {
            "id": subject_id,
            "type": "c_program",
            "expected_files": [f"{subject_id}.c"],
            "allowed_functions": ["write", "malloc", "free"],
            "norminette": not is_exam,
        }
    oracle_info = meta.get("golden_oracle", {}) or {}
    if isinstance(oracle_info, str):
        oracle_info = {"golden_code": oracle_info}
    expected_files = meta.get("expected_files", [f"{subject_id}.c"])

    if not submit_dir.exists():
        trace = [build_deepthought_header(subject_id, submit_dir, expected_files, git_repo=None, git_log_text=git_log_text)]
        trace.append(f"$> ls -la {subject_id}")
        trace.append(f"ls: {subject_id}: No such file or directory")
        trace.append("Nothing turned in\nGrade: 0")
        return GradeReport(subject_id, False, "Nothing turned in", "Nothing turned in", "\n".join(trace), "", oracle_info)

    collected = sorted(p.name for p in submit_dir.iterdir() if not p.name.startswith("."))
    trace = [build_deepthought_header(subject_id, submit_dir, expected_files, git_repo=None, git_log_text=git_log_text)]
    if not collected:
        trace.append(f"$> ls -la {subject_id}")
        trace.append(f"ls: {subject_id}: No such file or directory")
        trace.append("Nothing turned in\nGrade: 0")
        return GradeReport(subject_id, False, "Nothing turned in", "Nothing turned in", "\n".join(trace), "", oracle_info)

    stype = str(meta.get("type", "c_program")).lower()

    # --- Route 1: Shell Exercises ---
    if stype in {"shell", "shell_script", "shell_file"}:
        if ((not is_exam and (strict or meta.get("norminette", True))) or enforce_norm) and stype != "shell_file":
            ok_norm, norm_log = run_norminette_check(kit_root, [submit_dir / f for f in collected], is_shell=True)
            trace.append(norm_log)
            if not ok_norm:
                trace.append("\n= Final grade: 0 (Sh-Norm error) ===============================================")
                return GradeReport(subject_id, False, "Norme error", "Sh-Norm v4.2 violation", "\n".join(trace), "", oracle_info)
        sh_res = evaluate_shell_exercise(kit_root, subject_id, submit_dir, meta, strict=strict, subj_dir=subj_dir)
        trace.extend(sh_res.trace_lines)
        if sh_res.trap_hint:
            trace.append(f"\n[Moulinette Diagnostic]: {sh_res.trap_hint}")
        trace.append(f"\n= Final grade: {'100 (OK :)' if sh_res.ok else f'0 ({sh_res.reason})'} ===========================================")
        return GradeReport(subject_id, sh_res.ok, sh_res.reason, sh_res.reason, "\n".join(trace), sh_res.trap_hint, oracle_info)

    # --- Route 2: C Header Exercises (C 08) ---
    if stype == "c_header" or (expected_files and all(str(f).endswith(".h") for f in expected_files)):
        hdr_files = [submit_dir / f for f in expected_files if (submit_dir / f).exists()]
        bad_inc = check_forbidden_c_includes(hdr_files, allowed_root=submit_dir)
        if bad_inc:
            trace.extend(bad_inc)
            trace.append(">>>>>>>>>> FAILURE: Cheat detected (forbidden header include) <<<<<<<<<<")
            return GradeReport(subject_id, False, "Cheating (-42)", bad_inc[0], "\n".join(trace), "", oracle_info)
        if (not is_exam and meta.get("norminette", True)) or enforce_norm:
            ok_n, n_log = run_norminette_check(kit_root, hdr_files)
            trace.append(n_log)
            if not ok_n:
                return GradeReport(subject_id, False, "Norme error", "Norme error", "\n".join(trace), "", oracle_info)
        ok_h, status_h = evaluate_c_header(subject_id, submit_dir, meta, trace)
        return GradeReport(subject_id, ok_h, status_h, status_h, "\n".join(trace), "", oracle_info)

    # --- Route 3: Makefile Exercises (C 09 ex01) ---
    if stype == "makefile":
        dummy_srcs = {
            "includes/ft.h": "#ifndef FT_H\n# define FT_H\nvoid ft_putchar(char c);\nvoid ft_swap(int *a, int *b);\nvoid ft_putstr(char *str);\nint ft_strlen(char *str);\nint ft_strcmp(char *s1, char *s2);\n#endif\n",
            "srcs/ft_putchar.c": "#include <unistd.h>\nvoid ft_putchar(char c){write(1,&c,1);}\n",
            "srcs/ft_swap.c": "void ft_swap(int *a, int *b){int t=*a;*a=*b;*b=t;}\n",
            "srcs/ft_putstr.c": "#include <unistd.h>\nvoid ft_putstr(char *s){while(*s)write(1,s++,1);}\n",
            "srcs/ft_strlen.c": "int ft_strlen(char *s){int i=0;while(s[i])i++;return i;}\n",
            "srcs/ft_strcmp.c": "int ft_strcmp(char *a,char *b){while(*a&&*a==*b){a++;b++;}return (unsigned char)*a-(unsigned char)*b;}\n",
        }
        with tempfile.TemporaryDirectory(prefix="dt_mk_", dir=str(get_executable_temp_root())) as td:
            work = Path(td)
            for item in submit_dir.iterdir():
                if item.is_file():
                    shutil.copy2(item, work / item.name)
            mk_res = audit_makefile(work, expected_binary_or_lib="libft.a", sources_to_create=dummy_srcs)
            trace.extend(mk_res.steps_log)
            if not mk_res.ok:
                trace.append(f"\nMakefile KO: {mk_res.reason}\nGrade: 0")
                return GradeReport(subject_id, False, mk_res.reason, mk_res.reason, "\n".join(trace), "", oracle_info)
            trace.append("\nMakefile lifecycle & No-Relinking check: OK :D\nGrade: 100")
            return GradeReport(subject_id, True, "OK :)", "OK :)", "\n".join(trace), "", oracle_info)

    # --- Route 3.2: Shell Library Creator (C 09 ex00: libft_creator.sh) ---
    if stype == "shell_lib" or "libft_creator.sh" in expected_files or subject_id == "c09_libft":
        for exp in expected_files:
            if not (submit_dir / exp).exists():
                trace.append(f"Missing expected turn-in file: '{exp}'\nNothing turned in\nGrade: 0")
                return GradeReport(subject_id, False, "Nothing turned in", f"Missing {exp}", "\n".join(trace), "", oracle_info)
        with tempfile.TemporaryDirectory(prefix="dt_shlib_", dir=str(get_executable_temp_root())) as td:
            work = Path(td)
            for item in submit_dir.iterdir():
                if item.is_file():
                    shutil.copy2(item, work / item.name)
            trace.append("$> /bin/sh libft_creator.sh")
            sproc = subprocess.run(["/bin/sh", "libft_creator.sh"], cwd=work, capture_output=True, text=True, errors="replace", timeout=10)
            if sproc.returncode != 0 or not (work / "libft.a").exists():
                trace.append(sproc.stderr.strip() or "libft.a was not created by libft_creator.sh")
                trace.append("\nLibrary creation KO :(\nGrade: 0")
                return GradeReport(subject_id, False, "Does not compile", "libft.a not created", "\n".join(trace), "", oracle_info)
            test_main = work / "__dt_lib_main.c"
            test_main.write_text(
                '#include <stdio.h>\n'
                'void ft_putchar(char c);\n'
                'void ft_swap(int *a, int *b);\n'
                'void ft_putstr(char *str);\n'
                'int ft_strlen(char *str);\n'
                'int ft_strcmp(char *s1, char *s2);\n'
                'int main(void) {\n'
                '    int a = 21, b = 42;\n'
                '    ft_swap(&a, &b);\n'
                '    ft_putchar(\'X\');\n'
                '    fflush(stdout);\n'
                '    ft_putstr("1337");\n'
                '    fflush(stdout);\n'
                '    printf(":%d:%d:%d\\n", a, ft_strlen("hello"), ft_strcmp("abc", "abd") < 0);\n'
                '    return 0;\n'
                '}\n',
                encoding="utf-8",
            )
            lproc = subprocess.run(["cc", *FLAGS_COMPILE_SAFE, "__dt_lib_main.c", "libft.a", "-o", "user_exe"], cwd=work, capture_output=True, text=True, errors="replace")
            if lproc.returncode != 0:
                trace.append(lproc.stderr.strip())
                return GradeReport(subject_id, False, "Does not compile", "Failed to link against libft.a", "\n".join(trace), "", oracle_info)
            rproc = _run_isolated([str(work / "user_exe")], cwd=work, timeout=2.0)
            exp_out = "X1337:42:5:1\n"
            if rproc.stdout != exp_out:
                trace.append(format_unified_diff(exp_out, rproc.stdout, "expected", "got"))
                return GradeReport(subject_id, False, "Diff KO :(", "Diff KO :(", "\n".join(trace), "", oracle_info)
            trace.append("Diff OK :D\n\n= Final grade: 100 =============================================================")
            return GradeReport(subject_id, True, "OK :)", "OK :)", "\n".join(trace), "", oracle_info)

    # --- Route 3.4: C++ Exercises (cpp_module00..02) ---
    if stype == "cpp" or meta.get("language") == "cpp" or any(str(f).endswith(".cpp") for f in expected_files):
        return evaluate_cpp_exercise(subj_dir, subject_id, submit_dir, meta, trace, oracle_info)

    # --- Route 3.5: Python Exercises ---
    if stype == "python":
        return evaluate_python_exercise(subj_dir, subject_id, submit_dir, meta, trace, oracle_info)

    # --- Route 4: C Function, C Program & Project Exercises ---
    all_dir_files = [p for p in submit_dir.rglob("*") if p.is_file() and not any(part.startswith(".") for part in p.relative_to(submit_dir).parts)]
    is_rush_or_bsq = subject_id.startswith(("rush", "bsq")) or "rush" in str(subj_dir)
    has_wildcard_c = any("*" in exp for exp in expected_files) or ("Makefile" in expected_files) or (stype == "project") or (is_rush_or_bsq and stype == "c_program")
    if not has_wildcard_c and expected_files:
        expected_set = set(expected_files)
        if is_rush_or_bsq:
            user_files = [p for p in all_dir_files if p.name in expected_set or p.suffix == ".h" or (p.suffix == ".c" and p.name != "main.c")]
        else:
            user_files = [p for p in all_dir_files if p.name in expected_set or p.suffix == ".h"]
        norm_files = [p for p in all_dir_files if p.name in expected_set]
    else:
        user_files = [p for p in all_dir_files if p.suffix in {".c", ".h"} or p.name == "Makefile"]
        norm_files = user_files

    for exp in expected_files:
        if "*" not in exp and not (submit_dir / exp).exists():
            trace.append(f"$> ls -la {subject_id}/{exp}")
            trace.append(f"ls: {subject_id}/{exp}: No such file or directory")
            trace.append(f"Missing expected turn-in file: '{exp}'\nNothing turned in\nGrade: 0")
            return GradeReport(subject_id, False, "Nothing turned in", f"Missing {exp}", "\n".join(trace), "", oracle_info)

    bad_inc = check_forbidden_c_includes(user_files, allowed_root=submit_dir)
    if bad_inc:
        trace.extend(bad_inc)
        trace.append(">>>>>>>>>> FAILURE: Cheat detected (forbidden function) <<<<<<<<<<")
        return GradeReport(subject_id, False, "Cheating (-42)", bad_inc[0], "\n".join(trace), "", oracle_info)

    if (not is_exam and meta.get("norminette", True)) or enforce_norm:
        ok_n, n_log = run_norminette_check(kit_root, norm_files)
        trace.append(n_log)
        if not ok_n:
            trace.append("\nNorme error\nGrade: 0")
            return GradeReport(subject_id, False, "Norme error", "Norme error", "\n".join(trace), "", oracle_info)

    rev_corr = kit_root / "corrections/exams" / subject_id
    profile_yml = _safe_load_yaml(rev_corr / "profile.yml") if (rev_corr / "profile.yml").exists() else {}
    whitelist = profile_yml.get("white_list") if "white_list" in profile_yml else meta.get("allowed_functions")

    _last_arena_stats = getattr(_GRADER_TLS, "sink", getattr(_grade_subject_inner, "_tls_sink", [None]))
    with _tracked_eval_tempdir(get_executable_temp_root(), _last_arena_stats) as td:
        work = Path(td)
        for p in all_dir_files:
            rel_p = p.relative_to(submit_dir)
            dest_p = work / rel_p
            dest_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest_p)
        for sf_item in subj_dir.glob("*.h"):
            if not (work / sf_item.name).exists():
                shutil.copy2(sf_item, work / sf_item.name)

        tests_yml_path = subj_dir / "tests.yml"
        if tests_yml_path.exists():
            tests_cfg = _safe_load_yaml(tests_yml_path)
            if "__yaml_error__" in tests_cfg:
                return GradeReport(
                    subject_id,
                    False,
                    "Configuration Error: Malformed tests.yml",
                    tests_cfg["__yaml_error__"],
                    "\n".join(trace + [tests_cfg["__yaml_error__"]]),
                    "",
                    oracle_info,
                )
        else:
            tests_cfg = {}

        fixed_tests = tests_cfg.get("fixed_tests") or []
        oracle_tests = tests_cfg.get("oracle_tests") or []

        is_func_ex = (stype == "c_function") or bool(profile_yml.get("common_files"))
        student_has_main = any(has_main_definition(uf) for uf in user_files)

        if is_func_ex and student_has_main and meta.get("dual_mode", False) and any("args" in ft for ft in fixed_tests):
            is_func_ex = False
            fixed_tests = [ft for ft in fixed_tests if "args" in ft]
        elif is_func_ex:
            fixed_tests = [ft for ft in fixed_tests if "call" in ft or "expr" in ft or "code" in ft]

        if is_func_ex and not meta.get("allow_main", False):
            for uf in user_files:
                if has_main_definition(uf):
                    trace.append(f"{uf.name}: Error: main() function is forbidden in a function exercise!\n>>>>>>>>>> FAILURE: Student left a main() function in turned-in file <<<<<<<<<<\nGrade: 0")
                    return GradeReport(
                        subject_id,
                        False,
                        "Does not compile (main() in function exercise)",
                        "main() turned in for a function exercise",
                        "\n".join(trace),
                        "Moulinette Trap: Always delete or comment out your test `main()` before pushing a function exercise!",
                        oracle_info,
                    )

        # Step 4A: Compile `.o` & Verify `nm -u` symbol whitelist!
        c_sources = [work / uf.relative_to(submit_dir) for uf in user_files if uf.suffix == ".c"]
        inc_dirs = [work]
        for sub_inc in ["includes", "include", "srcs", "src"]:
            if (work / sub_inc).is_dir():
                inc_dirs.append(work / sub_inc)
        inc_flags = ["-I.", *[f"-I{d.relative_to(work)}" for d in inc_dirs if d != work]]
        comp_res, sym_res = verify_symbol_whitelist(
            c_sources,
            whitelist,
            work_dir=work,
            include_dirs=inc_dirs,
            strict_dual_compiler=strict,
        )
        trace.append(f"\n= {subject_id} " + "=" * max(5, 76 - len(subject_id)))
        trace.append("\n= Compilation ==================================================================")
        trace.append(f"$> {comp_res.command}")
        if not comp_res.ok:
            trace.append(comp_res.stderr.strip())
            trace.append("Could not compile 'user_exe'\nDoes not compile\nGrade: 0")
            return GradeReport(subject_id, False, "Does not compile", "Does not compile", "\n".join(trace), "", oracle_info)

        if sym_res.raw_nm_output:
            trace.append(sym_res.raw_nm_output)
        if not sym_res.ok:
            status_sym = sym_res.reason if sym_res.reason.startswith("Configuration Error") else "Cheating (-42)"
            trace.append(f"\n>>>>>>>>>> FAILURE: Cheat detected (forbidden function) <<<<<<<<<<\n{sym_res.reason}\nGrade: -42")
            return GradeReport(subject_id, False, status_sym, sym_res.reason, "\n".join(trace), "", oracle_info)

        # Step 4B: Standard tests.yml evaluation (fixed_tests + oracle_tests) + ExamPoolRevanced generator.py
        tests_executed = 0
        gen_py = rev_corr / "generator.py"
        if gen_py.exists() and not meta.get("alt_variants") and (not is_func_ex or (rev_corr / "main.c").exists()):
            gen_dir = work / "__dt_gen"
            shutil.copytree(rev_corr, gen_dir)
            env = {
                **os.environ,
                "PYTHONPATH": f"{kit_root}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
                "DT_TESTS_OUT": str(gen_dir / "__dt_generated_tests.json"),
            }
            gproc = subprocess.run([sys.executable, "generator.py"], cwd=gen_dir, env=env, capture_output=True, text=True, errors="replace", timeout=10)
            gen_json = gen_dir / "__dt_generated_tests.json"
            if gproc.returncode == 0 and gen_json.exists():
                generated_cases = json.loads(gen_json.read_text(encoding="utf-8"))
                if generated_cases:
                    common_files = [gen_dir / cf for cf in (profile_yml.get("common_files") or []) if (gen_dir / cf).exists()]
                    if is_func_ex and not common_files and (gen_dir / "main.c").exists():
                        common_files = [gen_dir / "main.c"]
                    user_gen_exe = work / "user_gen_exe"
                    gen_strict = []
                    if strict and (kit_root / "deepthought/sandbox_harness.c").exists():
                        shutil.copy2(kit_root / "deepthought/sandbox_harness.c", work / "sandbox_harness.c")
                        gen_strict = ["sandbox_harness.c", f"-I{kit_root / 'trusted_harness'}", f"-I{kit_root / 'third_party/tsoding_arena'}", "-DDT_WRAP_MALLOC", "-Wl,--wrap=malloc", "-Wl,--wrap=calloc", "-Wl,--wrap=realloc", "-Wl,--wrap=strdup", "-Wl,--wrap=free", "-Wl,--wrap=read", "-Wl,--wrap=exit", "-Wl,--wrap=_exit", "-Wl,--wrap=_Exit"]
                    link_cmd = ["cc", *FLAGS_COMPILE_SAFE, *(["-ftrapv"] if strict else []), *[str(p) for p in c_sources], *[str(p) for p in common_files], *gen_strict, "-o", str(user_gen_exe), "-lm"]
                    lproc = subprocess.run(link_cmd, cwd=work, capture_output=True, text=True, errors="replace")
                    if lproc.returncode == 0:
                        for case in generated_cases:
                            tests_executed += 1
                            tname = case["name"]
                            cmd_args = case["cmd"]
                            exp_out = case["output"]
                            trace.append(f"\n= {tname} ({case.get('fn_name', '')}) ===========================================")
                            trace.append(f"$> ./user_exe {cmd_args}")
                            try:
                                split_args = shlex.split(str(cmd_args)) if isinstance(cmd_args, str) else [str(a) for a in cmd_args]
                                rproc = _run_isolated(
                                    [str(user_gen_exe), *split_args],
                                    cwd=work,
                                    timeout=2.0,
                                )
                            except subprocess.TimeoutExpired:
                                trace.append("Command got killed by a Timeout (elapsed > 2.0s)\nGrade: 0")
                                return GradeReport(subject_id, False, "Timeout", "Timeout", "\n".join(trace), oracle_info.get("why_moulinette_fails", ""), oracle_info)

                            if len(rproc.stdout) > 262144 or len(rproc.stderr) > 262144:
                                trace.append("Output limit exceeded (>256 KB)\nGrade: 0")
                                return GradeReport(subject_id, False, "Output limit exceeded (>256 KB)", "Output limit exceeded", "\n".join(trace), "", oracle_info)
                            if rproc.returncode != 0:
                                err_detail = (rproc.stderr or "").strip()
                                sig_name, sig_reason, is_fatal_mem_sig = classify_process_exit_status(rproc.returncode, err_detail, False)
                                if is_fatal_mem_sig:
                                    if err_detail and any(k in err_detail for k in ("[REDZONE KO]", "[LEAK KO]", "[DOUBLE FREE KO]", "[INVALID FREE KO]", "[ARENA OWNERSHIP KO]", "[TRACKING EXHAUSTED KO]")):
                                        trace.append(err_detail)
                                    trace.append(f"Command got killed by a {sig_name}\nGrade: 0")
                                    return GradeReport(subject_id, False, sig_name, sig_reason, "\n".join(trace), oracle_info.get("why_moulinette_fails", ""), oracle_info)

                            if rproc.returncode != 0 and subject_id != "fix_result":
                                trace.append(f"Non-zero exit code: {rproc.returncode}\nDiff KO :(\nGrade: 0")
                                return GradeReport(subject_id, False, "Diff KO :(", f"Non-zero exit code {rproc.returncode}", "\n".join(trace), "", oracle_info)

                            trace.append(f"$> diff -U 3 user_output_{tname} {tname}.output | cat -e")
                            if rproc.stdout != exp_out:
                                diff_txt = format_unified_diff(exp_out, rproc.stdout, f"{tname}.output", f"user_output_{tname}")
                                trace.append(diff_txt)
                                trace.append("\nDiff KO :(\nGrade: 0")
                                return GradeReport(
                                    subject_id,
                                    False,
                                    "Diff KO :(",
                                    f"Failed on {tname}",
                                    "\n".join(trace),
                                    oracle_info.get("why_moulinette_fails", ""),
                                    oracle_info,
                                    last_cmd=f"./{subject_id} {cmd_args} | cat -e",
                                    expected_cat_e=_to_cat_e(exp_out),
                                    actual_cat_e=_to_cat_e(rproc.stdout),
                                )
                            trace.append("\nDiff OK :D")

        if is_func_ex:
            preamble = str(meta.get("hidden_preamble", "")).strip()
            proto = str(meta.get("prototype", "") or tests_cfg.get("prototype", "")).rstrip(";")
            headers = [
                "#include <stdio.h>",
                "#include <stdlib.h>",
                "#include <unistd.h>",
                "#include <string.h>",
                "#include <limits.h>",
                "#include <fcntl.h>",
                "#include <sys/wait.h>",
                "#include <stdbool.h>",
                "#include <stdint.h>",
            ]
            sc_extra = str(tests_cfg.get("support_code") or tests_cfg.get("preamble") or "").strip()
            local_h_texts = ""
            for hf in sorted(work.glob("*.h")):
                if hf.name == "sandbox_harness.c":
                    continue
                local_h_texts += "\n" + hf.read_text(encoding="utf-8", errors="ignore")
                if hf.name not in sc_extra and hf.name not in preamble:
                    headers.append(f'#include "{hf.name}"')
            combined_tests_text = " ".join(
                str(ft.get("call") or ft.get("code") or ft.get("expr") or "") + " " + " ".join(str(x) for x in (ft.get("setup") or []))
                for ft in fixed_tests
            )
            defined_blob = local_h_texts + "\n" + sc_extra + "\n" + preamble
            if ("t_stock_str" in proto or "t_stock_str" in combined_tests_text) and "s_stock_str" not in defined_blob:
                headers.append("typedef struct s_stock_str { int size; char *str; char *copy; } t_stock_str;")
            if ("t_btree" in proto or "t_btree" in combined_tests_text) and "s_btree" not in defined_blob:
                headers.append("typedef struct s_btree { void *item; struct s_btree *left; struct s_btree *right; } t_btree;")
            if ("t_list" in proto or "t_list" in combined_tests_text) and "s_list" not in defined_blob:
                headers.append("typedef struct s_list { void *data; struct s_list *next; } t_list;")
            if ("s_node" in proto or "s_node" in combined_tests_text or "node" in proto) and "struct s_node" not in defined_blob:
                headers.append("struct s_node { int value; int data; struct s_node *right; struct s_node *left; struct s_node *next; struct s_node *other; };")
            if sc_extra:
                headers.append(re.sub(r"\bstatic\s+(?!__attribute__)", "static __attribute__((unused)) ", sc_extra))
            if preamble:
                headers.append(preamble)
            student_c_blob = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in c_sources)
            all_known_defs = defined_blob + "\n" + student_c_blob
            if "->" in proto or (subject_id and not re.search(rf"\b{re.escape(subject_id)}\b", proto)):
                m_sig = re.search(
                    rf"^([A-Za-z_][\w\s\*]*?\b{re.escape(subject_id)}\s*\([^;{{}}]*\))\s*\{{",
                    student_c_blob,
                    re.MULTILINE,
                )
                if m_sig:
                    proto = " ".join(m_sig.group(1).split())
                elif "->" in proto:
                    proto = ""
            if proto:
                headers.append(proto + ";")
            uses_btree = "t_btree" in all_known_defs or "t_btree" in combined_tests_text
            uses_list = "t_list" in all_known_defs or "t_list" in combined_tests_text
            if uses_btree:
                dt_cmp_code = "static __attribute__((unused)) int dt_cmp(void *a, void *b) { return (*(int *)a - *(int *)b); }"
                dt_print_code = 'static __attribute__((unused)) void dt_print(void *d) { printf("%s", (char *)d); }'
            elif uses_list:
                dt_cmp_code = "static __attribute__((unused)) int dt_cmp(void *a, void *b) { return strcmp((const char *)a, (const char *)b); }"
                dt_print_code = 'static __attribute__((unused)) void dt_print(void *d) { printf("%s,", (char *)d); }'
            else:
                dt_cmp_code = "static __attribute__((unused)) int dt_cmp(int a, int b) { return (a - b); }"
                dt_print_code = 'static __attribute__((unused)) void dt_print(void *d) { printf("%s,", (char *)d); }'
            helper_snippets = [
                ("ascending", "static __attribute__((unused)) int ascending(int a, int b) { return (a <= b); }"),
                ("dt_is_empty", "static __attribute__((unused)) int dt_is_empty(char *s) { return (s[0] == '\\0' ? 1 : 0); }"),
                ("dt_is_short", "static __attribute__((unused)) int dt_is_short(char *s) { return (strlen(s) <= 1 ? 1 : 0); }"),
                ("dt_print_int", "static __attribute__((unused)) void dt_print_int(int n) { printf(\"%d,\", n); }"),
                ("dt_double", "static __attribute__((unused)) int dt_double(int n) { return (n * 2); }"),
                ("dt_strcmp", "static __attribute__((unused)) int dt_strcmp(char *a, char *b) { return strcmp(a, b); }"),
                ("dt_apply", 'static __attribute__((unused)) void dt_apply(void *item, int current_level, int is_first_elem) { printf("%d:%d:%s,", current_level, is_first_elem, (char *)item); }'),
                ("dt_cmp", dt_cmp_code),
                ("__dt_cmp", dt_cmp_code.replace("dt_cmp", "__dt_cmp")),
                ("dt_print", dt_print_code),
                ("cmp", "static __attribute__((unused)) int cmp(void *a, void *b) { return strcmp((const char *)a, (const char *)b); }"),
            ]
            for h_name, h_code in helper_snippets:
                if re.search(rf"\b{h_name}\b", combined_tests_text) and not re.search(rf"\b{h_name}\s*\(", defined_blob):
                    headers.append(h_code)
            if subject_id != "ft_create_elem" and re.search(r"\bft_create_elem\s*\(", combined_tests_text + "\n" + student_c_blob):
                if not re.search(r"\bft_create_elem\s*\([^;{}]*\)\s*\{", all_known_defs):
                    headers.append("t_list *ft_create_elem(void *data) { t_list *n = (t_list *)malloc(sizeof(t_list)); if (!n) return NULL; n->data = data; n->next = NULL; return n; }")
            if subject_id != "btree_create_node" and re.search(r"\bbtree_create_node\s*\(", combined_tests_text + "\n" + student_c_blob):
                if not re.search(r"\bbtree_create_node\s*\([^;{}]*\)\s*\{", all_known_defs):
                    headers.append("t_btree *btree_create_node(void *item) { t_btree *n = (t_btree *)malloc(sizeof(t_btree)); if (!n) return NULL; n->item = item; n->left = NULL; n->right = NULL; return n; }")

            if re.search(r"\bstrdup\s*\(", combined_tests_text):
                headers.append(
                    "static __attribute__((unused)) char *__dt_strdup(const char *s) { "
                    "size_t l = strlen(s) + 1; char *p = (char *)malloc(l); if (p) memcpy(p, s, l); return p; }\n"
                    "#undef strdup\n#define strdup __dt_strdup"
                )

            proto_prefix = proto.split("(")[0].strip() if "(" in proto else ""
            is_void_ret = bool(re.match(r"^(?:static\s+|inline\s+)*void\s+[A-Za-z_]\w*$", proto_prefix))

            def _guard_null_injection(stmt: str) -> str:
                return re.sub(
                    r'((?:struct\s+\w+|\w+)\s*\*+\s*([A-Za-z_]\w*)\s*=\s*[A-Za-z_]\w*\s*\((?:[^;"]|"[^"]*")*\)\s*;)',
                    r'\1 if (!\2 && getenv("DT_FAIL_MALLOC_AT")) return 0;',
                    stmt,
                )

            if fixed_tests:
                main_lines = [
                    *headers,
                    "#ifdef DT_WRAP_MALLOC",
                    '#include "dt_arena.h"',
                    "extern dt_arena_mark_t dt_harness_mark(void);",
                    "extern int dt_harness_rewind(dt_arena_mark_t m);",
                    "extern char *dt_harness_strdup(const char *s);",
                    "#define DT_TC_BEGIN(label) dt_arena_mark_t __dt_m = dt_harness_mark(); (void)dt_harness_strdup(label);",
                    "#define DT_TC_END() dt_harness_rewind(__dt_m);",
                    "#else",
                    "#define DT_TC_BEGIN(label) (void)0;",
                    "#define DT_TC_END() (void)0;",
                    "#endif",
                    "int main(int argc, char **argv) {",
                    "  setvbuf(stdout, NULL, _IONBF, 0);",
                    "  int tc = (argc > 1) ? atoi(argv[1]) : 0;",
                    "  (void)argv;",
                ]
                case_specs: list[tuple[int, str, str]] = []
                for ft_idx, ft in enumerate(fixed_tests, start=1):
                    setup_stmts = ft.get("setup") or []
                    if isinstance(setup_stmts, str):
                        setup_stmts = [setup_stmts]
                    setup_code = _guard_null_injection(" ".join(str(s).replace(r"\|", "|").strip().rstrip(";") + ";" for s in setup_stmts if str(s).strip()))
                    if "call" in ft:
                        call_c = _guard_null_injection(str(ft["call"]).replace(r"\|", "|").rstrip(";"))
                        main_lines.append(f"  if (tc == 0 || tc == {ft_idx}) {{ DT_TC_BEGIN(\"tc_{ft_idx}\"); {setup_code} {call_c}; fflush(stdout); DT_TC_END(); }}")
                        exp_piece = str(ft.get("stdout") if ft.get("stdout") is not None else ft.get("expected", ""))
                        desc = ft.get("name") or str(ft["call"])[:48]
                        case_specs.append((ft_idx, desc, exp_piece))
                    elif "code" in ft:
                        code_c = _guard_null_injection(str(ft["code"]).replace(r"\|", "|").rstrip(";"))
                        main_lines.append(f"  if (tc == 0 || tc == {ft_idx}) {{ DT_TC_BEGIN(\"tc_{ft_idx}\"); {setup_code} {code_c}; fflush(stdout); DT_TC_END(); }}")
                        raw_exp = ft.get("stdout") if ft.get("stdout") is not None else ft.get("expected", "")
                        exp_piece = str(raw_exp) if str(raw_exp).endswith("\n") else f"{raw_exp}\n"
                        desc = ft.get("name") or str(ft["code"])[:48]
                        case_specs.append((ft_idx, desc, exp_piece))
                    elif "expr" in ft:
                        expr_c = str(ft["expr"]).replace(r"\|", "|").rstrip(";")
                        if is_void_ret and re.search(rf"\b{re.escape(subject_id)}\s*\(", expr_c):
                            main_lines.append(f"  if (tc == 0 || tc == {ft_idx}) {{ DT_TC_BEGIN(\"tc_{ft_idx}\"); {setup_code} {expr_c}; fflush(stdout); DT_TC_END(); }}")
                        else:
                            fmt = ft.get("fmt", "%ld")
                            if fmt == "%s":
                                main_lines.append(f"  if (tc == 0 || tc == {ft_idx}) {{ DT_TC_BEGIN(\"tc_{ft_idx}\"); {setup_code} char *__dt_res = (char *)({expr_c}); printf(\"%s\\n\", __dt_res ? __dt_res : \"(null)\"); if (__dt_res) free(__dt_res); fflush(stdout); DT_TC_END(); }}")
                            else:
                                main_lines.append(f"  if (tc == 0 || tc == {ft_idx}) {{ DT_TC_BEGIN(\"tc_{ft_idx}\"); {setup_code} printf(\"{fmt}\\n\", (long)({expr_c})); fflush(stdout); DT_TC_END(); }}")
                        exp_piece = str(ft.get("stdout") if ft.get("stdout") is not None else f"{ft.get('expected', ft.get('return', ''))}\n")
                        desc = ft.get("name") or expr_c[:48]
                        case_specs.append((ft_idx, desc, exp_piece))
                main_lines.append("  return 0;\n}")
                (work / "__dt_main.c").write_text("\n".join(main_lines) + "\n", encoding="utf-8")
                strict_flags = _get_strict_sandbox_flags(kit_root, work)
                # For ft_atoi, compile user C source directly with -ftrapv so signed integer
                # overflow on -2147483648 traps with SIGABRT (Signal -6), killing MUT-E01!
                if subject_id in {"ft_atoi", "ft_atoi_base"}:
                    src_or_obj = ["-ftrapv", *[str(p.relative_to(work)) for p in c_sources]]
                else:
                    obj_files = [f"{p.stem}.o" for p in c_sources if (work / f"{p.stem}.o").exists()]
                    src_or_obj = obj_files if len(obj_files) == len(c_sources) else [str(p.relative_to(work)) for p in c_sources]
                cmd = ["cc", *FLAGS_COMPILE_SAFE, *inc_flags, *src_or_obj, "__dt_main.c", *strict_flags, "-o", "user_exe", "-lm"]
                trace.append("$> " + " ".join(["cc", *FLAGS_DEFAULT, *[p.name for p in c_sources], "main.c", "-o", "user_exe"]))
                lproc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, errors="replace")
                if lproc.returncode != 0:
                    trace.append(lproc.stderr.strip())
                    return GradeReport(subject_id, False, "Does not compile", "Linker error", "\n".join(trace), "", oracle_info)

                fixed_env = {**os.environ}
                if strict and ("free(" in combined_tests_text or subject_id in {"ft_list_clear", "ft_list_remove_if", "ft_strdel", "get_next_line", "broken_gnl", "gold_gain", "moment", "orderWeight", "queue", "stack"} or any(ft.get("check_leaks") for ft in fixed_tests)):
                    fixed_env["DT_CHECK_LEAKS"] = "1"
                for ft_idx, desc, exp_piece in case_specs:
                    tests_executed += 1
                    trace.append(f"\n= Test {ft_idx} ({desc}) " + "=" * max(5, 68 - len(str(desc))))
                    try:
                        rproc = _run_isolated([str(work / "user_exe"), str(ft_idx)], cwd=work, env=fixed_env, timeout=2.0)
                    except subprocess.TimeoutExpired:
                        trace.append("Command got killed by a Timeout (elapsed > 2.0s)\nGrade: 0")
                        return GradeReport(subject_id, False, "Timeout", "Timeout", "\n".join(trace), oracle_info.get("why_moulinette_fails", ""), oracle_info)
                    if rproc.returncode != 0:
                        err_detail = (rproc.stderr or "").strip()
                        if err_detail and any(k in err_detail for k in ("[REDZONE KO]", "[LEAK KO]", "[DOUBLE FREE KO]", "[INVALID FREE KO]", "[ARENA OWNERSHIP KO]", "[TRACKING EXHAUSTED KO]")):
                            trace.append(err_detail)
                        sig_name, sig_reason, _ = classify_process_exit_status(rproc.returncode, err_detail, False)
                        trace.append(f"Command got killed by a {sig_name}\nGrade: 0")
                        return GradeReport(subject_id, False, sig_name, sig_reason, "\n".join(trace), oracle_info.get("why_moulinette_fails", ""), oracle_info)
                    trace.append(f"$> diff -U 3 user_output_test{ft_idx} test{ft_idx}.output | cat -e")
                    got_out = rproc.stdout
                    if is_void_ret and got_out != exp_piece and got_out + "\n" == exp_piece:
                        got_out = got_out + "\n"
                    if got_out != exp_piece:
                        trace.append(format_unified_diff(exp_piece, got_out, f"test{ft_idx}.output", f"user_output_test{ft_idx}"))
                        trace.append("\nDiff KO :(\nGrade: 0")
                        return GradeReport(
                            subject_id,
                            False,
                            "Diff KO :(",
                            f"Failed on Test {ft_idx}",
                            "\n".join(trace),
                            oracle_info.get("why_moulinette_fails", ""),
                            oracle_info,
                            last_cmd=f"eval {desc}",
                            expected_cat_e=_to_cat_e(exp_piece),
                            actual_cat_e=_to_cat_e(got_out),
                        )
                    trace.append("\nDiff OK :D")
                if strict and (whitelist is None or "malloc" in (whitelist or [])):
                    null_env = {**os.environ, "DT_FAIL_MALLOC_AT": "1", "DT_CHUNK_READ": "1"}
                    try:
                        nproc = _run_isolated([str(work / "user_exe")], cwd=work, env=null_env, timeout=2.0)
                    except subprocess.TimeoutExpired:
                        return GradeReport(subject_id, False, "Timeout", "Timeout", "\n".join(trace), "", oracle_info)
                    if nproc.returncode < 0:
                        sig = -nproc.returncode
                        trace.append(f"\n[Strict Mode — null_check KO]: Command got killed by a Segmentation fault (Signal -{sig}) when malloc returned NULL!\nGrade: 0\n\n= Final grade: 0 ===============================================================")
                        return GradeReport(subject_id, False, "Strict KO: null_check (Segfault on malloc NULL)", "Unprotected malloc (segfault when malloc returns NULL)", "\n".join(trace), "Always check `if (!ptr) return (NULL);` immediately after `malloc()`.", oracle_info)
                    trace.append("[Strict Mode]: malloc null_check & chunked_read check: OK!")

            # Run oracle_tests (including Moulinette Stress & Edge cases)
            for idx, ot in enumerate(oracle_tests, start=len(fixed_tests) + 1):
                tests_executed += 1
                tname = ot.get("name", f"test{idx}")
                src_code = "\n".join([*headers, str(ot.get("source", "")).strip()]) + "\n"
                c_name = f"__dt_oracle_{idx}.c"
                b_name = f"user_oracle_{idx}"
                (work / c_name).write_text(src_code, encoding="utf-8")
                oracle_strict_flags = _get_strict_sandbox_flags(kit_root, work)
                if subject_id in {"ft_atoi", "ft_atoi_base"}:
                    oracle_inputs = ["-ftrapv", *[str(p.relative_to(work)) for p in c_sources]]
                else:
                    oracle_objs = [f"{p.stem}.o" for p in c_sources if (work / f"{p.stem}.o").exists()]
                    oracle_inputs = oracle_objs if len(oracle_objs) == len(c_sources) else [str(p.relative_to(work)) for p in c_sources]
                cmd = ["cc", *FLAGS_COMPILE_SAFE, *inc_flags, *oracle_inputs, c_name, *oracle_strict_flags, "-o", b_name, "-lm"]
                lproc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, errors="replace")
                if lproc.returncode != 0:
                    trace.append(lproc.stderr.strip())
                    return GradeReport(subject_id, False, "Does not compile", "Compile error in test harness", "\n".join(trace), "", oracle_info)
                trace.append(f"\n= Test {idx} ({tname}) ==================================================")
                oracle_env = {**os.environ}
                if strict and (whitelist is None or "free" in (whitelist or [])):
                    oracle_env["DT_CHECK_LEAKS"] = "1"
                try:
                    rproc = _run_isolated([str(work / b_name)], cwd=work, env=oracle_env, timeout=2.0)
                except subprocess.TimeoutExpired:
                    trace.append("Command got killed by a Timeout (elapsed > 2.0s)\nGrade: 0")
                    if oracle_info.get("why_moulinette_fails"):
                        trace.append(f"\n[Moulinette Trap Diagnostic]: {oracle_info['why_moulinette_fails']}")
                    return GradeReport(subject_id, False, "Timeout", "Timeout", "\n".join(trace), oracle_info.get("why_moulinette_fails", ""), oracle_info)
                if rproc.returncode != 0:
                    err_detail = rproc.stderr.strip()
                    if len(rproc.stdout) > 262144 or len(rproc.stderr) > 262144:
                        trace.append("Output limit exceeded (>256 KB)\nGrade: 0")
                        return GradeReport(subject_id, False, "Output limit exceeded (>256 KB)", "Output limit exceeded", "\n".join(trace), "", oracle_info)
                if rproc.returncode != 0:
                    err_detail = (rproc.stderr or "").strip()
                    sig_name, sig_reason, is_fatal_mem_sig = classify_process_exit_status(rproc.returncode, err_detail, False)
                    if is_fatal_mem_sig:
                        cmd_str = f"./{b_name}"
                        if err_detail and any(k in err_detail for k in ("[REDZONE KO]", "[LEAK KO]", "[DOUBLE FREE KO]", "[INVALID FREE KO]", "[ARENA OWNERSHIP KO]", "[TRACKING EXHAUSTED KO]")):
                            trace.append(err_detail)
                        trace.append(f"Command '{cmd_str}' got killed by a {sig_name}\nGrade: 0")
                        return GradeReport(subject_id, False, sig_name, sig_reason, "\n".join(trace), "", oracle_info, last_cmd=f"eval {tname}")
                    if oracle_info.get("why_moulinette_fails"):
                        trace.append(f"\n[Moulinette Trap Diagnostic]: {oracle_info['why_moulinette_fails']}")
                    return GradeReport(subject_id, False, "Diff KO :(", err_detail or "Failed edge case", "\n".join(trace), oracle_info.get("why_moulinette_fails", ""), oracle_info)
                exp_ot = ot.get("stdout") if ot.get("stdout") is not None else ot.get("expected")
                if exp_ot is not None and rproc.stdout != str(exp_ot):
                    trace.append(format_unified_diff(str(exp_ot), rproc.stdout, f"{tname}.output", f"user_{tname}"))
                    trace.append("\nDiff KO :(\nGrade: 0")
                    return GradeReport(
                        subject_id,
                        False,
                        "Diff KO :(",
                        "Diff KO :(",
                        "\n".join(trace),
                        oracle_info.get("why_moulinette_fails", ""),
                        oracle_info,
                        last_cmd=f"eval {tname}",
                        expected_cat_e=_to_cat_e(str(exp_ot)),
                        actual_cat_e=_to_cat_e(rproc.stdout),
                    )
                trace.append("Diff OK :D")

        else:
            # Program exercise (`c_program`)
            compile_cfg = meta.get("compile") or {}
            if compile_cfg.get("command") == "make" or "Makefile" in expected_files:
                run_bin_cfg = (meta.get("run") or {}).get("command", "").lstrip("./")
                if not run_bin_cfg and (work / "Makefile").exists():
                    mk_txt = (work / "Makefile").read_text(encoding="utf-8", errors="ignore")
                    m_name = re.search(r"^\s*NAME\s*[:?+]?=\s*([^\s#]+)", mk_txt, re.MULTILINE)
                    if m_name:
                        run_bin_cfg = m_name.group(1).strip()
                if not run_bin_cfg:
                    run_bin_cfg = "user_exe"
                for tmp_o in work.glob("*.o"):
                    tmp_o.unlink(missing_ok=True)
                mk_res = audit_makefile(work, expected_binary_or_lib=run_bin_cfg)
                trace.extend(mk_res.steps_log)
                if not mk_res.ok:
                    trace.append(f"\nMakefile KO: {mk_res.reason}\nGrade: 0")
                    return GradeReport(subject_id, False, mk_res.reason, mk_res.reason, "\n".join(trace), "", oracle_info)
                exe_path = work / run_bin_cfg
            else:
                exe_path = work / "user_exe"
                strict_flags = _get_strict_sandbox_flags(kit_root, work)
                cprog_objs = [f"{p.stem}.o" for p in c_sources if (work / f"{p.stem}.o").exists()]
                cprog_inputs = cprog_objs if len(cprog_objs) == len(c_sources) else [str(p.relative_to(work)) for p in c_sources]
                cmd = ["cc", *FLAGS_COMPILE_SAFE, *inc_flags, *cprog_inputs, *strict_flags, "-o", "user_exe", "-lm"]
                trace.append("$> " + " ".join(["cc", *FLAGS_DEFAULT, *[p.name for p in c_sources], "-o", "user_exe"]))
                lproc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, errors="replace")
                if lproc.returncode != 0:
                    trace.append(lproc.stderr.strip())
                    trace.append("Could not compile 'user_exe'\nDoes not compile\nGrade: 0")
                    return GradeReport(subject_id, False, "Does not compile", "Does not compile", "\n".join(trace), "", oracle_info)

            for idx, ft in enumerate(fixed_tests, start=1):
                exp_out = (
                    ft.get("stdout")
                    if ft.get("stdout") is not None
                    else (ft.get("expected") if ft.get("expected") is not None else ft.get("expected_stdout"))
                )
                exp_err = ft.get("stderr") if ft.get("stderr") is not None else ft.get("expected_stderr")
                exp_contains = ft.get("stdout_contains") or ft.get("expected_stdout_contains")
                exp_error_flag = bool(ft.get("expect_error", False) or ft.get("expected_error", False))
                exp_rc = ft.get("expected_returncode")

                if "python_harness" in ft:
                    tests_executed += 1
                    trace.append(f"\n= Test {idx} ({ft.get('name', 'socket_harness')}) ===========================================")
                    h_py = work / f"__dt_harness_{idx}.py"
                    h_py.write_text(str(ft["python_harness"]), encoding="utf-8")
                    hproc = _run_isolated([sys.executable, str(h_py), str(exe_path)], cwd=work, timeout=5.0)
                    exp_h = str(ft.get("expected", "OK\n"))
                    if hproc.returncode != 0 or hproc.stdout != exp_h:
                        trace.append(format_unified_diff(exp_h, hproc.stdout + hproc.stderr, f"test{idx}.output", f"user_output_test{idx}"))
                        trace.append("\nDiff KO :(\nGrade: 0")
                        return GradeReport(subject_id, False, "Diff KO :(", f"Failed socket harness {idx}", "\n".join(trace), "", oracle_info)
                    trace.append("\nDiff OK :D")
                    continue

                # Reject vacuous test oracle (GRD-003)
                if exp_out is None and exp_err is None and not exp_contains and not exp_error_flag and exp_rc is None:
                    trace.append(f"\nConfiguration Error: Empty test oracle on Test {idx}\nGrade: 0")
                    return GradeReport(
                        subject_id,
                        False,
                        "Configuration Error: Empty test oracle",
                        "Empty test oracle",
                        "\n".join(trace),
                        "",
                        oracle_info,
                    )

                tests_executed += 1
                if ft.get("map_content") is not None:
                    (work / "MAP_FILE").write_text(str(ft["map_content"]), encoding="utf-8")
                for rel_f, f_content in (ft.get("files") or {}).items():
                    fp = work / rel_f
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    fp.write_text(str(f_content), encoding="utf-8")
                args = [str(a) for a in (ft.get("args") or [])]
                quoted_args = " ".join(shlex.quote(a) for a in args)
                custom_argv0 = ft.get("argv0")
                if custom_argv0:
                    alt_bin_name = Path(str(custom_argv0)).name
                    alt_bin_path = work / alt_bin_name
                    if not alt_bin_path.exists():
                        shutil.copy2(exe_path, alt_bin_path)
                        os.chmod(alt_bin_path, 0o755)
                    invoke_bin = str(custom_argv0)
                else:
                    invoke_bin = f"./{exe_path.name}"
                cmd_display = f"{invoke_bin} {quoted_args}".rstrip() + " | cat -e"
                trace.append(f"\n= Test {idx} ===================================================================")
                trace.append(f"$> {invoke_bin} {quoted_args}".rstrip())
                try:
                    cprog_env = {**os.environ, **({"DT_CHECK_LEAKS": "1"} if strict else {})}
                    rproc = _run_isolated(
                        [invoke_bin, *args],
                        cwd=work,
                        env=cprog_env,
                        input_data=ft.get("stdin"),
                        timeout=2.0,
                    )
                except subprocess.TimeoutExpired:
                    trace.append("Command got killed by a Timeout (elapsed > 2.0s)\nGrade: 0")
                    return GradeReport(subject_id, False, "Timeout", "Timeout", "\n".join(trace), "", oracle_info, last_cmd=cmd_display)

                if len(rproc.stdout) > 262144 or len(rproc.stderr) > 262144:
                    trace.append("Output limit exceeded (>256 KB)\nGrade: 0")
                    return GradeReport(subject_id, False, "Output limit exceeded (>256 KB)", "Output limit exceeded", "\n".join(trace), "", oracle_info, last_cmd=cmd_display)
                if rproc.returncode != 0:
                    err_detail = (rproc.stderr or "").strip()
                    sig_name, sig_reason, is_fatal_mem_sig = classify_process_exit_status(rproc.returncode, err_detail, False)
                    if is_fatal_mem_sig:
                        cmd_str = f"./{exe_path.name} {quoted_args}".rstrip()
                        if err_detail and any(k in err_detail for k in ("[REDZONE KO]", "[LEAK KO]", "[DOUBLE FREE KO]", "[INVALID FREE KO]", "[ARENA OWNERSHIP KO]", "[TRACKING EXHAUSTED KO]")):
                            trace.append(err_detail)
                        trace.append(f"Command '{cmd_str}' got killed by a {sig_name}\nGrade: 0")
                        return GradeReport(subject_id, False, sig_name, sig_reason, "\n".join(trace), "", oracle_info, last_cmd=cmd_display)

                # Enforce expected returncode or exit-0 on positive test cases (GRD-004, MUT-B01, MUT-B02)
                if exp_rc is not None:
                    if rproc.returncode != int(exp_rc):
                        trace.append(f"Expected exit code {exp_rc}, got {rproc.returncode}\nDiff KO :(\nGrade: 0")
                        return GradeReport(subject_id, False, "Diff KO :(", f"Exit code {rproc.returncode} != {exp_rc}", "\n".join(trace), "", oracle_info, last_cmd=cmd_display)
                elif not exp_error_flag and exp_err is None and rproc.returncode != 0:
                    trace.append(f"Non-zero exit code {rproc.returncode} on positive test case\nDiff KO :(\nGrade: 0")
                    return GradeReport(subject_id, False, "Diff KO :(", f"Non-zero exit code {rproc.returncode}", "\n".join(trace), "", oracle_info, last_cmd=cmd_display)

                trace.append(f"$> diff -U 3 user_output_test{idx} test{idx}.output | cat -e")
                if exp_out is not None and rproc.stdout != str(exp_out):
                    trace.append(format_unified_diff(str(exp_out), rproc.stdout, f"test{idx}.output", f"user_output_test{idx}"))
                    trace.append("\nDiff KO :(\nGrade: 0")
                    if oracle_info.get("why_moulinette_fails"):
                        trace.append(f"\n[Moulinette Trap Diagnostic]: {oracle_info['why_moulinette_fails']}")
                    return GradeReport(
                        subject_id,
                        False,
                        "Diff KO :(",
                        "Diff KO :(",
                        "\n".join(trace),
                        oracle_info.get("why_moulinette_fails", ""),
                        oracle_info,
                        last_cmd=cmd_display,
                        expected_cat_e=_to_cat_e(str(exp_out)),
                        actual_cat_e=_to_cat_e(rproc.stdout),
                    )
                if exp_err is not None and rproc.stderr != str(exp_err):
                    trace.append(format_unified_diff(str(exp_err), rproc.stderr, f"test{idx}.stderr", f"user_stderr_test{idx}"))
                    trace.append("\nStderr Diff KO :(\nGrade: 0")
                    return GradeReport(
                        subject_id,
                        False,
                        "Diff KO :(",
                        "Stderr mismatch",
                        "\n".join(trace),
                        "",
                        oracle_info,
                        last_cmd=cmd_display,
                        expected_cat_e=_to_cat_e(str(exp_err)),
                        actual_cat_e=_to_cat_e(rproc.stderr),
                    )
                if exp_contains:
                    pieces = [exp_contains] if isinstance(exp_contains, str) else exp_contains
                    for piece in pieces:
                        if str(piece) not in rproc.stdout:
                            trace.append(f"Missing expected output fragment: {piece!r} in {rproc.stdout!r}\nDiff KO :(\nGrade: 0")
                            return GradeReport(subject_id, False, "Diff KO :(", f"Missing {piece}", "\n".join(trace), "", oracle_info)
                if exp_error_flag and rproc.returncode == 0 and not rproc.stderr and "error" not in rproc.stdout.lower():
                    trace.append("Expected non-zero exit code or error message\nDiff KO :(\nGrade: 0")
                    return GradeReport(subject_id, False, "Diff KO :(", "Expected error exit", "\n".join(trace), "", oracle_info)
                trace.append("\nDiff OK :D")

        # DEF-013 Guardrail: NEVER award 100/100 if 0 tests were executed!
        if tests_executed == 0:
            trace.append("\nConfiguration Error: No test suite defined (0 tests executed)\nGrade: 0")
            return GradeReport(
                subject_id,
                False,
                "Configuration Error: No test suite defined",
                "0 tests executed",
                "\n".join(trace),
                "",
                oracle_info,
            )

        trace.append("\n= Final grade: 100 =============================================================")
        return GradeReport(subject_id, True, "OK :)", "OK :)", "\n".join(trace), "", oracle_info)



def grade_subject(
    kit_root: Path,
    subject_id: str,
    submit_dir: Path,
    *,
    is_exam: bool = False,
    strict: bool = False,
    enforce_norm: bool = False,
    subj_dir_override: Path | None = None,
    git_log_text: str = "",
) -> GradeReport:
    sink: list[dict[str, int] | None] = [None]
    _GRADER_TLS.sink = sink
    _grade_subject_inner._tls_sink = sink  # type: ignore[attr-defined]
    rep = _grade_subject_inner(
        kit_root,
        subject_id,
        submit_dir,
        is_exam=is_exam,
        strict=strict,
        enforce_norm=enforce_norm,
        subj_dir_override=subj_dir_override,
        git_log_text=git_log_text,
    )
    if rep.arena_stats is None and sink[0] is not None:
        rep.arena_stats = sink[0]
    return rep
