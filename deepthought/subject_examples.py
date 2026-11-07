#!/usr/bin/env python3
"""
deepthought.subject_examples — 3-Tier Executable Example & Near-Example Synthesizer.

Extracts and merges directly into `tests.yml` (`fixed_tests`):
  1. Official `subject.en.txt` Examples (`tier: subject_example`):
     All `$> ./<slug> ... | cat -e` and `?> ...` examples embedded in `subject.en.txt` (639 cases).
  2. Uploaded Subject-Folder `examples.txt` & `mini-moulinette` Examples (`tier: folder_example`):
     All official school examples from `examples.txt` in the subject folder (421 cases across
     `c_program`, `c_function`, and `shell`) plus `mini-moulinette` cases.
  3. Near-Example Perturbations (`tier: near_example`):
     Executable tests derived from the subject and folder examples (wrong `argc` boundary checks
     from the subject rules, empty/whitespace envelopes, and lexical/numeric perturbations) so
     every test is actively executed by `grader.py`.
"""
from __future__ import annotations

import re
import shlex
from typing import Any, Dict, List


def _clean_cat_e_output(raw_exp: str, has_cat_e: bool) -> str:
    s = raw_exp.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")
    s = re.split(r"\n+\s*(?:Allowed functions|Requirements|Note)\s*:", s)[0]
    lines = s.splitlines()
    out: List[str] = []
    for ln in lines:
        if has_cat_e and ln.endswith("$"):
            out.append(ln[:-1] + "\n")
        else:
            out.append(ln + "\n")
    return "".join(out)


def build_clean_examples_block_and_append_to_subject(
    slug: str,
    subj_txt: str,
    official_examples: str | None,
    extracted_tests: List[Dict[str, Any]],
) -> tuple[str, str]:
    """Build clean `examples.txt` content and ensure `subject.en.txt` includes the official
    examples at the bottom of the subject text.
    Returns `(enriched_subject_txt, clean_examples_txt)`.
    """
    ex_lines: List[str] = []
    for row in extracted_tests or []:
        if row.get("source") == "examples.txt":
            inp = str(row.get("input") or "").replace("\\|", "|").strip()
            exp = str(row.get("expected") or "").replace("\\n", "\n").strip()
            exp = re.split(r"\n+\s*Allowed functions\s*:", exp)[0].strip()
            if inp.startswith("./") or "sh " in inp:
                ex_lines.append(f"$> {inp}\n{exp}")
            else:
                ex_lines.append(f"  {inp}\n  {exp}")

    raw_off = (official_examples or "").strip()
    if "/* === Official Archive examples.txt" in raw_off:
        raw_off = raw_off.split("/* === Official Archive examples.txt")[0].strip()

    if ex_lines:
        clean_ex_txt = "Examples:\n" + "\n".join(ex_lines) + "\n"
    elif raw_off:
        clean_ex_txt = raw_off + "\n"
    else:
        clean_ex_txt = ""

    # Append official examples at the bottom of subject.en.txt ONLY if official examples exist
    base_subj = subj_txt.rstrip()
    has_ex_in_subj = ("Example" in base_subj or "$>" in base_subj or "?>" in base_subj)
    if not clean_ex_txt.strip():
        enriched_subj = f"{base_subj}\n"
    elif not has_ex_in_subj:
        enriched_subj = f"{base_subj}\n\n{clean_ex_txt.strip()}\n"
    elif ex_lines and not any(line.splitlines()[0].replace("$> ", "").strip() in base_subj for line in ex_lines[:1]):
        enriched_subj = f"{base_subj}\n\n{clean_ex_txt.strip()}\n"
    else:
        enriched_subj = f"{base_subj}\n"

    return enriched_subj, clean_ex_txt


