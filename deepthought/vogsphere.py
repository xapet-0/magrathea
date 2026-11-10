#!/usr/bin/env python3
"""
Local Vogsphere bare Git repository manager for authentic 42 / 1337 ExamShell & Moulinette workflow.
Ensures grading evaluates commits pushed to the bare Vogsphere repository (`vogsphere.git` or
`vogsphere/<section>/<exercise>.git`) and provides authentic Vogsphere pre-receive hooks.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple


def _resolve_paths(path_arg: Path) -> Tuple[Path, Path]:
    path_arg = Path(path_arg).resolve()
    if path_arg.name in ("vogsphere.git", ".vogsphere.git") or path_arg.suffix == ".git":
        return path_arg.parent, path_arg
    if (path_arg / ".vogsphere.git").exists():
        return path_arg, path_arg / ".vogsphere.git"
    return path_arg, path_arg / "vogsphere.git"


_VOGSPHERE_HOOK_SH = """\
#!/bin/sh
UUID="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || uuidgen 2>/dev/null || printf '%s' "$(od -x /dev/urandom | head -1)")"
NOW="$(date '+%Y-%m-%d %H:%M:%S')"
echo "vogsphere: (INFO) Transaction ID : $UUID"
echo "vogsphere: (INFO) Please mention this ID in any ticket you create concerning this transaction"
echo "vogsphere: (INFO) This transaction has been started at $NOW, server time."
echo "vogsphere: (INFO) Rights will be determined using this time, so do NOT cut the connection."
echo "vogsphere: (INFO) You have read and write rights on this repository"
"""


def _install_vogsphere_hook(bare_repo: Path) -> None:
    """Install the authentic Vogsphere pre-receive hook into bare_repo/hooks/."""
    hooks_dir = bare_repo / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    pre_receive = hooks_dir / "pre-receive"
    pre_receive.write_text(_VOGSPHERE_HOOK_SH, encoding="utf-8")
    pre_receive.chmod(0o755)


def _is_temp_or_protected_host_home(target_path: Path, home_dir: Path) -> bool:
    """Return True if symlink creation in home_dir should be skipped to protect host $HOME or temporary workspaces."""
    if os.environ.get("DT_SKIP_HOME_SYMLINKS") == "1":
        return True
    resolved_str = str(target_path.resolve())
    if resolved_str.startswith(("/tmp/", "/var/tmp/", "/private/tmp/")):
        return True
    if "/test-homes/" in resolved_str or "/dt_int_" in resolved_str or "/dt_vog_" in resolved_str:
        if "test-homes" not in str(home_dir):
            return True
    # Protect real host /home/xapet from development workspace (/Downloads/) symlink overrides
    try:
        if str(home_dir.resolve()) == "/home/xapet" and "/Downloads/" in resolved_str:
            return True
    except OSError:
        pass
    return False


def _ensure_rendu_symlink(rendu_dir: Path) -> None:
    """Create ~/rendu -> rendu_dir symlink only for non-temporary workspaces and isolated/production homes."""
    home_dir = Path.home()
    if _is_temp_or_protected_host_home(rendu_dir, home_dir):
        return
    home_rendu = home_dir / "rendu"
    try:
        if home_rendu.is_symlink():
            if home_rendu.resolve() != rendu_dir.resolve():
                home_rendu.unlink()
                home_rendu.symlink_to(rendu_dir)
        elif not home_rendu.exists():
            home_rendu.symlink_to(rendu_dir)
    except OSError:
        pass


def init_vogsphere(path_arg: Path, clean: bool = False) -> Dict[str, str]:
    """Initialize a bare Vogsphere repository and clone it into rendu/."""
    workspace_root, bare_repo = _resolve_paths(path_arg)
    rendu_dir = workspace_root / "rendu"

    if clean:
        if bare_repo.exists():
            shutil.rmtree(bare_repo)
        if rendu_dir.exists():
            shutil.rmtree(rendu_dir)
    elif bare_repo.exists() and (bare_repo / "HEAD").exists() and (rendu_dir / ".git").exists():
        subprocess.run(["git", "config", "user.name", "Exam 42"], cwd=str(rendu_dir), check=False)
        subprocess.run(["git", "config", "user.email", "exam-no-reply@42.fr"], cwd=str(rendu_dir), check=False)
        subprocess.run(["git", "config", "push.default", "current"], cwd=str(rendu_dir), check=False)
        subprocess.run(["git", "config", "push.autoSetupRemote", "true"], cwd=str(rendu_dir), check=False)
        _install_vogsphere_hook(bare_repo)
        _ensure_rendu_symlink(rendu_dir)
        return {"bare_repo": str(bare_repo), "rendu_dir": str(rendu_dir)}

    bare_repo.parent.mkdir(parents=True, exist_ok=True)
    if not (bare_repo.exists() and (bare_repo / "HEAD").exists()):
        subprocess.run(
            ["git", "init", "--bare", str(bare_repo)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    if not (rendu_dir.exists() and (rendu_dir / ".git").exists()):
        if rendu_dir.exists():
            shutil.rmtree(rendu_dir)
        subprocess.run(
            ["git", "clone", str(bare_repo), str(rendu_dir)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    subprocess.run(["git", "config", "user.name", "Exam 42"], cwd=str(rendu_dir), check=True)
    subprocess.run(["git", "config", "user.email", "exam-no-reply@42.fr"], cwd=str(rendu_dir), check=True)
    subprocess.run(["git", "config", "push.default", "current"], cwd=str(rendu_dir), check=False)
    subprocess.run(["git", "config", "push.autoSetupRemote", "true"], cwd=str(rendu_dir), check=False)

    _install_vogsphere_hook(bare_repo)
    _ensure_rendu_symlink(rendu_dir)
    return {"bare_repo": str(bare_repo), "rendu_dir": str(rendu_dir)}


def ensure_home_workspace_symlinks(kit_root: Path) -> None:
    """Create ~/piscine -> kit_root/workspace/piscine and ~/exams -> kit_root/workspace/exams
    symlinks in $HOME so students on WSL (/mnt/c/...) always have short, clean ~/piscine/<mod>/<ex>
    paths that never wrap across terminal lines, while also pre-creating exercise directories
    with subject.en.txt inside each folder for direct command-line reading (`cd` + `cat subject.en.txt`).
    """
    ws_piscine = (kit_root / "workspace" / "piscine").resolve()
    ws_exams = (kit_root / "workspace" / "exams").resolve()
    ws_piscine.mkdir(parents=True, exist_ok=True)
    ws_exams.mkdir(parents=True, exist_ok=True)
    home_dir = Path.home()
    if _is_temp_or_protected_host_home(kit_root, home_dir):
        return
    for link_name, target_dir in (("piscine", ws_piscine), ("exams", ws_exams)):
        home_link = home_dir / link_name
        try:
            if home_link.is_symlink():
                if home_link.resolve() != target_dir:
                    home_link.unlink()
                    home_link.symlink_to(target_dir)
            elif not home_link.exists():
                home_link.symlink_to(target_dir)
        except OSError:
            pass


def provision_module_or_exercise_folders(kit_root: Path, mod_or_rel: Optional[str] = None) -> None:
    """Pre-create workspace directories and copy subject.en.txt (plus helper .h files) into each
    exercise folder so a student can `cd` into any exercise folder from the terminal and read
    `subject.en.txt` BEFORE running `init`.
    """
    ensure_home_workspace_symlinks(kit_root)
    subj_root = kit_root / "subjects"
    ws_root = kit_root / "workspace"
    targets: list[Path] = []
    if mod_or_rel:
        clean = mod_or_rel.strip("/")
        cand = subj_root / clean
        if cand.is_dir():
            if (cand / "subject.en.txt").is_file():
                targets.append(cand)
            else:
                targets.extend(p.parent for p in cand.rglob("subject.en.txt"))
    else:
        targets.extend(p.parent for p in (subj_root / "piscine").rglob("subject.en.txt"))

    for sdir in targets:
        rel = sdir.relative_to(subj_root)
        wdir = ws_root / rel
        wdir.mkdir(parents=True, exist_ok=True)
        for doc_name in ("subject.en.txt", "examples.txt"):
            src_doc = sdir / doc_name
            dst_doc = wdir / doc_name
            if src_doc.is_file() and not dst_doc.exists():
                shutil.copy2(src_doc, dst_doc)
        for h_file in sdir.glob("*.h"):
            dst_h = wdir / h_file.name
            if not dst_h.exists():
                shutil.copy2(h_file, dst_h)


def init_exercise_vogsphere_repo(
    kit_root: Path,
    rel_subj: str,
    work_dir: Path,
    login: str = "student",
) -> Dict[str, str]:
    """Initialize a per-exercise bare Vogsphere Git repository at `vogsphere/<rel_subj>.git`
    and connect `work_dir` (`workspace/<rel_subj>`) as a Git working tree with `origin` pointing
    to the bare Vogsphere repository. Ensures `work_dir` always exists on disk so `cd` never fails.
    """
    clean_rel = rel_subj.strip("/")
    bare_repo = (kit_root / "vogsphere" / f"{clean_rel}.git").resolve()
    work_dir = work_dir.resolve()
    bare_repo.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    if not (bare_repo / "HEAD").exists():
        subprocess.run(
            ["git", "init", "--bare", str(bare_repo)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    _install_vogsphere_hook(bare_repo)

    if not (work_dir / ".git").exists():
        subprocess.run(
            ["git", "init"],
            cwd=str(work_dir),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    # Configure remote origin -> bare_repo
    rem_res = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=str(work_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if rem_res.returncode != 0:
        subprocess.run(
            ["git", "remote", "add", "origin", str(bare_repo)],
            cwd=str(work_dir),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    elif rem_res.stdout.strip() != str(bare_repo):
        subprocess.run(
            ["git", "remote", "set-url", "origin", str(bare_repo)],
            cwd=str(work_dir),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    subprocess.run(["git", "config", "user.name", login], cwd=str(work_dir), check=False)
    subprocess.run(["git", "config", "user.email", f"{login}@student.1337.ma"], cwd=str(work_dir), check=False)
    subprocess.run(["git", "config", "push.default", "current"], cwd=str(work_dir), check=False)
    subprocess.run(["git", "config", "push.autoSetupRemote", "true"], cwd=str(work_dir), check=False)
    return {"bare_repo": str(bare_repo), "work_dir": str(work_dir)}


_ACTIVE_VOGSPHERE_PULL_DIRS: list[Path] = []


def cleanup_vogsphere_temp() -> int:
    """Remove temporary vogsphere_pull_* checkout directories created in this session."""
    removed = 0
    while _ACTIVE_VOGSPHERE_PULL_DIRS:
        p = _ACTIVE_VOGSPHERE_PULL_DIRS.pop()
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            removed += 1
    return removed


def has_commits(bare_repo: Path) -> bool:
    _, bare_repo = _resolve_paths(bare_repo)
    if not bare_repo.exists():
        return False
    res = subprocess.run(
        ["git", "--git-dir", str(bare_repo), "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if res.returncode == 0:
        return True
    res_all = subprocess.run(
        ["git", "--git-dir", str(bare_repo), "rev-list", "-n", "1", "--all"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if res_all.returncode == 0 and bool(res_all.stdout.strip()):
        return True
    res_refs = subprocess.run(
        ["git", "--git-dir", str(bare_repo), "for-each-ref", "refs/heads/"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return bool(res_refs.stdout.strip())


def collect_pushed_files(path_arg: Path, slug: Optional[str] = None) -> Tuple[bool, Path]:
    """
    Clone ONLY from the bare Vogsphere repository into a clean staging directory.
    Never reads uncommitted or unpushed files from local working trees.
    Supports custom branch names, rejects symlinks (SIM-F04), and tracks temp dirs for cleanup.
    Returns (has_push: bool, checkout_dir: Path).
    """
    _, bare_repo = _resolve_paths(path_arg)
    if not has_commits(bare_repo):
        return False, bare_repo.parent / "__empty_vogsphere__"
    cleanup_vogsphere_temp()
    tmp_checkout = Path(tempfile.mkdtemp(prefix="vogsphere_pull_"))
    _ACTIVE_VOGSPHERE_PULL_DIRS.append(tmp_checkout)

    res = subprocess.run(
        ["git", "-c", "core.symlinks=false", "clone", "--no-local", str(bare_repo), str(tmp_checkout / "repo")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if res.returncode != 0:
        shutil.rmtree(tmp_checkout, ignore_errors=True)
        return False, bare_repo.parent / "__empty_vogsphere__"

    repo_root = (tmp_checkout / "repo").resolve()
    if not any(f for f in repo_root.iterdir() if f.name != ".git"):
        refs_res = subprocess.run(
            ["git", "--git-dir", str(bare_repo), "for-each-ref", "--sort=-committerdate", "--format=%(refname:short)", "refs/heads/"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        candidate_branches = [b.strip() for b in refs_res.stdout.splitlines() if b.strip()]
        for br in (*candidate_branches, "main", "master"):
            subprocess.run(["git", "checkout", "-q", br], cwd=str(repo_root), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if any(f for f in repo_root.iterdir() if f.name != ".git"):
                break

    # Security gate (SIM-F04): purge both git-index symlinks (mode 120000 under core.symlinks=false) and OS symlinks
    ls_res = subprocess.run(
        ["git", "ls-files", "-s"],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    for line in ls_res.stdout.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[0] == "120000":
            (repo_root / parts[3]).unlink(missing_ok=True)

    for p in list(repo_root.rglob("*")):
        if ".git" in p.parts:
            continue
        if p.is_symlink():
            p.unlink(missing_ok=True)

    if slug is None:
        files = [p for p in repo_root.rglob("*") if p.is_file() and not p.is_symlink() and ".git" not in p.parts]
        if not files:
            shutil.rmtree(tmp_checkout, ignore_errors=True)
            return False, bare_repo.parent / "__empty_vogsphere__"
        return True, repo_root

    try:
        resolved_target = (repo_root / slug).resolve()
        if not resolved_target.is_relative_to(repo_root):
            shutil.rmtree(tmp_checkout, ignore_errors=True)
            return False, bare_repo.parent / "__empty_vogsphere__"
    except (ValueError, RuntimeError):
        shutil.rmtree(tmp_checkout, ignore_errors=True)
        return False, bare_repo.parent / "__empty_vogsphere__"

    target = repo_root / slug
    if not target.exists():
        shutil.rmtree(tmp_checkout, ignore_errors=True)
        return False, bare_repo.parent / "__empty_vogsphere__"

    files = [p for p in target.rglob("*") if p.is_file() and not p.is_symlink() and ".git" not in p.parts]
    if not files:
        shutil.rmtree(tmp_checkout, ignore_errors=True)
        return False, bare_repo.parent / "__empty_vogsphere__"
    return True, target


def get_git_history_log(path_arg: Path) -> str:
    """Return authentic `git log` history from the bare vogsphere repository across all branches."""
    _, bare_repo = _resolve_paths(path_arg)
    if not has_commits(bare_repo):
        return "No commits pushed to Vogsphere."
    res = subprocess.run(
        [
            "git",
            "--git-dir",
            str(bare_repo),
            "log",
            "--all",
            "-n",
            "5",
            "--stat",
            "--format=commit %H%nAuthor: %an <%ae>%nDate:   %ad%n%n    %s",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return res.stdout.strip()


def register_ssh_key(path_arg: Path, pubkey_text: str, login: str = "kaouzal") -> Dict[str, str]:
    import base64
    import hashlib
    import uuid

    _, bare_repo = _resolve_paths(path_arg)
    bare_repo.mkdir(parents=True, exist_ok=True)
    clean_key = pubkey_text.strip()
    if not clean_key.startswith(("ssh-rsa ", "ssh-ed25519 ", "ecdsa-sha2-")):
        raise ValueError("Invalid SSH public key format (expected ssh-rsa or ssh-ed25519)")

    parts = clean_key.split()
    key_type = parts[0]
    raw_b64 = parts[1] if len(parts) > 1 else ""
    comment = parts[2] if len(parts) > 2 else f"{login}@c2r6p4.1337.ma"
    digest = hashlib.sha256(raw_b64.encode("utf-8")).digest()
    fp_sha256 = "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")

    auth_file = bare_repo / "authorized_keys"
    existing = auth_file.read_text(encoding="utf-8").splitlines() if auth_file.exists() else []
    if clean_key not in existing:
        existing.append(clean_key)
        auth_file.write_text("\n".join(existing) + "\n", encoding="utf-8")

    tx_id = str(uuid.uuid4())
    return {
        "login": login,
        "key_type": key_type,
        "fingerprint": fp_sha256,
        "comment": comment,
        "authorized_keys_path": str(auth_file),
        "vogsphere_uri": f"vogsphere@vogsphere.1337.ma:intra-uuid-0895be2e-{login}",
        "transaction_id": tx_id,
    }


def get_registered_ssh_keys(path_arg: Path) -> list[str]:
    _, bare_repo = _resolve_paths(path_arg)
    auth_file = bare_repo / "authorized_keys"
    if not auth_file.exists():
        return []
    return [line.strip() for line in auth_file.read_text(encoding="utf-8").splitlines() if line.strip()]


init_vogsphere_repo = init_vogsphere
