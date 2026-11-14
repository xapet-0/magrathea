"""
deepthought.shell_evaluator
Authentic environment-isolated evaluator for Shell 00, Shell 01, Pre-Shell 00, Shell 02-13, and Shell Exams.
Provides real temporary Git repositories, real file trees, real tar/inode/symlink inspection,
differential reference-script oracle comparison, and automatic provisioning of Shell 00 ex07 (diff)
resources (`a` and `sw.diff`).
"""

from __future__ import annotations

import base64
import binascii
import contextlib
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
from typing import Any

import yaml


@dataclass
class ShellEvalResult:
    """Outcome and trace log produced by the declarative shell evaluator."""

    ok: bool
    reason: str
    trace_lines: list[str] = field(default_factory=list)
    trap_hint: str = ""


_SSH_KEY_PREFIXES: dict[str, str] = {
    "ssh-rsa": "AAAAB3NzaC1yc2",
    "ssh-ed25519": "AAAAC3NzaC1lZDI1NTE5",
    "ssh-dss": "AAAAB3NzaC1kc3",
    "ecdsa-sha2-nistp256": "AAAAE2VjZHNhLXNoYTItbmlzdHAyNT",
    "ecdsa-sha2-nistp384": "AAAAE2VjZHNhLXNoYTItbmlzdHAzOD",
    "ecdsa-sha2-nistp521": "AAAAE2VjZHNhLXNoYTItbmlzdHA1Mj",
    "sk-ssh-ed25519@openssh.com": "AAAAGnNrLXNzaC1lZDI1NTE5QG9wZW5zc2guY29t",
    "sk-ecdsa-sha2-nistp256@openssh.com": "AAAAInNrLWVjZHNhLXNoYTItbmlzdHAyNTZAb3BlbnNzaC5jb2",
}


def is_junk_dotfile(name: str) -> bool:
    """Return True for macOS Finder / editor swap junk files students leave behind."""
    return (
        name == ".DS_Store"
        or name.startswith("._")
        or name.startswith(".#")
        or name.endswith((".swp", ".swo", ".swn"))
    )


def _strip_shell_comments(script_text: str) -> str:
    """Return shell text with unquoted #... comments stripped while keeping quotes intact."""
    out: list[str] = []
    i = 0
    n = len(script_text)
    prev = "\n"
    while i < n:
        ch = script_text[i]
        if ch == "\\":
            out.append(script_text[i : i + 2])
            prev = script_text[i + 1] if i + 1 < n else ch
            i += 2
        elif ch == "#" and prev in ("", "\n", " ", "\t", ";", "|", "&", "("):
            while i < n and script_text[i] != "\n":
                i += 1
            prev = "\n"
        elif ch in ("'", '"'):
            quote = ch
            out.append(ch)
            i += 1
            while i < n and script_text[i] != quote:
                if quote == '"' and script_text[i] == "\\" and i + 1 < n:
                    out.append(script_text[i : i + 2])
                    i += 2
                else:
                    out.append(script_text[i])
                    i += 1
            if i < n:
                out.append(script_text[i])
                i += 1
            prev = quote
        else:
            out.append(ch)
            prev = ch
            i += 1
    return "".join(out)


def _check_forbidden_shell_rules(
    script_text: str,
    script_name: str,
    forbidden_commands: list[str],
    forbidden_patterns: list[str],
) -> ShellEvalResult | None:
    """Reject scripts using forbidden commands or hardcoded cheat patterns."""
    hits: list[str] = []
    if forbidden_commands:
        stripped = _strip_shell_comments_and_quotes(script_text)
        for cmd in forbidden_commands:
            c = str(cmd).strip()
            if not c:
                continue
            pat = rf"(?:^|[\s;|&(){{}}`])(?:(?:/[\w./-]+/)?{re.escape(c)})(?=$|[\s;|&(){{}}`])"
            if re.search(pat, stripped):
                hits.append(f"command '{c}'")
    if forbidden_patterns:
        no_comments = _strip_shell_comments(script_text)
        for raw_pat in forbidden_patterns:
            p = str(raw_pat)
            if not p:
                continue
            if p.startswith("re:"):
                if re.search(p[3:], no_comments, re.MULTILINE):
                    hits.append(f"pattern '{p}'")
            elif p in no_comments:
                hits.append(f"pattern '{p}'")
    if hits:
        msg = f"Cheating (-42): Forbidden construct in {script_name}: {', '.join(hits)}"
        return ShellEvalResult(False, "Cheating (-42)", [msg])
    return None


def _parse_octal_mode(raw: Any) -> int:
    """Parse octal permission specification from int or string (e.g. '0750', '750', 0o750)."""
    if isinstance(raw, int):
        return raw & 0o777
    text = str(raw).strip()
    if text.startswith(("0o", "0O")):
        text = text[2:]
    return int(text, 8) & 0o777


def _safe_rel_path(root: Path, raw_rel: str) -> Path:
    """Resolve raw_rel safely under root without following symlinks or allowing '..' escape."""
    rel_p = Path(raw_rel)
    if rel_p.is_absolute() or ".." in rel_p.parts:
        raise ValueError(f"Unsafe fixture path: {raw_rel!r}")
    root_res = root.resolve()
    # Resolve parent chain only when target may be a symlink itself
    cand = (root_res / rel_p).parent.resolve() / rel_p.name if rel_p.parts else root_res
    if cand != root_res and root_res not in cand.parents:
        raise ValueError(f"Path escapes working root: {raw_rel!r}")
    return root / rel_p


def _chmod_tree_writable(root: Path) -> None:
    """Restore owner rwx permissions across work trees so temp cleanup handles chmod tests."""
    for dirpath, dirnames, filenames in os.walk(root, topdown=False, followlinks=False):
        dp = Path(dirpath)
        for fn in filenames:
            fp = dp / fn
            if not fp.is_symlink():
                try:
                    os.chmod(fp, 0o600)
                except OSError:
                    pass
        for dn in dirnames:
            sub = dp / dn
            if not sub.is_symlink():
                try:
                    os.chmod(sub, 0o700)
                except OSError:
                    pass
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass


def _provision_case_files(
    root: Path,
    files_spec: dict[str, Any] | None,
    modes_spec: dict[str, Any] | None = None,
) -> None:
    """Create text fixtures, empty directories, symlinks, and initial chmod modes safely."""
    for rel_f, spec in (files_spec or {}).items():
        fp = _safe_rel_path(root, str(rel_f))
        fp.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(spec, dict):
            if spec.get("symlink") is not None:
                if fp.exists() or fp.is_symlink():
                    fp.unlink()
                os.symlink(str(spec["symlink"]), fp)
                continue
            if spec.get("dir"):
                fp.mkdir(parents=True, exist_ok=True)
            else:
                fp.write_text(str(spec.get("content", "")), encoding="utf-8")
            if spec.get("mode") is not None:
                os.chmod(fp, _parse_octal_mode(spec["mode"]))
        else:
            fp.write_text(str(spec), encoding="utf-8")
    for rel_m, mode_val in (modes_spec or {}).items():
        mp = _safe_rel_path(root, str(rel_m))
        if mp.exists() and not mp.is_symlink():
            os.chmod(mp, _parse_octal_mode(mode_val))