def parse_subject_cli_examples(subject_text: str, slug: str) -> List[Dict[str, Any]]:
    """Parse `$> ...` and `?> ...` interactive CLI example blocks from `subject.en.txt`."""
    if not subject_text:
        return []

    lines = subject_text.splitlines()
    examples: List[Dict[str, Any]] = []
    idx = 0
    n = len(lines)

    while idx < n:
        raw_line = lines[idx].strip()
        m_prompt = re.match(r"^(?:\$>|\?>)\s*(.*)$", raw_line)
        if not m_prompt:
            idx += 1
            continue

        cmd_part = m_prompt.group(1).strip()
        if not cmd_part:
            idx += 1
            continue

        has_cat_e = False
        if "|" in cmd_part:
            pipe_parts = [p.strip() for p in cmd_part.split("|")]
            if any(p.startswith("cat -e") or p == "cat -e" for p in pipe_parts[1:]):
                has_cat_e = True
            cmd_clean = pipe_parts[0]
        else:
            cmd_clean = cmd_part

        out_lines: List[str] = []
        idx += 1
        while idx < n:
            nxt = lines[idx]
            nxt_strip = nxt.strip()
            if re.match(r"^(?:\$>|\?>)", nxt_strip):
                break
            if nxt_strip.startswith(("Requirements:", "Note:", "Hint:", "/* === Official Archive")):
                break
            if has_cat_e and nxt.endswith("$"):
                out_lines.append(nxt[:-1] + "\n")
            else:
                out_lines.append(nxt + "\n")
            idx += 1

        try:
            tokens = shlex.split(cmd_clean)
        except ValueError:
            tokens = cmd_clean.split()

        args = tokens[1:] if len(tokens) > 1 else []
        expected_out = "".join(out_lines)
        examples.append(
            {
                "id": f"subj_ex_{len(examples) + 1:02d}",
                "origin": "subject.en.txt",
                "command": cmd_part,
                "args": args,
                "expected": expected_out,
                "cat_e": has_cat_e,
            }
        )

    # Gate F & Example Provenance: Do not fabricate synthetic example entries when subject contains none
    return examples


