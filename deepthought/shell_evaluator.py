"""
deepthought.shell_evaluator
Authentic environment-isolated evaluator for Shell 00, Shell 01, Pre-Shell 00, Shell 02-13, and Shell Exams.
Provides real temporary Git repositories, real file trees, real tar/inode/symlink inspection,
differential reference-script oracle comparison, and automatic provisioning of Shell 00 ex07 (diff)
resources (`a` and `sw.diff`).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import yaml
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ShellEvalResult:
    ok: bool
    reason: str
    trace_lines: list[str] = field(default_factory=list)
    trap_hint: str = ""


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
    (repo_dir / ".gitignore").write_text("*.o\n*~*\n.DS_Store\nignored_secret.txt\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=repo_dir, env=env, check=True)
    hashes: list[str] = []
    for i in range(1, 7):
        f = repo_dir / f"file_{i}.c"
        f.write_text(f"/* commit {i} */\n", encoding="utf-8")
        subprocess.run(["git", "add", f.name], cwd=repo_dir, env=env, check=True)
        subprocess.run(["git", "commit", "-q", "-m", f"Commit number {i}"], cwd=repo_dir, env=env, check=True)
        h = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_dir, text=True, errors="replace").strip()
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
    kit_root = kit_root.resolve()
    submit_dir = submit_dir.resolve()
    trace: list[str] = []
    expected_files = meta.get("expected_files", []) or []

    # Special case: MaRViN / forty_two filename with backslashes and quotes
    if subject_id in {"special_filename_MaRViN", "forty_two"}:
        found = [p for p in submit_dir.rglob("*") if p.is_file() and ("MaRViN" in p.name or "KwaMe" in p.name or p.name == "_")]
        if not found:
            return ShellEvalResult(False, "Nothing turned in", ["Expected special filename not found."])
        raw_val = found[0].read_text(encoding="utf-8", errors="ignore")
        if raw_val in {"42", "42\n"}:
            return ShellEvalResult(True, "OK :)", [f"Found {found[0].name} containing '42'"])
        return ShellEvalResult(False, "Diff KO :(", [f"File must contain '42', got {raw_val!r}."])

    # 1. Verify expected files exist and no extra files (like leaving `a` or `sw.diff` in ex07!)
    visible = [p for p in submit_dir.iterdir() if not p.name.startswith(".") or p.name == ".gitignore"]
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
            [f"Forbidden extra file(s) found: {', '.join(extra)} (Only allowed: {', '.join(expected_files)})"],
            trap_hint=hint,
        )

    # 2. Subject-specific authentic Deepthought evaluation
    from .grader import get_executable_temp_root, _run_isolated
    with tempfile.TemporaryDirectory(prefix="dt_shell_", dir=str(get_executable_temp_root(kit_root))) as tmp:
        work = Path(tmp)

        # --- Exam: perm_setup (box 0750, box/key 42B 0440, shortcut -> box/key) ---
        if subject_id == "perm_setup":
            raw_sc = (submit_dir / "perm_setup.sh").read_text(encoding="utf-8", errors="ignore")
            shutil.copy2(submit_dir / "perm_setup.sh", work / "perm_setup.sh")
            proc = _run_isolated(["/bin/sh", "perm_setup.sh"], cwd=work, timeout=2.5)
            trace.append("$> /bin/sh perm_setup.sh && ls -ld box box/key shortcut")
            if proc.returncode != 0:
                return ShellEvalResult(False, f"Command exited with code {proc.returncode}", trace + [proc.stderr.strip()])
            box_p = work / "box"
            key_p = work / "box" / "key"
            sym_p = work / "shortcut"
            if not box_p.is_dir() or box_p.is_symlink():
                return ShellEvalResult(False, "Diff KO :(", trace + ["'box' directory was not created."])
            box_mode = box_p.stat().st_mode & 0o777
            if box_mode != 0o750:
                return ShellEvalResult(False, "Wrong permissions", trace + [f"Expected 'box' permissions 0750, got {oct(box_mode)}."])
            if not key_p.is_file() or key_p.is_symlink():
                return ShellEvalResult(False, "Diff KO :(", trace + ["'box/key' regular file was not created."])
            key_stat = key_p.stat()
            if key_stat.st_size != 42:
                return ShellEvalResult(False, "Wrong file size", trace + [f"Expected 'box/key' size 42 bytes, got {key_stat.st_size} bytes."])
            if (key_stat.st_mode & 0o777) != 0o440:
                return ShellEvalResult(False, "Wrong permissions", trace + [f"Expected 'box/key' permissions 0440, got {oct(key_stat.st_mode & 0o777)}."])
            if not sym_p.is_symlink() or os.readlink(sym_p) != "box/key":
                return ShellEvalResult(False, "Wrong symlink", trace + [f"Expected symlink 'shortcut -> box/key', got {os.readlink(sym_p) if sym_p.is_symlink() else 'not a symlink'!r}."])
            return ShellEvalResult(True, "OK :)", trace)

        # --- Exam: git_audit (short commit hash and author name in a Git repo) ---
        if subject_id == "git_audit":
            _init_temp_git_repo(work)
            shutil.copy2(submit_dir / "git_audit.sh", work / "git_audit.sh")
            proc = _run_isolated(["/bin/sh", "git_audit.sh"], cwd=work, timeout=2.5)
            ref_full = subprocess.run(["git", "log", "-n", "5", "--format=%h %an"], cwd=work, capture_output=True, text=True, errors="replace")
            ref_one = subprocess.run(["git", "log", "-n", "1", "--format=%h %an"], cwd=work, capture_output=True, text=True, errors="replace")
            trace.append("$> /bin/sh git_audit.sh | cat -e")
            trace.append(proc.stdout.replace("\n", "$\n"))
            if proc.returncode != 0:
                return ShellEvalResult(False, f"Command exited with code {proc.returncode}", trace + [proc.stderr.strip()])
            out_lines = [ln.strip() for ln in proc.stdout.strip().splitlines() if ln.strip()]
            ref_lines = [ln.strip() for ln in ref_full.stdout.strip().splitlines() if ln.strip()]
            # Verify output contains authentic short commit hash + author ("Marvin") from the test repo (reject static "echo OK" stubs!)
            if not out_lines or not all(ln in ref_lines for ln in out_lines):
                return ShellEvalResult(
                    False,
                    "Diff KO :(",
                    trace + [f"Expected short hash + author lines from git log (e.g. {ref_one.stdout.strip()!r}), got {proc.stdout!r}"],
                )
            return ShellEvalResult(True, "OK :)", trace)

        # --- Exam: black_hole (redirect stderr to /dev/null and print OK\n) ---
        if subject_id == "black_hole":
            raw_bh = (submit_dir / "black_hole.sh").read_text(encoding="utf-8", errors="ignore")
            if "/dev/null" not in raw_bh:
                return ShellEvalResult(
                    False,
                    "Diff KO :(",
                    trace + ["black_hole.sh must explicitly redirect standard error (2>/dev/null) to /dev/null."],
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
                return ShellEvalResult(False, "Invalid tar archive", trace + ["testShell00.tar is not a valid tar archive."])
            with tarfile.open(tar_file, "r:*") as tf:
                members = [m for m in tf.getmembers() if m.name.lstrip("./") == "testShell00"]
                if not members:
                    return ShellEvalResult(False, "Missing testShell00 in tar", trace + ["Archive does not contain 'testShell00'."])
                m = members[0]
                mode = m.mode & 0o777
                trace.append(f"mode={oct(mode)} size={m.size} isreg={m.isfile()} issym={m.issym()}")
                if not m.isfile() or m.issym():
                    return ShellEvalResult(False, "Wrong file type", trace + ["testShell00 must be a regular file, not a symlink."])
                if m.size != 40:
                    return ShellEvalResult(False, "Wrong file size", trace + [f"Expected size 40 bytes, got {m.size} bytes."])
                if mode != 0o455:
                    return ShellEvalResult(
                        False,
                        "Wrong permissions",
                        trace + [f"Expected permissions 0455 (-r--r-xr-x), got {oct(mode)}."],
                        trap_hint="r-- (4), r-x (5), r-x (5) -> chmod 455 testShell00",
                    )
            return ShellEvalResult(True, "OK :)", trace)

        # --- Shell 00 ex02: exo2 ---
        if subject_id == "exo2":
            tar_file = submit_dir / "exo2.tar"
            trace.append("$> tar -tvf exo2.tar")
            if not tarfile.is_tarfile(tar_file):
                return ShellEvalResult(False, "Invalid tar archive", trace + ["exo2.tar is not a valid tar archive."])
            with tarfile.open(tar_file, "r:*") as tf:
                by_name = {m.name.lstrip("./").rstrip("/"): m for m in tf.getmembers() if m.name.lstrip("./")}
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
                        return ShellEvalResult(False, "Missing entry in exo2.tar", trace + [f"Missing '{name}' inside exo2.tar"])
                    m = by_name[name]
                    mode = m.mode & 0o777
                    if kind == "dir" and not m.isdir():
                        return ShellEvalResult(False, "Wrong type", trace + [f"{name} must be a directory"])
                    if kind == "sym":
                        if not m.issym() or m.linkname.lstrip("./") != "test0":
                            return ShellEvalResult(False, "Wrong symlink", trace + [f"test6 must be a symlink pointing to 'test0' (got {m.linkname!r})"])
                    else:
                        if exp_mode is not None and mode != exp_mode:
                            return ShellEvalResult(False, "Wrong permissions", trace + [f"{name}: expected mode {oct(exp_mode)}, got {oct(mode)}"])
                        eff_size = by_name[m.linkname.lstrip("./")].size if (m.islnk() and m.size == 0 and m.linkname.lstrip("./") in by_name) else m.size
                        if exp_size is not None and eff_size != exp_size:
                            return ShellEvalResult(False, "Wrong size", trace + [f"{name}: expected size {exp_size}, got {eff_size}"])
                m3, m5 = by_name["test3"], by_name["test5"]
                work_resolved = work.resolve()
                for member in tf.getmembers():
                    dest_path = (work_resolved / member.name.lstrip("/")).resolve()
                    if not str(dest_path).startswith(str(work_resolved) + os.sep) and dest_path != work_resolved:
                        return ShellEvalResult(False, "Unsafe path in tar archive", trace + [f"Archive member '{member.name}' escapes working directory"])
                if hasattr(tarfile, "data_filter"):
                    tf.extractall(work, filter="data")
                else:
                    tf.extractall(work)
                if (work / "test3").exists() and (work / "test5").exists():
                    if (work / "test3").stat().st_ino != (work / "test5").stat().st_ino and not (m3.islnk() or m5.islnk()):
                        return ShellEvalResult(
                            False,
                            "Hard link missing",
                            trace + ["test3 and test5 must be hard-linked (`ln test3 test5`) so link count is 2!"],
                        )
            return ShellEvalResult(True, "OK :)", trace)

        # --- Shell 00 ex03: id_rsa_pub ---
        if subject_id == "id_rsa_pub":
            content = (submit_dir / "id_rsa_pub").read_text(encoding="utf-8", errors="ignore").strip()
            trace.append("$> head -n 1 id_rsa_pub")
            if content.startswith("ssh-"):
                return ShellEvalResult(True, "OK :)", trace + ["Valid SSH public key format."])
            return ShellEvalResult(False, "Diff KO :(", trace + ["id_rsa_pub must contain a valid SSH public key starting with 'ssh-'."])

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
            p_ref = subprocess.run(["ls", "-mpt"], cwd=work, capture_output=True, text=True, errors="replace")
            trace.append(f"$> /bin/sh midLS\n{p_user.stdout}")
            if ".hidden" in p_user.stdout or "dir_sub/" not in p_user.stdout or "," not in p_user.stdout:
                return ShellEvalResult(False, "Diff KO :(", trace + [f"Expected output matching `ls -mpt`: {p_ref.stdout!r}"])
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
                    trap_hint="Use `git log -n 5 --format=\"%H\"` to print the last 5 full commit hashes.",
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
                text=True, errors="replace",
            )
            trace.append("$> bash git_ignore.sh | cat -e")
            trace.append(proc.stdout.replace("\n", "$\n"))
            if proc.returncode != 0 or sorted(proc.stdout.splitlines()) != sorted(ref.stdout.splitlines()):
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
            p_diff = subprocess.run(["diff", str(a_file), str(user_b)], capture_output=True, text=True, errors="replace")
            expected_diff = sw_diff.read_text(encoding="utf-8")
            if p_diff.stdout == expected_diff:
                trace.append("Diff OK :D (Your file 'b' produces the exact Star Wars sw.diff!)")
                return ShellEvalResult(True, "OK :)", trace)
            return ShellEvalResult(
                False,
                "Diff KO :(",
                trace + [f"`diff a b` did not match `sw.diff`.\nExpected diff:\n{expected_diff}\nGot diff:\n{p_diff.stdout}"],
                trap_hint="Run `patch a -i sw.diff -o b` using the provided 'a' and 'sw.diff', and submit ONLY 'b'!",
            )

        # --- Shell 00 ex08: clean ---
        if subject_id == "clean":
            cmd_txt = (submit_dir / "clean").read_text(encoding="utf-8").strip()
            trace.append(f"$> cat clean\n{cmd_txt}")
            if ";" in cmd_txt.replace(r"\;", "") or "&&" in cmd_txt or "||" in cmd_txt:
                return ShellEvalResult(False, "Forbidden chaining in clean", trace + ["Subject states: Only one command is allowed, no ';' or '&&'."])
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
                    trace + ["`clean` did not delete '*~' and '#*#' files in subdirectories!"],
                    trap_hint=r"Remember to group -o with parentheses: find . \( -name '*~' -o -name '#*#' \) -print -delete",
                )
            if not keep1.exists() or not keep2.exists():
                return ShellEvalResult(False, "Deleted valid files!", trace + ["`clean` deleted files that should NOT be deleted!"])
            return ShellEvalResult(True, "OK :)", trace)

        # --- Shell 00 ex09: ft_magic ---
        if subject_id == "ft_magic":
            magic_file = submit_dir / "ft_magic"
            sample_42 = work / "sample42.bin"
            sample_42.write_bytes(b"A" * 41 + b"42" + b"Z" * 10)
            proc = subprocess.run(["file", "-m", str(magic_file), str(sample_42)], capture_output=True, text=True, errors="replace")
            trace.append(f"$> file -m ft_magic sample42.bin\n{proc.stdout.strip()}")
            if "42 file" in proc.stdout:
                return ShellEvalResult(True, "OK :)", trace)
            return ShellEvalResult(
                False,
                "Diff KO :(",
                trace + ["`file -m ft_magic` did not identify byte offset 41 ('42' at 42nd byte) as '42 file'."],
                trap_hint="Format in ft_magic: `41 string 42 42 file` (0-indexed offset 41 is the 42nd byte!).",
            )

        # --- Shell 01 & General Shell Scripts / Static Shell Files ---
        script_file = submit_dir / expected_files[0]

        # Locate subject tests.yml
        subj_candidates = []
        if subj_dir is not None and (subj_dir / "tests.yml").exists():
            subj_candidates.append(subj_dir / "tests.yml")
        subj_candidates.extend(
            list((kit_root / "subjects/exams").glob(f"{subject_id}/tests.yml"))
            + list((kit_root / "subjects/piscine").glob(f"*/{subject_id}/tests.yml"))
            + list((kit_root / "subjects/piscine").glob(f"*/{subject_id}.sh/tests.yml"))
        )
        fixed_tests = []
        if subj_candidates:
            t_cfg = yaml.safe_load(subj_candidates[0].read_text(encoding="utf-8")) or {}
            fixed_tests = t_cfg.get("fixed_tests") or []

        # Handle static turned-in files (`shell_file` like kerberos, mobile-phone.ldif)
        if str(meta.get("type", "")).lower() == "shell_file":
            file_content = script_file.read_text(encoding="utf-8", errors="ignore")
            if not file_content.strip():
                return ShellEvalResult(False, "Nothing turned in (empty file)", [f"{script_file.name} is empty"])
            if not fixed_tests:
                trace.append(f"Configuration Error: No test suite defined for {script_file.name}")
                return ShellEvalResult(False, "Configuration Error: No test suite defined", trace)
            ft0 = fixed_tests[0]
            exp_out = (
                ft0.get("stdout")
                if ft0.get("stdout") is not None
                else (ft0.get("expected") if ft0.get("expected") is not None else ft0.get("expected_content"))
            )
            exp_regex = ft0.get("expected_regex")
            if exp_out is None and exp_regex is None:
                return ShellEvalResult(False, "Configuration Error: Empty test oracle", trace)
            if exp_out is not None and file_content != str(exp_out):
                trace.append(f"Expected content:\n{exp_out!r}\nActual content:\n{file_content!r}")
                return ShellEvalResult(False, "Diff KO :(", trace)
            if exp_regex is not None and not re.search(str(exp_regex), file_content, re.MULTILINE):
                trace.append(f"Expected regex {exp_regex!r} not matched in {file_content!r}")
                return ShellEvalResult(False, "Diff KO :(", trace)
            cat_e_out = file_content.replace("\n", "$\n")
            trace.append(f"$> cat -e {script_file.name}\n{cat_e_out}")
            return ShellEvalResult(True, "OK :)", trace)

        # [DEF-005] 1. Reject empty or comment-only shell scripts immediately!
        raw_script = script_file.read_text(encoding="utf-8", errors="ignore")
        meaningful_lines = [
            ln.strip() for ln in raw_script.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        if not meaningful_lines:
            trace.append(f"{script_file.name}: Error: script is empty (0 executable commands)!")
            return ShellEvalResult(False, "Nothing turned in (empty script)", trace)

        # [DEF-005 & DEF-013] 2. Run all fixed_tests with STDOUT diff verification
        if not fixed_tests:
            trace.append("Configuration Error: No test suite defined for shell exercise!")
            return ShellEvalResult(False, "Configuration Error: No test suite defined", trace)

        base_env = {
            **os.environ,
            "PATH": f"{kit_root / 'bin'}:/bin:/usr/bin:{os.environ.get('PATH', '')}",
            "FT_USER": os.environ.get("USER", "root"),
            "FT_LINE": "Hello 1337 World!",
            "FT_LINE1": "1",
            "FT_LINE2": "3",
            "FT_NBR1": "\\\x27?\"\\\"\x27\\",
            "FT_NBR2": "rcrdmddd",
        }

        oracle_raw = meta.get("golden_oracle", "")
        oracle_script_code = oracle_raw.get("golden_code", "") if isinstance(oracle_raw, dict) else str(oracle_raw or "")
        if not oracle_script_code.strip():
            for cand_corr in [kit_root / "corrections/piscine/shell01" / subject_id / script_file.name, kit_root / "corrections/piscine/shell00" / subject_id / script_file.name, kit_root / "corrections/exams" / subject_id / script_file.name]:
                if cand_corr.is_file():
                    oracle_script_code = cand_corr.read_text(encoding="utf-8", errors="ignore")
                    break

        for idx, ft in enumerate(fixed_tests, start=1):
            case_work = work / f"case_{idx}"
            case_work.mkdir(parents=True, exist_ok=True)
            has_custom_files = bool(ft.get("files"))
            if has_custom_files:
                bin_dir = work / f"__bin_{idx}"
                bin_dir.mkdir(parents=True, exist_ok=True)
                runner_script = bin_dir / script_file.name
            else:
                runner_script = case_work / script_file.name
            shutil.copy2(script_file, runner_script)
            os.chmod(runner_script, 0o755)

            for rel_f, content_f in (ft.get("files") or {}).items():
                fp = case_work / rel_f
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(str(content_f), encoding="utf-8")

            ft_env = ft.get("env") or {}
            case_env = {**base_env, **{k: str(v) for k, v in ft_env.items()}}
            run_cwd = case_work
            if "PWD" in ft_env and not has_custom_files and Path(str(ft_env["PWD"])).is_dir():
                run_cwd = Path(str(ft_env["PWD"]))

            args = [str(a) for a in (ft.get("args") or [])]
            stdin_data = ft.get("stdin")
            exp_exit = int(ft.get("exit_code", 0))
            exp_stdout = ft.get("stdout") if ft.get("stdout") is not None else ft.get("expected")
            stdout_contains = ft.get("stdout_contains")

            # If exp_stdout is None or empty and we have a golden_oracle script, compute expected output dynamically!
            if (exp_stdout is None or exp_stdout == "") and not stdout_contains and oracle_script_code.strip() and (not ft.get("expect_empty", False) or subject_id in {"print_groups.sh", "print_groups"}):
                ref_work = work / f"ref_{idx}"
                ref_work.mkdir(parents=True, exist_ok=True)
                for rel_f, content_f in (ft.get("files") or {}).items():
                    fp = ref_work / rel_f
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    fp.write_text(str(content_f), encoding="utf-8")
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
                    text=True, errors="replace",
                    timeout=5,
                )
                exp_stdout = ref_proc.stdout
                exp_exit = ref_proc.returncode

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
                return ShellEvalResult(False, f"Command exited with code {proc.returncode} (expected {exp_exit})", trace)

            if subject_id in {"bg_pid", "find_proc", "ps_user"}:
                lines = [ln.strip() for ln in proc.stdout.strip().splitlines() if ln.strip()]
                if not lines or not all(ln.isdigit() and int(ln) > 0 for ln in lines):
                    trace.append(f"Expected valid numeric PID(s), got:\n{proc.stdout!r}")
                    return ShellEvalResult(False, "Diff KO :(", trace)
                continue

            if stdout_contains:
                for sub_s in stdout_contains:
                    if str(sub_s) not in proc.stdout:
                        trace.append(f"Expected STDOUT to contain {sub_s!r}, got:\n{proc.stdout!r}")
                        return ShellEvalResult(False, "Diff KO :(", trace)
            elif exp_stdout is not None and proc.stdout != str(exp_stdout):
                # Allow order-independent line comparison for find-based exercises where tmpfs inode order varies
                if "find" in subject_id or subject_id in {"basename_sh", "clean_temp", "tree_walk", "inc_backup"}:
                    if sorted(proc.stdout.splitlines()) == sorted(str(exp_stdout).splitlines()):
                        continue
                # For count_files.sh, allow optional leading whitespace from BSD/GNU `wc -l`
                if subject_id in {"count_files.sh", "count_files"} and proc.stdout.strip() == str(exp_stdout).strip() and proc.stdout.endswith("\n"):
                    continue
                trace.append(f"Expected STDOUT:\n{exp_stdout!r}\nActual STDOUT:\n{proc.stdout!r}")
                return ShellEvalResult(False, "Diff KO :(", trace)
            elif exp_stdout is None and not proc.stdout.strip() and subject_id not in {"perm_setup", "clean", "exo2", "testShell00", "MAC.sh"}:
                trace.append("Script produced empty STDOUT!")
                return ShellEvalResult(False, "Diff KO :( (empty output)", trace)

        return ShellEvalResult(True, "OK :)", trace)