def _normalize_file_assertions(
    assertions_cfg: Any,
    absent_files: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Normalize dict/list file_assertions and absent_files into a uniform list of assertion specs."""
    out: list[dict[str, Any]] = []
    if isinstance(assertions_cfg, dict):
        for rel_p, spec in assertions_cfg.items():
            entry = dict(spec) if isinstance(spec, dict) else {"content": str(spec)}
            entry.setdefault("path", str(rel_p))
            out.append(entry)
    elif isinstance(assertions_cfg, list):
        for item in assertions_cfg:
            if isinstance(item, dict):
                out.append(dict(item))
    for rel_a in absent_files or []:
        out.append({"path": str(rel_a), "exists": False})
    return out


def _verify_file_assertions(
    work_dir: Path,
    assertions: list[dict[str, Any]],
    trace: list[str],
    ref_dir: Path | None = None,
) -> ShellEvalResult | None:
    """Verify post-execution filesystem side effects (existence, type, mode, size, symlink, content, oracle parity)."""
    for spec in assertions:
        raw_path = str(spec.get("path", "")).strip()
        if not raw_path:
            continue
        p = _safe_rel_path(work_dir, raw_path)
        exists_flag = p.exists() or p.is_symlink()
        want_exists = (
            not spec.get("absent", False)
            if "absent" in spec
            else bool(spec.get("exists", True))
        )
        if not want_exists:
            if exists_flag:
                return ShellEvalResult(
                    False,
                    "Diff KO :(",
                    trace
                    + [
                        f"Expected '{raw_path}' to be absent/deleted, but it still exists."
                    ],
                )
            continue
        if not exists_flag:
            return ShellEvalResult(
                False,
                "Diff KO :(",
                trace + [f"Expected '{raw_path}' to exist, but it is missing."],
            )

        want_type = spec.get("type")
        if want_type == "dir" and (not p.is_dir() or p.is_symlink()):
            return ShellEvalResult(
                False,
                "Wrong file type",
                trace + [f"Expected '{raw_path}' to be a directory."],
            )
        if want_type == "file" and (not p.is_file() or p.is_symlink()):
            return ShellEvalResult(
                False,
                "Wrong file type",
                trace + [f"Expected '{raw_path}' to be a regular file."],
            )
        if want_type == "symlink" and not p.is_symlink():
            return ShellEvalResult(
                False,
                "Wrong symlink",
                trace + [f"Expected '{raw_path}' to be a symlink."],
            )

        if spec.get("symlink_target") is not None:
            if not p.is_symlink() or os.readlink(p) != str(spec["symlink_target"]):
                actual_tgt = os.readlink(p) if p.is_symlink() else "not a symlink"
                return ShellEvalResult(
                    False,
                    "Wrong symlink",
                    trace
                    + [
                        f"Expected symlink '{raw_path} -> {spec['symlink_target']}', got {actual_tgt!r}."
                    ],
                )

        st = p.lstat()
        if spec.get("mode") is not None:
            want_mode = _parse_octal_mode(spec["mode"])
            actual_mode = st.st_mode & 0o777
            if actual_mode != want_mode:
                return ShellEvalResult(
                    False,
                    "Wrong permissions",
                    trace
                    + [
                        f"Expected '{raw_path}' permissions {oct(want_mode)}, got {oct(actual_mode)}."
                    ],
                )

        if spec.get("size") is not None and st.st_size != int(spec["size"]):
            return ShellEvalResult(
                False,
                "Wrong file size",
                trace
                + [
                    f"Expected '{raw_path}' size {int(spec['size'])} bytes, got {st.st_size} bytes."
                ],
            )

        if spec.get("content") is not None:
            actual_txt = p.read_text(encoding="utf-8", errors="replace")
            if actual_txt != str(spec["content"]):
                return ShellEvalResult(
                    False,
                    "Diff KO :(",
                    trace
                    + [
                        f"Expected '{raw_path}' content:\n{spec['content']!r}\nActual:\n{actual_txt!r}"
                    ],
                )

        if spec.get("content_contains") is not None:
            actual_txt = p.read_text(encoding="utf-8", errors="replace")
            reqs = (
                spec["content_contains"]
                if isinstance(spec["content_contains"], list)
                else [spec["content_contains"]]
            )
            for sub in reqs:
                if str(sub) not in actual_txt:
                    return ShellEvalResult(
                        False,
                        "Diff KO :(",
                        trace
                        + [
                            f"Expected '{raw_path}' to contain {sub!r}, got:\n{actual_txt!r}"
                        ],
                    )

        if spec.get("matches_oracle") and ref_dir is not None:
            rp = _safe_rel_path(ref_dir, raw_path)
            r_exists = rp.exists() or rp.is_symlink()
            if not r_exists:
                return ShellEvalResult(
                    False,
                    "Configuration Error: Oracle missing expected artifact",
                    trace + [f"Oracle missing '{raw_path}'."],
                )
            if p.is_symlink() != rp.is_symlink():
                return ShellEvalResult(
                    False,
                    "Wrong symlink",
                    trace + [f"Symlink mismatch vs oracle for '{raw_path}'."],
                )
            if p.is_symlink():
                if os.readlink(p) != os.readlink(rp):
                    return ShellEvalResult(
                        False,
                        "Wrong symlink",
                        trace
                        + [
                            f"'{raw_path}' symlink target {os.readlink(p)!r} != oracle {os.readlink(rp)!r}."
                        ],
                    )
            else:
                umode, rmode = p.stat().st_mode & 0o777, rp.stat().st_mode & 0o777
                if umode != rmode:
                    return ShellEvalResult(
                        False,
                        "Wrong permissions",
                        trace
                        + [
                            f"'{raw_path}' permissions {oct(umode)} != oracle {oct(rmode)}."
                        ],
                    )
                if p.is_file() and rp.is_file() and p.read_bytes() != rp.read_bytes():
                    return ShellEvalResult(
                        False,
                        "Diff KO :(",
                        trace + [f"'{raw_path}' content differs from oracle output."],
                    )
    return None


@contextlib.contextmanager
def _local_http_fixtures(routes: dict[str, Any] | None):
    """Run an ephemeral localhost HTTP server serving deterministic fixtures for offline curl tests."""
    if not routes:
        yield None
        return

    norm_routes: dict[str, tuple[int, str, bytes]] = {}
    for route, spec in routes.items():
        key = route if str(route).startswith("/") else f"/{route}"
        if isinstance(spec, dict):
            status = int(spec.get("status", 200))
            ctype = str(spec.get("content_type", "application/json; charset=utf-8"))
            body = str(spec.get("body", "")).encode("utf-8")
        else:
            status = 200
            ctype = "text/plain; charset=utf-8"
            body = str(spec).encode("utf-8")
        norm_routes[key] = (status, ctype, body)

    class _FixtureHandler(BaseHTTPRequestHandler):
        """HTTP request handler serving static fixtures for shell exercises."""

        def do_GET(self) -> None:  # noqa: N802
            """Serve static GET fixture responses."""
            path_only = self.path.split("?", 1)[0]
            if path_only in norm_routes:
                st, ctype, payload = norm_routes[path_only]
            else:
                st, ctype, payload = (404, "text/plain", b"Not Found")
            self.send_response(st)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Suppress default HTTP server stderr logging during fixture tests."""
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _strip_shell_comments_and_quotes(script_text: str) -> str:
    """Return POSIX shell code with comments removed and non-target quotes blanked."""
    out: list[str] = []
    i = 0
    n = len(script_text)
    prev = "\n"
    while i < n:
        ch = script_text[i]
        if ch == "\\":
            out.append(script_text[i : i + 2])
            prev = script_text[i + 1] if i + 1 < n else ch
            i += 2
        elif ch == "#" and prev in ("", "\n", " ", "\t", ";", "|", "&", "("):
            while i < n and script_text[i] != "\n":
                i += 1
            prev = "\n"
        elif ch in ("'", '"'):
            quote = ch
            i += 1
            start = i
            while i < n and script_text[i] != quote:
                if quote == '"' and script_text[i] == "\\" and i + 1 < n:
                    i += 2
                else:
                    i += 1
            inner = script_text[start:i]
            out.append("/dev/null" if inner == "/dev/null" else '""')
            if i < n:
                i += 1
            prev = quote
        else:
            out.append(ch)
            prev = ch
            i += 1
    return "".join(out)


def _has_active_stderr_null_redirect(script_text: str) -> bool:
    """Verify the shell script contains an unquoted, uncommented stderr -> /dev/null redirection."""
    stripped = _strip_shell_comments_and_quotes(script_text)
    return bool(
        re.search(
            r"(?:^|[\s;|&()])(?:(?:2\s*>>?|&>)\s*/dev/null|>\s*/dev/null[^;\n]*2\s*>&\s*1)",
            stripped,
        )
    )


def _validate_ssh_public_key(
    content: str, *, allow_unpadded: bool = False
) -> tuple[bool, str]:
    """Validate OpenSSH public key line structure, algorithm, prefix, and base64 payload."""
    lines = [ln.strip() for ln in content.strip().splitlines() if ln.strip()]
    if len(lines) != 1 or "PRIVATE KEY" in content:
        return (
            False,
            "id_rsa_pub must contain a single public SSH key line (never a private key).",
        )
    parts = lines[0].split()
    if len(parts) < 2:
        return False, "id_rsa_pub must contain '<key-type> <base64-key> [comment]'."
    key_type, key_blob = parts[0], parts[1]
    prefix = _SSH_KEY_PREFIXES.get(key_type)
    if not prefix:
        return False, f"Unsupported or invalid SSH public key algorithm {key_type!r}."
    if len(key_blob) < 32 or not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", key_blob):
        return False, "id_rsa_pub contains an invalid or truncated base64 key payload."
    if not key_blob.startswith(prefix):
        return (
            False,
            f"SSH key payload does not match OpenSSH wire header for {key_type}.",
        )
    if len(key_blob) % 4 != 0:
        if allow_unpadded:
            return True, "Valid SSH public key format."
        return False, "id_rsa_pub base64 payload length must be a valid multiple of 4."
    try:
        raw = base64.b64decode(key_blob.encode("ascii"), validate=True)
    except (binascii.Error, ValueError):
        return False, "id_rsa_pub base64 payload failed strict decoding."
    alg_bytes = key_type.encode("ascii")
    if (
        len(raw) < 4 + len(alg_bytes)
        or int.from_bytes(raw[:4], "big") != len(alg_bytes)
        or raw[4 : 4 + len(alg_bytes)] != alg_bytes
    ):
        return False, f"Decoded SSH wire blob does not match {key_type}."
    return True, "Valid SSH public key format."


def _init_temp_git_repo(repo_dir: Path) -> list[str]:
    """Create a realistic Git repository with 6 commits and .gitignore for git_commit.sh and git_ignore.sh."""
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Marvin",
        "GIT_AUTHOR_EMAIL": "marvin@1337.ma",
        "GIT_COMMITTER_NAME": "Marvin",
        "GIT_COMMITTER_EMAIL": "marvin@1337.ma",
    }
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, env=env, check=True)
    (repo_dir / ".gitignore").write_text(
        "*.o\n*~*\n.DS_Store\nignored_secret.txt\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", ".gitignore"], cwd=repo_dir, env=env, check=True)
    hashes: list[str] = []
    for i in range(1, 7):
        f = repo_dir / f"file_{i}.c"
        f.write_text(f"/* commit {i} */\n", encoding="utf-8")
        subprocess.run(["git", "add", f.name], cwd=repo_dir, env=env, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"Commit number {i}"],
            cwd=repo_dir,
            env=env,
            check=True,
        )
        h = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_dir, text=True, errors="replace"
        ).strip()
        hashes.append(h)
    (repo_dir / ".DS_Store").write_text("junk", encoding="utf-8")
    (repo_dir / "mywork.c~").write_text("backup", encoding="utf-8")
    (repo_dir / "ignored_secret.txt").write_text("secret", encoding="utf-8")
    return list(reversed(hashes[-5:]))