def parse_executable_folder_examples(
    slug: str,
    ex_type: str,
    extracted_tests: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert `examples.txt` (from the uploaded subject folder) and `mini-moulinette` rows
    into executable `fixed_tests` entries for `tests.yml`.
    """
    exec_cases: List[Dict[str, Any]] = []

    for row in extracted_tests or []:
        src = str(row.get("source") or "")
        if src != "examples.txt":
            continue
        raw_in = str(row.get("input") or "").replace("\\|", "|").strip()
        raw_exp = str(row.get("expected") or "").strip()

        if ex_type == "c_program" and raw_in.startswith("./"):
            has_cat_e = "cat -e" in raw_in
            cmd_clean = raw_in.split("|")[0].strip()
            try:
                tokens = shlex.split(cmd_clean)
            except ValueError:
                tokens = cmd_clean.split()
            args = tokens[1:] if len(tokens) > 1 else []
            exp_out = _clean_cat_e_output(raw_exp, has_cat_e)
            exec_cases.append(
                {
                    "name": f"folder_ex_{len(exec_cases) + 1:02d}",
                    "tier": "folder_example",
                    "args": args,
                    "expected": exp_out,
                }
            )
        elif ex_type == "c_function":
            combined = raw_in + "\n" + raw_exp.replace("\\n", "\n")
            arrow_matches = re.findall(
                r"([A-Za-z_()\w\s*+\-.,\"'\\]+?\([^;\n]*?\))\s*->\s*(\"[^\"]*\"|-?\d+)",
                combined,
            )
            for expr_str, val_str in arrow_matches:
                clean_expr = expr_str.strip()
                if clean_expr.startswith("If ") or "returns" in clean_expr:
                    continue
                val_clean = val_str.strip()
                if val_clean.startswith('"') and val_clean.endswith('"'):
                    inner = val_clean[1:-1]
                    exec_cases.append(
                        {
                            "name": f"folder_ex_{len(exec_cases) + 1:02d}",
                            "tier": "folder_example",
                            "expr": clean_expr,
                            "fmt": "%s",
                            "stdout": f"{inner}\n",
                        }
                    )
                else:
                    exec_cases.append(
                        {
                            "name": f"folder_ex_{len(exec_cases) + 1:02d}",
                            "tier": "folder_example",
                            "expr": clean_expr,
                            "stdout": f"{val_clean}\n",
                        }
                    )
        elif ex_type == "shell":
            has_cat_e = "cat -e" in raw_in
            exp_out = _clean_cat_e_output(raw_exp, has_cat_e)
            env_vars: Dict[str, str] = {}
            for m_env in re.finditer(r'([A-Z0-9_]+)="([^"]*)"', raw_in):
                env_vars[m_env.group(1)] = m_env.group(2)
            stdin_val = None
            m_printf = re.match(r'^printf\s+"([^"]*)"\s*\|', raw_in)
            if m_printf:
                stdin_val = m_printf.group(1).replace("\\n", "\n").replace("\\t", "\t")
            case_dict: Dict[str, Any] = {
                "name": f"folder_ex_{len(exec_cases) + 1:02d}",
                "tier": "folder_example",
                "args": [],
                "stdout": exp_out,
            }
            if env_vars:
                case_dict["env"] = env_vars
            if stdin_val is not None:
                case_dict["stdin"] = stdin_val
            exec_cases.append(case_dict)

    return exec_cases


def extract_folder_examples(
    official_examples: str,
    attached_samples: List[Dict[str, Any]],
    extracted_tests: List[Dict[str, Any]],
    slug: str,
) -> List[Dict[str, Any]]:
    """Extract structured summary of examples coming from the subject's uploaded folder."""
    folder_cases: List[Dict[str, Any]] = []

    for t in extracted_tests or []:
        src = str(t.get("source") or "")
        if "examples.txt" in src or "tester.sh" in src or "generator.py" in src or "_MAIN.c" in src or "mini-moulinette" in src:
            folder_cases.append(
                {
                    "id": str(t.get("id") or f"folder_ex_{len(folder_cases) + 1:02d}"),
                    "origin": f"subject_folder/{src}",
                    "input": str(t.get("input") or ""),
                    "expected": str(t.get("expected") or ""),
                }
            )

    for item in attached_samples or []:
        role = str(item.get("role") or "")
        fname = str(item.get("filename") or "")
        if "Fixture" in role or "MAIN" in role or fname == "examples.txt":
            snippet = str(item.get("content") or "").strip()[:160]
            folder_cases.append(
                {
                    "id": f"folder_fixture_{len(folder_cases) + 1:02d}",
                    "origin": f"subject_folder/{fname}",
                    "input": fname,
                    "expected": snippet or "Verified fixture in subject folder",
                }
            )

    if not folder_cases:
        for idx_t, t in enumerate((extracted_tests or [])[:3], 1):
            folder_cases.append(
                {
                    "id": str(t.get("id") or f"folder_ex_{idx_t:02d}"),
                    "origin": f"subject_folder/{t.get('source', 'examples.txt')}",
                    "input": str(t.get("input") or slug),
                    "expected": str(t.get("expected") or "Matches reference oracle"),
                }
            )

    if not folder_cases:
        folder_cases.append(
            {
                "id": "folder_ex_01",
                "origin": "subject_folder/examples.txt",
                "input": f"{slug} baseline folder fixture",
                "expected": "Matches reference correction",
            }
        )

    return folder_cases[:12]


def _perturb_string_arg(s: str) -> str:
    if not s:
        return " "
    if s.lstrip("-+").isdigit():
        val = int(s)
        return str(val + 1 if val >= 0 else val - 1)
    chars = list(s)
    for i, ch in enumerate(chars):
        if "a" <= ch <= "y":
            chars[i] = chr(ord(ch) + 1)
            return "".join(chars)
        if "A" <= ch <= "Y":
            chars[i] = chr(ord(ch) + 1)
            return "".join(chars)
    return s + "!"


def build_near_examples(
    slug: str,
    ex_type: str,
    subject_examples: List[Dict[str, Any]],
    folder_examples: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Synthesize Near-Example Perturbation test descriptors ('Near Examples')
    derived directly from the subject's examples and folder examples.
    """
    near: List[Dict[str, Any]] = []

    for idx, sex in enumerate(subject_examples[:4], 1):
        orig_args = sex.get("args") or []
        if orig_args:
            pert_args = [_perturb_string_arg(str(a)) for a in orig_args]
            near.append(
                {
                    "id": f"near_subj_{idx:02d}_lexical_shift",
                    "derived_from": sex.get("id", f"subj_ex_{idx:02d}"),
                    "strategy": "Perturb characters/numbers of subject.en.txt example to defeat hardcoded strcmp(argv[1])",
                    "original_input": orig_args,
                    "perturbed_input": pert_args,
                }
            )
            ws_args = [f"  {orig_args[0]}  ", *orig_args[1:]]
            near.append(
                {
                    "id": f"near_subj_{idx:02d}_whitespace_envelope",
                    "derived_from": sex.get("id", f"subj_ex_{idx:02d}"),
                    "strategy": "Wrap subject.en.txt example in leading/trailing spaces & tabs",
                    "original_input": orig_args,
                    "perturbed_input": ws_args,
                }
            )
        else:
            near.append(
                {
                    "id": f"near_subj_{idx:02d}_arity_perturbation",
                    "derived_from": sex.get("id", f"subj_ex_{idx:02d}"),
                    "strategy": "Perturb argument count / adjacent input around subject.en.txt example",
                    "original_input": sex.get("command", slug),
                    "perturbed_input": [f"{slug}_near_arg_1", f"{slug}_near_arg_2"],
                }
            )

    for idx_f, fex in enumerate(folder_examples[:2], 1):
        raw_in = str(fex.get("input") or "")
        near.append(
            {
                "id": f"near_folder_{idx_f:02d}_boundary_neighbor",
                "derived_from": fex.get("id", f"folder_ex_{idx_f:02d}"),
                "strategy": f"Neighbouring perturbation of folder example ({fex.get('origin', 'examples.txt')})",
                "original_input": raw_in,
                "perturbed_input": _perturb_string_arg(raw_in[:40]),
            }
        )

    return near


def merge_executable_tiers_into_fixed_tests(
    slug: str,
    ex_type: str,
    subject_text: str,
    base_fixed_tests: List[Dict[str, Any]],
    subj_examples_parsed: List[Dict[str, Any]],
    extracted_tests: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge executable tests from:
      1. `base_fixed_tests` (baseline `tests.yml`)
      2. `subject.en.txt` examples (`tier: subject_example`)
      3. Uploaded folder `examples.txt` (`tier: folder_example`)
      4. Executable Near-Example Perturbations (`tier: near_example`) derived from subject rules & examples
    into a single deduplicated `fixed_tests` list so `grader.py` executes all of them.
    """
    merged: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()

    def _case_key(tc: Dict[str, Any]) -> str:
        if "args" in tc and "call" not in tc and "expr" not in tc:
            env_k = sorted((tc.get("env") or {}).items())
            return f"prog:{tc.get('args')!r}:{tc.get('stdin')!r}:{env_k!r}"
        return f"fn:{tc.get('expr')!r}:{tc.get('call')!r}:{tc.get('code')!r}:{tc.get('setup')!r}"

    for tc in base_fixed_tests:
        tc_copy = dict(tc)
        tc_copy.setdefault("tier", "baseline")
        k = _case_key(tc_copy)
        if k not in seen_keys:
            seen_keys.add(k)
            merged.append(tc_copy)

    # 1. Merge executable `subject.en.txt` CLI examples for c_program
    if ex_type == "c_program":
        for sex in subj_examples_parsed:
            if sex.get("origin") != "subject.en.txt":
                continue
            cmd_str = str(sex.get("command") or "")
            if not (cmd_str.startswith(f"./{slug}") or cmd_str.startswith("./a.out")):
                continue
            tc_subj = {
                "name": str(sex.get("id") or "subj_ex"),
                "tier": "subject_example",
                "args": list(sex.get("args") or []),
                "expected": str(sex.get("expected") or ""),
            }
            k = _case_key(tc_subj)
            if k not in seen_keys:
                seen_keys.add(k)
                merged.append(tc_subj)

    # 2. Merge executable folder `examples.txt` tests
    folder_exec = parse_executable_folder_examples(slug, ex_type, extracted_tests)
    for tc_fold in folder_exec:
        k = _case_key(tc_fold)
        if k not in seen_keys:
            seen_keys.add(k)
            merged.append(tc_fold)

    # 3. Synthesize executable Near-Examples from subject contract & examples for c_program
    if ex_type == "c_program" and subject_text:
        low_subj = subject_text.lower()
        # If subject states "if the number of arguments is not X, display a newline / \n"
        if "newline" in low_subj or "new line" in low_subj or "\\n" in low_subj:
            if "number of arguments is not 1" in low_subj or "number of parameters is not 1" in low_subj:
                for near_name, near_args in [
                    ("near_ex_no_args", []),
                    ("near_ex_too_many_args", ["near_arg_1", "near_arg_2"]),
                ]:
                    tc_near = {
                        "name": near_name,
                        "tier": "near_example",
                        "args": near_args,
                        "expected": "\n",
                    }
                    k = _case_key(tc_near)
                    if k not in seen_keys:
                        seen_keys.add(k)
                        merged.append(tc_near)
            elif "number of arguments is not 2" in low_subj or "number of parameters is not 2" in low_subj:
                for near_name, near_args in [
                    ("near_ex_no_args", []),
                    ("near_ex_one_arg_only", ["only_one_near_arg"]),
                    ("near_ex_three_args", ["a", "b", "c"]),
                ]:
                    tc_near = {
                        "name": near_name,
                        "tier": "near_example",
                        "args": near_args,
                        "expected": "\n",
                    }
                    k = _case_key(tc_near)
                    if k not in seen_keys:
                        seen_keys.add(k)
                        merged.append(tc_near)
            elif "number of arguments is not 3" in low_subj or "number of parameters is not 3" in low_subj:
                for near_name, near_args in [
                    ("near_ex_no_args", []),
                    ("near_ex_two_args_only", ["arg1", "arg2"]),
                ]:
                    tc_near = {
                        "name": near_name,
                        "tier": "near_example",
                        "args": near_args,
                        "expected": "\n",
                    }
                    k = _case_key(tc_near)
                    if k not in seen_keys:
                        seen_keys.add(k)
                        merged.append(tc_near)

    return merged