def evaluate_shell_exercise(
    kit_root: Path,
    subject_id: str,
    submit_dir: Path,
    meta: dict,
    *,
    strict: bool = False,
    subj_dir: Path | None = None,
) -> ShellEvalResult:
    """Evaluate a 42 shell exercise submission against fixture tests."""
    kit_root = kit_root.resolve()
    submit_dir = submit_dir.resolve()
    trace: list[str] = []
    expected_files = meta.get("expected_files", []) or []

    # Special case: MaRViN / forty_two filename with backslashes and quotes
    if subject_id in {"special_filename_MaRViN", "forty_two"}:
        is_corr_dir = (kit_root / "corrections").resolve() in [
            submit_dir,
            *submit_dir.parents,
        ]
        visible = [
            p
            for p in submit_dir.iterdir()
            if not p.name.startswith(".") or is_junk_dotfile(p.name)
        ]
        allowed_names = set(expected_files)
        if is_corr_dir:
            allowed_names.add(subject_id)
        found = [p for p in visible if p.is_file() and p.name in allowed_names]
        if not found:
            return ShellEvalResult(
                False, "Nothing turned in", ["Expected special filename not found."]
            )
        extra = [p.name for p in visible if p.name not in allowed_names]
        if extra:
            return ShellEvalResult(
                False,
                "Extraneous file(s) in turn-in directory",
                [f"Forbidden extra file(s) found: {', '.join(extra)}"],
            )
        raw_val = found[0].read_text(encoding="utf-8", errors="ignore")
        if raw_val == "42":
            return ShellEvalResult(
                True,
                "OK :)",
                [f"Found {found[0].name} containing exact '42' (2 bytes)"],
            )
        return ShellEvalResult(
            False,
            "Diff KO :(",
            [f"File must contain exact '42' (2 bytes), got {raw_val!r}."],
        )

    # 1. Verify expected files exist and no extra files (like leaving `a`, `sw.diff`, or `.DS_Store`/`.swp`!)
    visible = [
        p
        for p in submit_dir.iterdir()
        if (
            not p.name.startswith(".")
            or p.name == ".gitignore"
            or is_junk_dotfile(p.name)
        )
    ]
    for exp in expected_files:
        if not (submit_dir / exp).exists():
            return ShellEvalResult(
                False,
                "Nothing turned in",
                [f"Expected file '{exp}' is missing in submission directory."],
            )
    extra = [p.name for p in visible if p.name not in expected_files]
    if extra:
        hint = ""
        if subject_id == "diff" and ("a" in extra or "sw.diff" in extra):
            hint = "Moulinette Trap: You left 'a' or 'sw.diff' inside ex07/! Only 'b' may be turned in."
        return ShellEvalResult(
            False,
            "Extraneous file(s) in turn-in directory",
            [
                f"Forbidden extra file(s) found: {', '.join(extra)} (Only allowed: {', '.join(expected_files)})"
            ],
            trap_hint=hint,
        )

    # 2. Subject-specific & declarative fixed_tests evaluation
    from .grader import _run_isolated, get_executable_temp_root

    with tempfile.TemporaryDirectory(
        prefix="dt_shell_", dir=str(get_executable_temp_root(kit_root))
    ) as tmp:
        work = Path(tmp)
        try:
            res = _evaluate_shell_inside_workdir(
                kit_root=kit_root,
                subject_id=subject_id,
                submit_dir=submit_dir,
                meta=meta,
                subj_dir=subj_dir,
                work=work,
                expected_files=expected_files,
                trace=trace,
                run_isolated=_run_isolated,
            )
            return res
        finally:
            _chmod_tree_writable(work)


_PERM_SETUP_ASSERTIONS: list[dict[str, Any]] = [
    {"path": "box", "type": "dir", "mode": "0750"},
    {"path": "box/key", "type": "file", "mode": "0440", "size": 42},
    {"path": "shortcut", "type": "symlink", "symlink_target": "box/key"},
]


def _evaluate_shell_inside_workdir(
    *,
    kit_root: Path,
    subject_id: str,
    submit_dir: Path,
    meta: dict,
    subj_dir: Path | None,
    work: Path,
    expected_files: list[str],
    trace: list[str],
    run_isolated: Any,
) -> ShellEvalResult:
    """Execute shell evaluation inside an isolated temporary working directory."""
    _run_isolated = run_isolated

    # Locate subject tests.yml early so forbidden_commands / forbidden_patterns apply uniformly
    subj_candidates = []
    if subj_dir is not None and (subj_dir / "tests.yml").exists():
        subj_candidates.append(subj_dir / "tests.yml")
    subj_candidates.extend(
        list((kit_root / "subjects/exams").glob(f"{subject_id}/tests.yml"))
        + list((kit_root / "subjects/piscine").glob(f"*/{subject_id}/tests.yml"))
        + list((kit_root / "subjects/piscine").glob(f"*/{subject_id}.sh/tests.yml"))
    )
    t_cfg: dict[str, Any] = {}
    fixed_tests: list[dict[str, Any]] = []
    if subj_candidates:
        t_cfg = yaml.safe_load(subj_candidates[0].read_text(encoding="utf-8")) or {}
        fixed_tests = t_cfg.get("fixed_tests") or []

    # Handle static turned-in files (`shell_file` like kerberos, mobile-phone.ldif, diff)
    stype_lower = str(meta.get("type", "")).lower()

    # Check declarative forbidden_commands / forbidden_patterns on executable shell scripts
    script_file = submit_dir / expected_files[0]
    if stype_lower != "shell_file" and script_file.is_file():
        forbidden_cmds = list(meta.get("forbidden_commands") or []) + list(
            t_cfg.get("forbidden_commands") or []
        )
        forbidden_pats = list(meta.get("forbidden_patterns") or []) + list(
            t_cfg.get("forbidden_patterns") or []
        )
        if forbidden_cmds or forbidden_pats:
            raw_for_rules = script_file.read_text(encoding="utf-8", errors="ignore")
            cheat_res = _check_forbidden_shell_rules(
                raw_for_rules, script_file.name, forbidden_cmds, forbidden_pats
            )
            if cheat_res is not None:
                return cheat_res

    # --- Exam: perm_setup (box 0750, box/key 42B 0440, shortcut -> box/key) ---
    if subject_id == "perm_setup":
        shutil.copy2(submit_dir / "perm_setup.sh", work / "perm_setup.sh")
        proc = _run_isolated(["/bin/sh", "perm_setup.sh"], cwd=work, timeout=2.5)
        trace.append("$> /bin/sh perm_setup.sh && ls -ld box box/key shortcut")
        if proc.returncode != 0:
            return ShellEvalResult(
                False,
                f"Command exited with code {proc.returncode}",
                trace + [proc.stderr.strip()],
            )
        fail_res = _verify_file_assertions(work, _PERM_SETUP_ASSERTIONS, trace)
        if fail_res is not None:
            return fail_res
        return ShellEvalResult(True, "OK :)", trace)

    # --- Exam: git_audit (short commit hash and author name in a Git repo) ---
    if subject_id == "git_audit":
        _init_temp_git_repo(work)
        shutil.copy2(submit_dir / "git_audit.sh", work / "git_audit.sh")
        proc = _run_isolated(["/bin/sh", "git_audit.sh"], cwd=work, timeout=2.5)
        ref_full = subprocess.run(
            ["git", "log", "-n", "5", "--format=%h %an"],
            cwd=work,
            capture_output=True,
            text=True,
            errors="replace",
        )
        ref_one = subprocess.run(
            ["git", "log", "-n", "1", "--format=%h %an"],
            cwd=work,
            capture_output=True,
            text=True,
            errors="replace",
        )
        trace.append("$> /bin/sh git_audit.sh | cat -e")
        trace.append(proc.stdout.replace("\n", "$\n"))
        if proc.returncode != 0:
            return ShellEvalResult(
                False,
                f"Command exited with code {proc.returncode}",
                trace + [proc.stderr.strip()],
            )
        out_lines = [
            ln.strip() for ln in proc.stdout.strip().splitlines() if ln.strip()
        ]
        ref_lines = [
            ln.strip() for ln in ref_full.stdout.strip().splitlines() if ln.strip()
        ]
        # Verify output contains authentic short commit hash + author ("Marvin") from the test repo (reject static "echo OK" stubs!)
        if not out_lines or not all(ln in ref_lines for ln in out_lines):
            return ShellEvalResult(
                False,
                "Diff KO :(",
                trace
                + [
                    f"Expected short hash + author lines from git log (e.g. {ref_one.stdout.strip()!r}), got {proc.stdout!r}"
                ],
            )
        return ShellEvalResult(True, "OK :)", trace)

    # --- Exam: black_hole (redirect stderr to /dev/null and print OK\n) ---
    if subject_id == "black_hole":
        raw_bh = (submit_dir / "black_hole.sh").read_text(
            encoding="utf-8", errors="ignore"
        )
        if not _has_active_stderr_null_redirect(raw_bh):
            return ShellEvalResult(
                False,
                "Diff KO :(",
                trace
                + [
                    "black_hole.sh must actively redirect standard error (2>/dev/null) to /dev/null outside comments/quotes."
                ],
            )

    # --- Shell 00 ex00: z ---
    if subject_id == "z":
        content = (submit_dir / "z").read_text(encoding="utf-8", errors="replace")
        trace.append("$> cat -e z")
        trace.append(content.replace("\n", "$\n"))
        if content == "Z\n":
            return ShellEvalResult(True, "OK :)", trace)
        return ShellEvalResult(
            False,
            "Diff KO :(",
            trace + [f"Expected exact 'Z\\n' (2 bytes), got {content!r}"],
            trap_hint="Remember: `cat z` must display 'Z' followed by a newline (`echo Z > z`).",
        )

    # --- Shell 00 ex01: testShell00 ---
    if subject_id == "testShell00":
        tar_file = submit_dir / "testShell00.tar"
        trace.append("$> tar -tvf testShell00.tar")
        if not tarfile.is_tarfile(tar_file):
            return ShellEvalResult(
                False,
                "Invalid tar archive",
                trace + ["testShell00.tar is not a valid tar archive."],
            )
        with tarfile.open(tar_file, "r:*") as tf:
            members = [
                m for m in tf.getmembers() if m.name.lstrip("./") == "testShell00"
            ]
            if not members:
                return ShellEvalResult(
                    False,
                    "Missing testShell00 in tar",
                    trace + ["Archive does not contain 'testShell00'."],
                )
            m = members[0]
            mode = m.mode & 0o777
            trace.append(
                f"mode={oct(mode)} size={m.size} isreg={m.isfile()} issym={m.issym()}"
            )
            if not m.isfile() or m.issym():
                return ShellEvalResult(
                    False,
                    "Wrong file type",
                    trace + ["testShell00 must be a regular file, not a symlink."],
                )
            if m.size != 40:
                return ShellEvalResult(
                    False,
                    "Wrong file size",
                    trace + [f"Expected size 40 bytes, got {m.size} bytes."],
                )
            if mode != 0o455:
                return ShellEvalResult(
                    False,
                    "Wrong permissions",
                    trace
                    + [f"Expected permissions 0455 (-r--r-xr-x), got {oct(mode)}."],
                    trap_hint="r-- (4), r-x (5), r-x (5) -> chmod 455 testShell00",
                )
        return ShellEvalResult(True, "OK :)", trace)

    # --- Shell 00 ex02: exo2 ---
    if subject_id == "exo2":
        tar_file = submit_dir / "exo2.tar"
        trace.append("$> tar -tvf exo2.tar")
        if not tarfile.is_tarfile(tar_file):
            return ShellEvalResult(
                False,
                "Invalid tar archive",
                trace + ["exo2.tar is not a valid tar archive."],
            )
        with tarfile.open(tar_file, "r:*") as tf:
            by_name = {
                m.name.lstrip("./").rstrip("/"): m
                for m in tf.getmembers()
                if m.name.lstrip("./")
            }
            req = {
                "test0": ("dir", 0o715, None),
                "test1": ("file", 0o714, 4),
                "test2": ("dir", 0o504, None),
                "test3": ("file", 0o404, 1),
                "test4": ("file", 0o641, 2),
                "test5": ("file", 0o404, 1),
                "test6": ("sym", None, None),
            }
            for name, (kind, exp_mode, exp_size) in req.items():
                if name not in by_name:
                    return ShellEvalResult(
                        False,
                        "Missing entry in exo2.tar",
                        trace + [f"Missing '{name}' inside exo2.tar"],
                    )
                m = by_name[name]
                mode = m.mode & 0o777
                if kind == "dir" and not m.isdir():
                    return ShellEvalResult(
                        False, "Wrong type", trace + [f"{name} must be a directory"]
                    )
                if kind == "sym":
                    if not m.issym() or m.linkname.lstrip("./") != "test0":
                        return ShellEvalResult(
                            False,
                            "Wrong symlink",
                            trace
                            + [
                                f"test6 must be a symlink pointing to 'test0' (got {m.linkname!r})"
                            ],
                        )
                else:
                    if exp_mode is not None and mode != exp_mode:
                        return ShellEvalResult(
                            False,
                            "Wrong permissions",
                            trace
                            + [
                                f"{name}: expected mode {oct(exp_mode)}, got {oct(mode)}"
                            ],
                        )
                    eff_size = (
                        by_name[m.linkname.lstrip("./")].size
                        if (
                            m.islnk()
                            and m.size == 0
                            and m.linkname.lstrip("./") in by_name
                        )
                        else m.size
                    )
                    if exp_size is not None and eff_size != exp_size:
                        return ShellEvalResult(
                            False,
                            "Wrong size",
                            trace
                            + [f"{name}: expected size {exp_size}, got {eff_size}"],
                        )
            m3, m5 = by_name["test3"], by_name["test5"]
            work_resolved = work.resolve()
            for member in tf.getmembers():
                dest_path = (work_resolved / member.name.lstrip("/")).resolve()
                if (
                    not str(dest_path).startswith(str(work_resolved) + os.sep)
                    and dest_path != work_resolved
                ):
                    return ShellEvalResult(
                        False,
                        "Unsafe path in tar archive",
                        trace
                        + [f"Archive member '{member.name}' escapes working directory"],
                    )
            if hasattr(tarfile, "data_filter"):
                tf.extractall(work, filter="data")
            else:
                tf.extractall(work)
            if (work / "test3").exists() and (work / "test5").exists():
                if (work / "test3").stat().st_ino != (
                    work / "test5"
                ).stat().st_ino and not (m3.islnk() or m5.islnk()):
                    return ShellEvalResult(
                        False,
                        "Hard link missing",
                        trace
                        + [
                            "test3 and test5 must be hard-linked (`ln test3 test5`) so link count is 2!"
                        ],
                    )
        return ShellEvalResult(True, "OK :)", trace)

    # --- Shell 00 ex03: id_rsa_pub ---
    if subject_id == "id_rsa_pub":
        content = (submit_dir / "id_rsa_pub").read_text(
            encoding="utf-8", errors="ignore"
        )
        is_corr_dir = (kit_root / "corrections").resolve() in [
            submit_dir,
            *submit_dir.parents,
        ]
        trace.append("$> head -n 1 id_rsa_pub")
        ok_key, msg_key = _validate_ssh_public_key(content, allow_unpadded=is_corr_dir)
        if ok_key:
            return ShellEvalResult(True, "OK :)", trace + [msg_key])
        return ShellEvalResult(False, "Diff KO :(", trace + [msg_key])

    # --- Shell 00 ex04: midLS ---
    if subject_id.lower() == "midls":
        cmd_txt = (submit_dir / "midLS").read_text(encoding="utf-8").strip()
        trace.append(f"$> cat midLS\n{cmd_txt}")
        (work / ".hidden").write_text("x", encoding="utf-8")
        (work / "dir_sub").mkdir()
        (work / "alpha.txt").write_text("a", encoding="utf-8")
        (work / "beta.txt").write_text("b", encoding="utf-8")
        shutil.copy2(submit_dir / "midLS", work / "midLS")
        p_user = _run_isolated(["/bin/sh", "midLS"], cwd=work, timeout=2.5)
        p_ref = subprocess.run(
            ["ls", "-mpt"], cwd=work, capture_output=True, text=True, errors="replace"
        )
        trace.append(f"$> /bin/sh midLS\n{p_user.stdout}")
        if (
            ".hidden" in p_user.stdout
            or "dir_sub/" not in p_user.stdout
            or "," not in p_user.stdout
        ):
            return ShellEvalResult(
                False,
                "Diff KO :(",
                trace + [f"Expected output matching `ls -mpt`: {p_ref.stdout!r}"],
            )
        return ShellEvalResult(True, "OK :)", trace)

    # --- Shell 00 ex05: git_commit.sh ---
    if subject_id == "git_commit.sh":
        expected_hashes = _init_temp_git_repo(work)
        shutil.copy2(submit_dir / "git_commit.sh", work / "git_commit.sh")
        proc = _run_isolated(["/bin/sh", "git_commit.sh"], cwd=work, timeout=2.5)
        expected_out = "\n".join(expected_hashes) + "\n"
        trace.append("$> bash git_commit.sh | cat -e")
        trace.append(proc.stdout.replace("\n", "$\n"))
        if proc.returncode != 0 or proc.stdout != expected_out:
            return ShellEvalResult(
                False,
                "Diff KO :(",
                trace + [f"Expected:\n{expected_out}Got:\n{proc.stdout}"],
                trap_hint='Use `git log -n 5 --format="%H"` to print the last 5 full commit hashes.',
            )
        return ShellEvalResult(True, "OK :)", trace)

    # --- Shell 00 ex06: git_ignore.sh ---
    if subject_id == "git_ignore.sh":
        _init_temp_git_repo(work)
        shutil.copy2(submit_dir / "git_ignore.sh", work / "git_ignore.sh")
        proc = _run_isolated(["/bin/sh", "git_ignore.sh"], cwd=work, timeout=2.5)
        ref = subprocess.run(
            ["git", "ls-files", "--others", "--ignored", "--exclude-standard"],
            cwd=work,
            capture_output=True,
            text=True,
            errors="replace",
        )
        trace.append("$> bash git_ignore.sh | cat -e")
        trace.append(proc.stdout.replace("\n", "$\n"))
        if proc.returncode != 0 or sorted(proc.stdout.splitlines()) != sorted(
            ref.stdout.splitlines()
        ):
            return ShellEvalResult(
                False,
                "Diff KO :(",
                trace + [f"Expected:\n{ref.stdout}Got:\n{proc.stdout}"],
                trap_hint="Use `git ls-files --others --ignored --exclude-standard`.",
            )
        return ShellEvalResult(True, "OK :)", trace)

    # --- Shell 00 ex07: diff (Star Wars 'a' + 'sw.diff' -> 'b') ---
    if subject_id == "diff":
        diff_assets_dir = (
            subj_dir
            if (subj_dir is not None and (subj_dir / "sw.diff").exists())
            else (
                kit_root / "subjects/piscine/shell00/diff"
                if (kit_root / "subjects/piscine/shell00/diff/sw.diff").exists()
                else kit_root / "resources/shell00/ex07"
            )
        )
        a_file = diff_assets_dir / "a"
        sw_diff = diff_assets_dir / "sw.diff"
        user_b = submit_dir / "b"
        trace.append("$> diff a b > user.diff && diff -U 3 user.diff sw.diff")
        p_diff = subprocess.run(
            ["diff", str(a_file), str(user_b)],
            capture_output=True,
            text=True,
            errors="replace",
        )
        expected_diff = sw_diff.read_text(encoding="utf-8")
        if p_diff.stdout == expected_diff:
            trace.append(
                "Diff OK :D (Your file 'b' produces the exact Star Wars sw.diff!)"
            )
            return ShellEvalResult(True, "OK :)", trace)
        return ShellEvalResult(
            False,
            "Diff KO :(",
            trace
            + [
                f"`diff a b` did not match `sw.diff`.\nExpected diff:\n{expected_diff}\nGot diff:\n{p_diff.stdout}"
            ],
            trap_hint="Run `patch a -i sw.diff -o b` using the provided 'a' and 'sw.diff', and submit ONLY 'b'!",
        )

    # --- Shell 00 ex08: clean ---
    if subject_id == "clean":
        cmd_txt = (submit_dir / "clean").read_text(encoding="utf-8").strip()
        trace.append(f"$> cat clean\n{cmd_txt}")
        if ";" in cmd_txt.replace(r"\;", "") or "&&" in cmd_txt or "||" in cmd_txt:
            return ShellEvalResult(
                False,
                "Forbidden chaining in clean",
                trace
                + ["Subject states: Only one command is allowed, no ';' or '&&'."],
            )
        sub = work / "nested/deep"
        sub.mkdir(parents=True)
        t1 = work / "junk~"
        t2 = sub / "#temp#"
        keep1 = work / "#not_both"
        keep2 = sub / "valid.c"
        for f in [t1, t2, keep1, keep2]:
            f.write_text("data", encoding="utf-8")
        shutil.copy2(submit_dir / "clean", work / "clean")
        proc = _run_isolated(["/bin/sh", "clean"], cwd=work, timeout=2.5)
        (work / "clean").unlink(missing_ok=True)
        trace.append(f"$> /bin/sh clean\n{proc.stdout}")
        if t1.exists() or t2.exists():
            return ShellEvalResult(
                False,
                "Files were not deleted!",
                trace
                + ["`clean` did not delete '*~' and '#*#' files in subdirectories!"],
                trap_hint=r"Remember to group -o with parentheses: find . \( -name '*~' -o -name '#*#' \) -print -delete",
            )
        if not keep1.exists() or not keep2.exists():
            return ShellEvalResult(
                False,
                "Deleted valid files!",
                trace + ["`clean` deleted files that should NOT be deleted!"],
            )
        return ShellEvalResult(True, "OK :)", trace)

    # --- Shell 00 ex09: ft_magic ---
    if subject_id == "ft_magic":
        magic_file = submit_dir / "ft_magic"
        sample_42 = work / "sample42.bin"
        sample_42.write_bytes(b"A" * 41 + b"42" + b"Z" * 10)
        proc = subprocess.run(
            ["file", "-m", str(magic_file), str(sample_42)],
            capture_output=True,
            text=True,
            errors="replace",
        )
        trace.append(f"$> file -m ft_magic sample42.bin\n{proc.stdout.strip()}")
        if "42 file" in proc.stdout:
            return ShellEvalResult(True, "OK :)", trace)
        return ShellEvalResult(
            False,
            "Diff KO :(",
            trace
            + [
                "`file -m ft_magic` did not identify byte offset 41 ('42' at 42nd byte) as '42 file'."
            ],
            trap_hint="Format in ft_magic: `41 string 42 42 file` (0-indexed offset 41 is the 42nd byte!).",
        )

    # Handle static turned-in files (`shell_file` like kerberos, mobile-phone.ldif)
    if stype_lower == "shell_file":
        file_content = script_file.read_text(encoding="utf-8", errors="ignore")
        if not file_content.strip():
            return ShellEvalResult(
                False,
                "Nothing turned in (empty file)",
                [f"{script_file.name} is empty"],
            )
        if not fixed_tests:
            trace.append(
                f"Configuration Error: No test suite defined for {script_file.name}"
            )
            return ShellEvalResult(
                False, "Configuration Error: No test suite defined", trace
            )
        ft0 = fixed_tests[0]
        exp_out = (
            ft0.get("stdout")
            if ft0.get("stdout") is not None
            else (
                ft0.get("expected")
                if ft0.get("expected") is not None
                else ft0.get("expected_content")
            )
        )
        exp_regex = ft0.get("expected_regex")
        if exp_out is None and exp_regex is None:
            return ShellEvalResult(
                False, "Configuration Error: Empty test oracle", trace
            )
        if exp_out is not None and file_content != str(exp_out):
            trace.append(
                f"Expected content:\n{exp_out!r}\nActual content:\n{file_content!r}"
            )
            return ShellEvalResult(False, "Diff KO :(", trace)
        if exp_regex is not None and not re.search(
            str(exp_regex), file_content, re.MULTILINE
        ):
            trace.append(
                f"Expected regex {exp_regex!r} not matched in {file_content!r}"
            )
            return ShellEvalResult(False, "Diff KO :(", trace)
        cat_e_out = file_content.replace("\n", "$\n")
        trace.append(f"$> cat -e {script_file.name}\n{cat_e_out}")
        return ShellEvalResult(True, "OK :)", trace)

    # [DEF-005] 1. Reject empty or comment-only shell scripts immediately!
    raw_script = script_file.read_text(encoding="utf-8", errors="ignore")
    meaningful_lines = [
        ln.strip()
        for ln in raw_script.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if not meaningful_lines:
        trace.append(
            f"{script_file.name}: Error: script is empty (0 executable commands)!"
        )
        return ShellEvalResult(False, "Nothing turned in (empty script)", trace)

    # [DEF-005 & DEF-013] 2. Run all fixed_tests with STDOUT/STDERR diff & file_assertions verification
    if not fixed_tests:
        trace.append("Configuration Error: No test suite defined for shell exercise!")
        return ShellEvalResult(
            False, "Configuration Error: No test suite defined", trace
        )

    base_env = {
        **os.environ,
        "PATH": f"{kit_root / 'bin'}:/bin:/usr/bin:{os.environ.get('PATH', '')}",
        "FT_USER": os.environ.get("USER", "root"),
        "FT_LINE": "Hello 1337 World!",
        "FT_LINE1": "1",
        "FT_LINE2": "3",
        "FT_NBR1": '\\\x27?"\\"\x27\\',
        "FT_NBR2": "rcrdmddd",
    }

    oracle_raw = meta.get("golden_oracle", "")
    oracle_script_code = (
        oracle_raw.get("golden_code", "")
        if isinstance(oracle_raw, dict)
        else str(oracle_raw or "")
    )
    if not oracle_script_code.strip():
        for cand_corr in [
            kit_root / "corrections/piscine/shell01" / subject_id / script_file.name,
            kit_root / "corrections/piscine/shell00" / subject_id / script_file.name,
            kit_root / "corrections/exams" / subject_id / script_file.name,
        ]:
            if cand_corr.is_file():
                oracle_script_code = cand_corr.read_text(
                    encoding="utf-8", errors="ignore"
                )
                break

    for idx, ft in enumerate(fixed_tests, start=1):
        case_work = work / f"case_{idx}"
        case_work.mkdir(parents=True, exist_ok=True)
        file_assertions = _normalize_file_assertions(
            ft.get("file_assertions"), ft.get("absent_files")
        )
        has_custom_files = bool(
            ft.get("files") or ft.get("file_modes") or file_assertions
        )
        if has_custom_files:
            bin_dir = work / f"__bin_{idx}"
            bin_dir.mkdir(parents=True, exist_ok=True)
            runner_script = bin_dir / script_file.name
        else:
            runner_script = case_work / script_file.name
        shutil.copy2(script_file, runner_script)
        os.chmod(runner_script, 0o755)

        _provision_case_files(case_work, ft.get("files"), ft.get("file_modes"))

        ft_env = ft.get("env") or {}
        case_env = {
            **base_env,
            "DT_SANDBOX_IFCONFIG": "1",
            **{k: str(v) for k, v in ft_env.items()},
        }
        run_cwd = case_work
        if (
            "PWD" in ft_env
            and not has_custom_files
            and Path(str(ft_env["PWD"])).is_dir()
        ):
            run_cwd = Path(str(ft_env["PWD"]))

        args = [str(a) for a in (ft.get("args") or [])]
        stdin_data = ft.get("stdin")
        exp_exit = int(ft.get("exit_code", 0))
        exp_stdout = (
            ft.get("stdout") if ft.get("stdout") is not None else ft.get("expected")
        )
        exp_stderr = (
            ft.get("stderr")
            if ft.get("stderr") is not None
            else ft.get("expected_stderr")
        )
        stdout_contains = ft.get("stdout_contains")

        need_stdout_oracle = (
            (exp_stdout is None or exp_stdout == "")
            and not stdout_contains
            and bool(oracle_script_code.strip())
            and (
                not ft.get("expect_empty", False)
                or subject_id in {"print_groups.sh", "print_groups"}
            )
        )
        need_fs_oracle = bool(oracle_script_code.strip()) and any(
            bool(a.get("matches_oracle")) for a in file_assertions
        )

        with _local_http_fixtures(ft.get("http_routes")) as http_url:
            if http_url:
                case_env["DT_HTTP_URL"] = http_url
                case_env["DT_HTTP_PORT"] = http_url.rsplit(":", 1)[1]

            ref_cwd: Path | None = None
            if need_stdout_oracle or need_fs_oracle:
                ref_work = work / f"ref_{idx}"
                ref_work.mkdir(parents=True, exist_ok=True)
                _provision_case_files(ref_work, ft.get("files"), ft.get("file_modes"))
                if has_custom_files:
                    ref_bin_dir = work / f"__ref_bin_{idx}"
                    ref_bin_dir.mkdir(parents=True, exist_ok=True)
                    ref_script = ref_bin_dir / script_file.name
                else:
                    ref_script = ref_work / script_file.name
                ref_script.write_text(oracle_script_code, encoding="utf-8")
                os.chmod(ref_script, 0o755)
                ref_cwd = run_cwd if run_cwd != case_work else ref_work
                ref_proc = subprocess.run(
                    ["/bin/sh", str(ref_script), *args],
                    cwd=ref_cwd,
                    env=case_env,
                    input=stdin_data if stdin_data is not None else "",
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=5,
                )
                if need_stdout_oracle:
                    exp_stdout = ref_proc.stdout
                    exp_exit = ref_proc.returncode

            before_entries = (
                {p.name for p in run_cwd.iterdir()}
                if subject_id == "black_hole"
                else set()
            )
            try:
                proc = _run_isolated(
                    ["/bin/sh", str(runner_script), *args],
                    cwd=run_cwd,
                    env=case_env,
                    input_data=stdin_data if stdin_data is not None else "",
                    timeout=2.5,
                )
            except subprocess.TimeoutExpired:
                trace.append("Command got killed by a Timeout (elapsed > 2.5s)")
                return ShellEvalResult(False, "Timeout", trace)

        trace.append(f"$> /bin/sh {script_file.name} {' '.join(args)}".rstrip())
        if proc.returncode != exp_exit:
            trace.append(proc.stderr.strip())
            return ShellEvalResult(
                False,
                f"Command exited with code {proc.returncode} (expected {exp_exit})",
                trace,
            )
        if exp_stderr is not None and proc.stderr != str(exp_stderr):
            trace.append(
                f"Expected STDERR:\n{exp_stderr!r}\nActual STDERR:\n{proc.stderr!r}"
            )
            return ShellEvalResult(False, "Diff KO :(", trace)
        if subject_id == "black_hole":
            if proc.stderr:
                trace.append(f"Expected empty STDERR, got:\n{proc.stderr!r}")
                return ShellEvalResult(False, "Diff KO :(", trace)
            leftovers = sorted({p.name for p in run_cwd.iterdir()} - before_entries)
            if leftovers:
                trace.append(
                    f"Script left temporary files behind: {', '.join(leftovers)}"
                )
                return ShellEvalResult(False, "Diff KO :(", trace)

        if subject_id in {"bg_pid", "find_proc", "ps_user"}:
            lines = [
                ln.strip() for ln in proc.stdout.strip().splitlines() if ln.strip()
            ]
            if not lines or not all(ln.isdigit() and int(ln) > 0 for ln in lines):
                trace.append(f"Expected valid numeric PID(s), got:\n{proc.stdout!r}")
                return ShellEvalResult(False, "Diff KO :(", trace)
        elif stdout_contains:
            for sub_s in stdout_contains:
                if str(sub_s) not in proc.stdout:
                    trace.append(
                        f"Expected STDOUT to contain {sub_s!r}, got:\n{proc.stdout!r}"
                    )
                    return ShellEvalResult(False, "Diff KO :(", trace)
        elif exp_stdout is not None and proc.stdout != str(exp_stdout):
            stdout_ok = False
            # Allow order-independent line comparison for find-based exercises where tmpfs inode order varies
            if "find" in subject_id or subject_id in {
                "basename_sh",
                "clean_temp",
                "tree_walk",
                "inc_backup",
            }:
                stdout_ok = sorted(proc.stdout.splitlines()) == sorted(
                    str(exp_stdout).splitlines()
                )
            # For count_files.sh, allow optional leading whitespace from BSD/GNU `wc -l`
            elif (
                subject_id in {"count_files.sh", "count_files"}
                and proc.stdout.strip() == str(exp_stdout).strip()
                and proc.stdout.endswith("\n")
            ):
                stdout_ok = True
            if not stdout_ok:
                trace.append(
                    f"Expected STDOUT:\n{exp_stdout!r}\nActual STDOUT:\n{proc.stdout!r}"
                )
                return ShellEvalResult(False, "Diff KO :(", trace)
        elif (
            exp_stdout is None
            and exp_stderr is None
            and not file_assertions
            and not proc.stdout.strip()
            and subject_id
            not in {"perm_setup", "clean", "exo2", "testShell00", "MAC.sh"}
        ):
            trace.append("Script produced empty STDOUT!")
            return ShellEvalResult(False, "Diff KO :( (empty output)", trace)

        if file_assertions:
            fail_fs = _verify_file_assertions(
                run_cwd, file_assertions, trace, ref_dir=ref_cwd
            )
            if fail_fs is not None:
                return fail_fs

    return ShellEvalResult(True, "OK :)", trace)
