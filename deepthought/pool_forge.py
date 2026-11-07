#!/usr/bin/env python3
"""
deepthought.pool_forge — Scaffolding & Blueprint Generator for 1337 / 42 Exercises & Pools.
Creates empty or template-based 4-component exercise skeletons:
  1. subject.en.txt (80-dash header contract)
  2. meta.yml       (expected_files, allowed_functions, compiler_flags, norminette)
  3. tests.yml      (deterministic & mutation-killing test vectors)
  4. scale.yml      (1337HUB Peer-Evaluation Scale with Live Mutation Defense)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
KIT_ROOT = Path(__file__).resolve().parents[1]
if str(KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(KIT_ROOT))

import json
import re
from typing import Any, Dict, List
import yaml
from deepthought.progression import calculate_exercise_xp
from deepthought.subject_examples import (
    build_clean_examples_block_and_append_to_subject,
    build_near_examples,
    extract_folder_examples,
    merge_executable_tiers_into_fixed_tests,
    parse_subject_cli_examples,
)

_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_YAML_DUMPER = getattr(yaml, "CSafeDumper", yaml.SafeDumper)


def _fast_yaml_dump(data: Any) -> str:
    return str(yaml.dump(data, Dumper=_YAML_DUMPER, sort_keys=False, allow_unicode=True))


def _fast_yaml_load(stream: str) -> Any:
    return yaml.load(stream, Loader=_YAML_LOADER)


def _write_if_changed(path: Path, content: str) -> None:
    try:
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return
    except Exception:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")



HEADER_42_TEMPLATE = (
    "/* ************************************************************************** */\n"
    "/*                                                                            */\n"
    "/*                                                        :::      ::::::::   */\n"
    "/*   {fname:<51}:+:      :+:    :+:   */\n"
    "/*                                                    +:+ +:+         +:+     */\n"
    "/*   By: marvin <marvin@42.fr>                      +#+  +:+       +#+        */\n"
    "/*                                                +#+#+#+#+#+   +#+           */\n"
    "/*   Created: 2026/10/26 10:00:00 by marvin            #+#    #+#             */\n"
    "/*   Updated: 2026/10/26 10:00:00 by marvin           ###   ########.fr       */\n"
    "/*                                                                            */\n"
    "/* ************************************************************************** */\n\n"
)

MODULE_SLUG_MAP = {
    "Shell 00": "shell00",
    "Shell 01": "shell01",
    "C 00": "c00",
    "C 01": "c01",
    "C 02": "c02",
    "C 03": "c03",
    "C 04": "c04",
    "C 05": "c05",
    "C 06": "c06",
    "C 07": "c07",
    "C 08": "c08",
    "C 09": "c09",
    "C 10": "c10",
    "C 11": "c11",
    "C 12": "c12",
    "C 13": "c13",
    "Rush 00–02 & BSQ": "rush_bsq",
}


def _clean_c_prototype(raw_proto: str | None, slug: str, ex_type: str) -> str | None:
    if not raw_proto or not raw_proto.strip():
        return None
    s = raw_proto.strip()
    if ex_type not in ("c_function", "c_program"):
        return s
    m = re.search(
        r"((?:unsigned\s+|signed\s+|const\s+|struct\s+\w+\s+|long\s+|short\s+|int\s+|void\s+|char\s+|float\s+|double\s+|size_t\s+|t_list\s+|t_btree\s+)+[*]*\s*[A-Za-z_]\w*\s*\([^;{}]*\))\s*;?",
        s,
    )
    if m:
        return " ".join(m.group(1).split()) + ";"
    return s


def _unescape_catalog_str(val: str) -> str:
    s = str(val or "")
    if s.startswith("`\\n`"):
        return "\n"
    if s.startswith("`") and s.endswith("`") and len(s) >= 2:
        s = s[1:-1]
    return (
        s.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace("\\v", "\v")
        .replace("\\f", "\f")
        .replace("\\|", "|")
    )


CANONICAL_FIXED_TESTS: Dict[str, List[Dict[str, Any]]] = {
    "rot_13": [
        {"name": "subj_ex_01_abc", "tier": "subject_example", "args": ["abc"], "expected": "nop\n"},
        {"name": "subj_ex_02_horse", "tier": "subject_example", "args": ["My horse is Amazing."], "expected": "Zl ubefr vf Nznmvat.\n"},
        {"name": "subj_ex_03_mixed", "tier": "subject_example", "args": ["AkjhZ zLKIJz , 23y "], "expected": "NxwuM mYXVWm , 23l \n"},
        {"name": "subj_ex_04_no_args", "tier": "subject_example", "args": [], "expected": "\n"},
        {"name": "subj_ex_05_empty", "tier": "subject_example", "args": [""], "expected": "\n"},
        {"name": "folder_ex_alphabet", "tier": "folder_example", "args": ["abcdefghijklmnopqrstuvwxyz"], "expected": "nopqrstuvwxyzabcdefghijklm\n"},
        {"name": "near_ex_horse_perturbed", "tier": "near_example", "args": ["My horse is Amazing!"], "expected": "Zl ubefr vf Nznmvat!\n"},
        {"name": "near_ex_abc_upper_shift", "tier": "near_example", "args": ["abc XYZ"], "expected": "nop KLM\n"},
    ],
    "first_word": [
        {"name": "subj_ex_01_for_pony", "tier": "subject_example", "args": ["FOR PONY"], "expected": "FOR\n"},
        {"name": "subj_ex_02_sparta", "tier": "subject_example", "args": ["this        ...       is sparta, then again, maybe    not"], "expected": "this\n"},
        {"name": "subj_ex_03_spaces_only", "tier": "subject_example", "args": ["   "], "expected": "\n"},
        {"name": "subj_ex_04_multi_args", "tier": "subject_example", "args": ["a", "b"], "expected": "\n"},
        {"name": "subj_ex_05_lorem", "tier": "subject_example", "args": ["  lorem,ipsum  "], "expected": "lorem,ipsum\n"},
        {"name": "near_ex_tabs_and_spaces", "tier": "near_example", "args": ["\t\t  FOR_PONY_NEAR \t world"], "expected": "FOR_PONY_NEAR\n"},
    ],
    "inter": [
        {"name": "subj_ex_01_padinton", "tier": "subject_example", "args": ["padinton", "paqefwtdjetyiytjneytjoeyjnejeyj"], "expected": "padinto\n"},
        {"name": "subj_ex_02_duplicates", "tier": "subject_example", "args": ["ddf6vewg64f", "gtwthgdwthdwfteewhrtag6h4ffdhsd"], "expected": "df6ewg4\n"},
        {"name": "subj_ex_03_rien", "tier": "subject_example", "args": ["rien", "cette phrase ne cache rien"], "expected": "rien\n"},
        {"name": "subj_ex_04_no_args", "tier": "subject_example", "args": [], "expected": "\n"},
        {"name": "folder_ex_no_common", "tier": "folder_example", "args": ["abc", "XYZ"], "expected": "\n"},
        {"name": "near_ex_padinton_perturbed", "tier": "near_example", "args": ["padinton!", "paqefwtdjetyiytjneytjoeyjnejeyj!"], "expected": "padinto!\n"},
        {"name": "near_ex_wrong_argc", "tier": "near_example", "args": ["abc"], "expected": "\n"},
    ],
    "wdmatch": [
        {"name": "subj_ex_01_faya", "tier": "subject_example", "args": ["faya", "fgvvfdxcacpolhyghbreda"], "expected": "faya\n"},
        {"name": "subj_ex_02_no_match", "tier": "subject_example", "args": ["faya", "fgvvfdxcacpolhyghbred"], "expected": "\n"},
        {"name": "subj_ex_03_quarante_deux", "tier": "subject_example", "args": ["quarante deux", "qfqfsudf arzgsayns tsregfdgs sjytdekuoixq "], "expected": "quarante deux\n"},
        {"name": "subj_ex_04_error", "tier": "subject_example", "args": ["error", "rrerrrfiiljdfxjyuifrrvcoojh"], "expected": "\n"},
        {"name": "near_ex_faya_perturbed", "tier": "near_example", "args": ["fayb", "fgvvfdxcacpolhyghbredb"], "expected": "fayb\n"},
        {"name": "near_ex_wrong_argc", "tier": "near_example", "args": ["abc"], "expected": "\n"},
    ],
    "ft_swap": [
        {"name": "subj_ex_swap_1_2", "tier": "subject_example", "call": 'int a = 1, b = 2; ft_swap(&a, &b); printf("%d %d\\n", a, b)', "stdout": "2 1\n"},
        {"name": "folder_ex_swap_neg", "tier": "folder_example", "call": 'int a = -10, b = -20; ft_swap(&a, &b); printf("%d,%d\\n", a, b)', "stdout": "-20,-10\n"},
        {"name": "near_ex_swap_adjacent", "tier": "near_example", "call": 'int a = 42, b = 43; ft_swap(&a, &b); printf("%d,%d\\n", a, b)', "stdout": "43,42\n"},
        {"name": "near_ex_swap_zero", "tier": "near_example", "call": 'int a = 0, b = 1337; ft_swap(&a, &b); printf("%d,%d\\n", a, b)', "stdout": "1337,0\n"},
    ],
    "ft_itoa": [
        {"name": "subj_ex_neg_42", "tier": "subject_example", "call": 'char *s = ft_itoa(-42); printf("%s\\n", s ? s : "NULL"); free(s)', "stdout": "-42\n"},
        {"name": "subj_ex_zero", "tier": "subject_example", "call": 'char *s = ft_itoa(0); printf("%s\\n", s ? s : "NULL"); free(s)', "stdout": "0\n"},
        {"name": "folder_ex_int_min", "tier": "folder_example", "call": 'char *s = ft_itoa(-2147483648); printf("%s\\n", s ? s : "NULL"); free(s)', "stdout": "-2147483648\n"},
        {"name": "near_ex_neg_43", "tier": "near_example", "call": 'char *s = ft_itoa(-43); printf("%s\\n", s ? s : "NULL"); free(s)', "stdout": "-43\n"},
    ],
    "ft_atoi": [
        {"name": "subj_ex_zero", "tier": "subject_example", "expr": 'ft_atoi("0")', "stdout": "0\n"},
        {"name": "subj_ex_positive_42", "tier": "subject_example", "expr": 'ft_atoi("42")', "stdout": "42\n"},
        {"name": "folder_ex_spaces_negative", "tier": "folder_example", "expr": 'ft_atoi("   \\t\\n\\v\\f\\r  -42")', "stdout": "-42\n"},
        {"name": "near_ex_positive_43_padded", "tier": "near_example", "expr": 'ft_atoi("  +43abc")', "stdout": "43\n"},
        {"name": "near_ex_plus_1337", "tier": "near_example", "expr": 'ft_atoi("+1337abc")', "stdout": "1337\n"},
    ],
    "ft_split": [
        {
            "name": "subj_ex_multi_spaces_and_tabs",
            "tier": "subject_example",
            "setup": ['char **w = ft_split("  hello \\t 1337 \\n world  ");'],
            "call": 'printf("%s|%s|%s|%d\\n", w[0] ? w[0] : "NULL", w[1] ? w[1] : "NULL", w[2] ? w[2] : "NULL", w[3] == NULL)',
            "stdout": "hello|1337|world|1\n",
        },
        {
            "name": "near_ex_perturbed_words",
            "tier": "near_example",
            "setup": ['char **w = ft_split(" \\t alpha   beta_42 \\n ");'],
            "call": 'printf("%s|%s|%d\\n", w[0] ? w[0] : "NULL", w[1] ? w[1] : "NULL", w[2] == NULL)',
            "stdout": "alpha|beta_42|1\n",
        },
        {
            "name": "folder_ex_empty_string",
            "tier": "folder_example",
            "setup": ['char **w = ft_split("   \\t\\n  ");'],
            "call": 'printf("w[0]=%s\\n", w && w[0] ? w[0] : "NULL")',
            "stdout": "w[0]=NULL\n",
        },
    ],
    "strlen_sh": [
        {"name": "subj_ex_len_16", "tier": "subject_example", "env": {"FT_LINE": "0123456789abcdef"}, "args": [], "stdout": "16\n"},
        {"name": "folder_ex_len_0", "tier": "folder_example", "env": {"FT_LINE": ""}, "args": [], "stdout": "0\n"},
        {"name": "near_ex_len_17_perturbed", "tier": "near_example", "env": {"FT_LINE": "0123456789abcdefX"}, "args": [], "stdout": "17\n"},
    ],
}


def scaffold_exercise(
    slug: str,
    ex_type: str,
    category: str,
    allowed: str,
    expected_files: list[str],
    *,
    xp: int | None = None,
    module_code: str = "",
    prototype: str | None = None,
    subject_text: str | None = None,
    official_examples: str | None = None,
    attached_samples: list[dict[str, Any]] | None = None,
    extracted_tests: list[dict[str, Any]] | None = None,
    fixed_tests: list[dict[str, Any]] | None = None,
    edge_tests: list[dict[str, Any]] | None = None,
    raw_tests_yml: dict[str, Any] | None = None,
) -> Path:
    target_dir = KIT_ROOT / "subjects" / category / slug
    target_dir.mkdir(parents=True, exist_ok=True)

    files_str = " ".join(expected_files)
    if subject_text and subject_text.strip():
        subj_txt = subject_text.strip() + "\n"
        if "Assignment name" not in subj_txt:
            subj_txt = (
                f"Assignment name  : {slug}\n"
                f"Expected files   : {files_str}\n"
                f"Allowed functions: {allowed}\n"
                f"{'-' * 80}\n\n"
                + subj_txt
            )
    else:
        subj_txt = (
            f"Assignment name  : {slug}\n"
            f"Expected files   : {files_str}\n"
            f"Allowed functions: {allowed}\n"
            f"{'-' * 80}\n\n"
            f"Write the implementation of `{slug}` adhering strictly to the 1337 / 42 contract.\n\n"
            f"Examples:\n"
            f"$> ./{slug} | cat -e\n"
            f"OK$\n"
        )
    subj_txt, clean_ex_txt = build_clean_examples_block_and_append_to_subject(
        slug,
        subj_txt,
        official_examples or "",
        extracted_tests,
    )
    _write_if_changed(target_dir / "subject.en.txt", subj_txt)
    if clean_ex_txt.strip():
        _write_if_changed(target_dir / "examples.txt", clean_ex_txt)

    subj_examples_parsed = parse_subject_cli_examples(subj_txt, slug)
    folder_examples_parsed = extract_folder_examples(
        official_examples or "",
        attached_samples or [],
        extracted_tests or [],
        slug,
    )
    near_examples_parsed = build_near_examples(
        slug,
        ex_type,
        subj_examples_parsed,
        folder_examples_parsed,
    )

    allowed_list = [
        x.strip()
        for x in re.split(r"[,\s]+", allowed)
        if x.strip()
        and x.strip().lower() != "none"
        and not x.strip().startswith("---")
        and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", x.strip())
    ]
    xp_val = xp if (xp is not None and xp > 0) else calculate_exercise_xp(module_code, ex_type, 1.0)
    clean_proto = _clean_c_prototype(prototype, slug, ex_type)
    meta_data: Dict[str, Any] = {
        "id": slug,
        "type": ex_type,
        "module": module_code or category,
        "xp": int(xp_val),
        "expected_files": expected_files,
        "allowed_functions": allowed_list,
        "compiler_flags": ["-Wall", "-Wextra", "-Werror"],
        "norminette": bool(not category.startswith("exams")),
    }
    if clean_proto:
        meta_data["prototype"] = clean_proto
    _write_if_changed(target_dir / "meta.yml", _fast_yaml_dump(meta_data))

    if raw_tests_yml and isinstance(raw_tests_yml, dict) and raw_tests_yml.get("fixed_tests"):
        tests_data = dict(raw_tests_yml)
        tests_data.setdefault("mode", ex_type)
    else:
        tests_data = {
            "mode": ex_type,
            "fixed_tests": fixed_tests
            if fixed_tests
            else [
                {
                    "name": "nominal_contract_check",
                    "args": [],
                    "expected": "OK\n",
                }
            ],
        }
    if slug not in CANONICAL_FIXED_TESTS and isinstance(tests_data.get("fixed_tests"), list):
        tests_data["fixed_tests"] = merge_executable_tiers_into_fixed_tests(
            slug,
            ex_type,
            subj_txt,
            tests_data["fixed_tests"],
            subj_examples_parsed,
            extracted_tests or [],
        )
    tests_data["subject_examples"] = subj_examples_parsed
    tests_data["folder_examples"] = folder_examples_parsed
    tests_data["near_examples"] = near_examples_parsed
    _write_if_changed(target_dir / "tests.yml", _fast_yaml_dump(tests_data))

    scale_txt = (
        f"project: {slug}\n"
        "scale_version: 1337HUB-v4.2\n"
        "stop_on_first_failure: true\n"
        "zero_tolerance_gates:\n"
        "- segfault\n"
        "- memory_leak\n"
        "- norme_error\n"
        "- forbidden_function\n"
        "sections:\n"
        "- id: preliminaries\n"
        "  title: 'Step 1: Preliminaries & Vogsphere Integrity Check'\n"
        "  points: 20\n"
        "  checks:\n"
        "  - Clone official Vogsphere repository into an empty folder.\n"
        "  - Verify no malicious shell aliases or unauthorized files exist.\n"
        "  - Run norminette / shnorm and verify clean compilation with -Wall -Wextra -Werror.\n"
        "- id: explain_before_checking\n"
        "  title: 'Step 2: Conceptual Defense (Explain Before Checking)'\n"
        "  points: 30\n"
        "  checks:\n"
        "  - Student explains data structures and control flow before executing tests.\n"
        "- id: live_mutation\n"
        "  title: 'Step 3: Live Mutation & Edge-Case Verification'\n"
        "  points: 50\n"
        "  checks:\n"
        "  - Inject a live boundary modification on the spot and verify deterministic behavior.\n"
    )
    _write_if_changed(target_dir / "scale.yml", scale_txt)
    return target_dir


def _sanitize_c_candidate(code: str) -> str:
    txt = code
    if '#include "header.h"' in txt:
        txt = txt.replace('#include "header.h"', "#include <stdio.h>\n#include <stdlib.h>\n#include <unistd.h>")
    # If two complete files with main() were concatenated (e.g. aff_a.c), keep the second clean block
    mains = list(re.finditer(r"\bint\s+main\s*\(", txt))
    if len(mains) > 1:
        second_inc = txt.find("#include", mains[0].end())
        if second_inc != -1:
            txt = txt[second_inc:]
    return txt if txt.endswith("\n") else (txt + "\n")


def _synthesize_reference_solution(slug: str, ex_type: str, expected_file: str, prototype: str | None, attached: list[dict[str, Any]]) -> str:
    hdr = HEADER_42_TEMPLATE.format(fname=expected_file[:50])
    if slug == "strlen_sh":
        return '#!/bin/sh\nprintf "%s" "$FT_LINE" | wc -m | tr -d " "\n'
    if slug == "first_word":
        return (
            f"{hdr}#include <unistd.h>\n\n"
            "int\tmain(int argc, char **argv)\n{\n\tint\ti;\n\n"
            "\tif (argc == 2)\n\t{\n\t\ti = 0;\n"
            "\t\twhile (argv[1][i] == ' ' || argv[1][i] == '\\t')\n\t\t\ti++;\n"
            "\t\twhile (argv[1][i] && argv[1][i] != ' ' && argv[1][i] != '\\t')\n"
            "\t\t{\n\t\t\twrite(1, &argv[1][i], 1);\n\t\t\ti++;\n\t\t}\n\t}\n"
            "\twrite(1, \"\\n\", 1);\n\treturn (0);\n}\n"
        )
    if slug == "ft_atoi":
        return (
            f"{hdr}int\tft_atoi(const char *str)\n{{\n\tint\ti;\n\tint\tsign;\n\tlong\tres;\n\n"
            "\ti = 0;\n\tsign = 1;\n\tres = 0;\n"
            "\twhile (str[i] == ' ' || (str[i] >= 9 && str[i] <= 13))\n\t\ti++;\n"
            "\tif (str[i] == '-' || str[i] == '+')\n\t{\n\t\tif (str[i] == '-')\n\t\t\tsign = -1;\n\t\ti++;\n\t}\n"
            "\twhile (str[i] >= '0' && str[i] <= '9')\n\t{\n\t\tres = res * 10 + (str[i] - '0');\n\t\ti++;\n\t}\n"
            "\treturn (res * sign);\n}\n"
        )
    if slug == "ft_itoa":
        return (
            f"{hdr}#include <stdlib.h>\n\n"
            "static int\tft_numlen(long n)\n{\n\tint\tlen;\n\n\tlen = (n <= 0) ? 1 : 0;\n"
            "\twhile (n != 0)\n\t{\n\t\tn /= 10;\n\t\tlen++;\n\t}\n\treturn (len);\n}\n\n"
            "char\t*ft_itoa(int nbr)\n{\n\tlong\tn;\n\tint\t\tlen;\n\tchar\t*str;\n\n"
            "\tn = nbr;\n\tlen = ft_numlen(n);\n\tstr = (char *)malloc(sizeof(char) * (len + 1));\n"
            "\tif (!str)\n\t\treturn (NULL);\n\tstr[len] = '\\0';\n\tif (n == 0)\n\t\tstr[0] = '0';\n"
            "\tif (n < 0)\n\t{\n\t\tstr[0] = '-';\n\t\tn = -n;\n\t}\n"
            "\twhile (n > 0)\n\t{\n\t\tstr[--len] = (char)((n % 10) + '0');\n\t\tn /= 10;\n\t}\n"
            "\treturn (str);\n}\n"
        )

    candidates: list[str] = []
    for item in attached or []:
        fname = str(item.get("filename") or "")
        content = str(item.get("content") or "")
        if not content.strip():
            continue
        if fname == "tests.yml" or fname.endswith((".yml", ".yaml", ".txt", "_MAIN.c", "tester.sh", ".h")):
            continue
        candidates.append(_sanitize_c_candidate(content) if ex_type in ("c_program", "c_function") else (content if content.endswith("\n") else content + "\n"))

    if candidates:
        for cand in candidates:
            if "fprime_recursive" in cand and "void\tfprime(" not in cand and "void fprime(" not in cand:
                continue
            return cand
        return candidates[0]

    if ex_type == "shell":
        return "#!/bin/sh\nset -eu\nprintf 'OK\\n'\n"
    if ex_type == "c_header":
        guard = re.sub(r"[^A-Z0-9_]", "_", expected_file.upper())
        return f"{hdr}#ifndef {guard}\n# define {guard}\n\n#endif\n"
    if ex_type == "cpp":
        return "#include <iostream>\n\nint main(void)\n{\n\tstd::cout << \"OK\" << std::endl;\n\treturn (0);\n}\n"
    if ex_type == "c_function":
        proto = (_clean_c_prototype(prototype, slug, ex_type) or f"int\t{slug}(void)").strip().rstrip(";")
        if proto.startswith("void") and "*" not in proto.split("(")[0]:
            return f"{hdr}{proto}\n{{\n\treturn ;\n}}\n"
        if "*" in proto.split("(")[0]:
            return f"{hdr}#include <stddef.h>\n\n{proto}\n{{\n\treturn (NULL);\n}}\n"
        return f"{hdr}{proto}\n{{\n\treturn (0);\n}}\n"
    return f"{hdr}#include <unistd.h>\n\nint\tmain(int argc, char **argv)\n{{\n\t(void)argc;\n\t(void)argv;\n\twrite(1, \"OK\\n\", 3);\n\treturn (0);\n}}\n"


def _build_executable_fixed_tests(slug: str, ex_type: str, extracted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if slug in CANONICAL_FIXED_TESTS:
        return CANONICAL_FIXED_TESTS[slug]

    import ast
    fixed_rows = [r for r in (extracted or []) if r.get("source") == "tests.yml (fixed_tests)"]
    if not fixed_rows:
        fixed_rows = (extracted or [])[:6]

    out: list[dict[str, Any]] = []
    for idx_t, row in enumerate(fixed_rows[:12], 1):
        tname = str(row.get("id") or f"T{idx_t:02d}")
        desc = str(row.get("desc") or "Nominal functional test")
        raw_in = str(row.get("input") or "").strip()
        raw_exp = str(row.get("expected") or "")
        cat = str(row.get("category") or "Functional")
        exp_val = _unescape_catalog_str(raw_exp)

        if ex_type == "c_program":
            args_list: list[str] = []
            if raw_in.startswith("[") and raw_in.endswith("]"):
                try:
                    parsed_a = ast.literal_eval(raw_in)
                    if isinstance(parsed_a, list):
                        args_list = [_unescape_catalog_str(str(x)) for x in parsed_a]
                except Exception:
                    args_list = []
            elif "no CLI arguments" in raw_in or "argc == 1" in raw_in:
                args_list = []
            out.append(
                {
                    "name": tname,
                    "description": desc,
                    "args": args_list,
                    "expected": exp_val,
                    "category": cat,
                }
            )
        elif ex_type == "c_function":
            clean_in = raw_in[1:-1] if (raw_in.startswith("`") and raw_in.endswith("`") and len(raw_in) >= 2) else raw_in
            stdout_val = exp_val if exp_val.endswith("\n") else (exp_val + "\n")
            if ";" in clean_in or "printf" in clean_in:
                out.append(
                    {
                        "name": tname,
                        "description": desc,
                        "call": clean_in,
                        "stdout": stdout_val,
                        "category": cat,
                    }
                )
            else:
                out.append(
                    {
                        "name": tname,
                        "description": desc,
                        "expr": clean_in,
                        "stdout": stdout_val,
                        "category": cat,
                    }
                )
        else:
            out.append(
                {
                    "name": tname,
                    "description": desc,
                    "args": [],
                    "input": raw_in,
                    "expected": exp_val,
                    "category": cat,
                }
            )
    return out


def materialize_all_402_exercises(catalog_path: Path | None = None) -> Dict[str, int]:
    if catalog_path is None:
        catalog_path = KIT_ROOT.parent / "src" / "data" / "exerciseCatalog402.json"
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    exercises = data["exercises"]

    piscine_by_mod: Dict[str, List[Dict[str, Any]]] = {}
    exam_by_mod: Dict[str, List[Dict[str, Any]]] = {}
    piscine_count = 0
    exam_count = 0

    for ex in exercises:
        slug = ex["name"]
        ex_type = ex["type"]
        track = ex["track"]
        mod_code = ex.get("moduleCode") or "C 00"
        est_hours = float(ex.get("estimatedHours") or 1.0)
        xp_val = calculate_exercise_xp(mod_code, ex_type, est_hours)

        is_piscine = track.startswith("1.")
        if is_piscine:
            mod_slug = MODULE_SLUG_MAP.get(mod_code, re.sub(r"[^a-z0-9]+", "", mod_code.lower()))
            category = f"piscine/{mod_slug}"
            piscine_by_mod.setdefault(mod_slug, []).append({"slug": slug, "mod_code": mod_code, "xp": xp_val})
            piscine_count += 1
        else:
            category = "exams"
            exam_by_mod.setdefault(mod_code, []).append({"slug": slug, "mod_code": mod_code, "xp": xp_val})
            exam_count += 1

        raw_exp = str(ex.get("expectedFiles") or "").strip()
        if not raw_exp or "/" in raw_exp:
            ext = ".sh" if ex_type == "shell" and not slug.endswith(".sh") else ("" if "." in slug else (".cpp" if ex_type == "cpp" else ".c"))
            exp_files = [f"{slug}{ext}"]
        else:
            exp_files = [tok.strip(",") for tok in raw_exp.split() if tok.strip(",")]
            if not exp_files:
                exp_files = [f"{slug}.c"]

        attached = ex.get("attachedCodeSamples") or []
        raw_tests_yml = None
        for item in attached:
            if item.get("filename") == "tests.yml" and item.get("content"):
                try:
                    raw_tests_yml = _fast_yaml_load(str(item["content"]))
                except Exception:
                    raw_tests_yml = None
                break

        fixed_tests = _build_executable_fixed_tests(slug, ex_type, ex.get("extractedTests") or [])
        edge_tests: List[Dict[str, Any]] = []
        for idx_g, gap in enumerate(ex.get("missingGaps") or [], 1):
            edge_tests.append(
                {
                    "name": f"edge_{idx_g:02d}_{gap.get('code', '[B]').strip('[]')}",
                    "code": str(gap.get("code") or "[B]"),
                    "title": str(gap.get("title") or "Boundary case"),
                    "input": str(gap.get("input") or ""),
                    "expected": str(gap.get("expected") or ""),
                }
            )

        subj_dir = scaffold_exercise(
            slug=slug,
            ex_type=ex_type,
            category=category,
            allowed=str(ex.get("allowedFunctions") or "write"),
            expected_files=exp_files,
            xp=xp_val,
            module_code=mod_code,
            prototype=ex.get("prototype"),
            subject_text=ex.get("subjectText"),
            official_examples=ex.get("officialExamples"),
            attached_samples=attached,
            extracted_tests=ex.get("extractedTests") or [],
            fixed_tests=fixed_tests,
            edge_tests=edge_tests,
            raw_tests_yml=raw_tests_yml,
        )

        corr_dir = KIT_ROOT / "corrections" / category / slug
        for item in attached:
            fname = str(item.get("filename") or "")
            if fname.endswith(".h") and item.get("content"):
                h_txt = str(item["content"])
                if not h_txt.endswith("\n"):
                    h_txt += "\n"
                _write_if_changed(corr_dir / fname, h_txt)
                _write_if_changed(subj_dir / fname, h_txt)

        primary_file = exp_files[0]
        ref_content = _synthesize_reference_solution(
            slug,
            ex_type,
            primary_file,
            ex.get("prototype"),
            attached,
        )
        _write_if_changed(corr_dir / primary_file, ref_content)

    # Restore complete Shell 00 (10 ex), Shell 01 (8 ex), and C 00..C 13 exercises from official archive
    import shutil
    import zipfile

    fin_zip_path = KIT_ROOT.parent / "public" / "assets" / "aistudio" / "fin_99fb5bef.zip"
    mod_code_by_slug = {v: k for k, v in MODULE_SLUG_MAP.items()}
    if fin_zip_path.is_file():
        target_piscine_mods = ["shell00", "shell01"] + [f"c{i:02d}" for i in range(14)]
        with zipfile.ZipFile(fin_zip_path) as zf:
            znames = set(zf.namelist())
            for mod_slug in target_piscine_mods:
                mod_code = mod_code_by_slug.get(mod_slug, mod_slug.upper())
                mod_subj_root = KIT_ROOT / "subjects" / "piscine" / mod_slug
                mod_subj_root.mkdir(parents=True, exist_ok=True)
                existing_lower = {
                    p.name.lower() for p in mod_subj_root.iterdir() if p.is_dir()
                }
                prefix = f"fin/1337-deepthought-kit-v2.1.0/subjects/piscine/{mod_slug}/"
                slugs_in_zip = sorted(
                    {
                        n[len(prefix) :].split("/")[0]
                        for n in znames
                        if n.startswith(prefix) and n.endswith("/meta.yml")
                    }
                )
                for z_slug in slugs_in_zip:
                    norm_low = z_slug.lower()
                    if norm_low in existing_lower or (norm_low == "c00_ft_putnbr" and "ft_putnbr" in existing_lower):
                        continue
                    z_meta_raw = _fast_yaml_load(
                        zf.read(f"{prefix}{z_slug}/meta.yml").decode("utf-8", "replace")
                    ) or {}
                    z_subj_txt = zf.read(f"{prefix}{z_slug}/subject.en.txt").decode("utf-8", "replace")
                    z_tests_raw = None
                    if f"{prefix}{z_slug}/tests.yml" in znames:
                        z_tests_raw = _fast_yaml_load(
                            zf.read(f"{prefix}{z_slug}/tests.yml").decode("utf-8", "replace")
                        )
                    z_type = str(z_meta_raw.get("type") or ("shell" if mod_slug.startswith("shell") else "c_function"))
                    if z_type not in ("c_function", "c_program", "c_header", "makefile", "shell", "python", "cpp"):
                        z_type = "shell" if mod_slug.startswith("shell") else "c_function"
                    z_exp_files = [str(x) for x in (z_meta_raw.get("expected_files") or [z_slug])]
                    z_allowed_list = z_meta_raw.get("allowed_functions") or []
                    z_allowed = ", ".join(str(x) for x in z_allowed_list) if z_allowed_list else "None"
                    xp_val = calculate_exercise_xp(mod_code, z_type, 1.0)

                    sdir = scaffold_exercise(
                        slug=z_slug,
                        ex_type=z_type,
                        category=f"piscine/{mod_slug}",
                        allowed=z_allowed,
                        expected_files=z_exp_files,
                        xp=xp_val,
                        module_code=mod_code,
                        prototype=z_meta_raw.get("prototype"),
                        subject_text=z_subj_txt,
                        official_examples="",
                        attached_samples=[],
                        extracted_tests=[],
                        fixed_tests=None,
                        edge_tests=[],
                        raw_tests_yml=z_tests_raw,
                    )
                    # Copy extra subject attachments (e.g., a, sw.diff, resources.tar.gz in shell00/diff)
                    for extra_f in ("a", "sw.diff", "resources.tar.gz"):
                        z_extra = f"{prefix}{z_slug}/{extra_f}"
                        if z_extra in znames:
                            (sdir / extra_f).write_bytes(zf.read(z_extra))

                    # Copy reference correction files from archive
                    corr_prefix = f"fin/1337-deepthought-kit-v2.1.0/corrections/piscine/{mod_slug}/{z_slug}/"
                    cdir = KIT_ROOT / "corrections" / "piscine" / mod_slug / z_slug
                    cdir.mkdir(parents=True, exist_ok=True)
                    copied_corr = 0
                    for cn in znames:
                        if cn.startswith(corr_prefix) and not cn.endswith("/"):
                            rel_cn = cn[len(corr_prefix) :]
                            out_cf = cdir / rel_cn
                            out_cf.parent.mkdir(parents=True, exist_ok=True)
                            out_cf.write_bytes(zf.read(cn))
                            copied_corr += 1
                    if copied_corr == 0:
                        _write_if_changed(cdir / z_exp_files[0], "#!/bin/sh\nexit 0\n")

                    piscine_by_mod.setdefault(mod_slug, []).append(
                        {"slug": z_slug, "mod_code": mod_code, "xp": xp_val}
                    )
                    existing_lower.add(norm_low)
                    piscine_count += 1

    # Copy all 20 Official Piscine PDFs into their respective module folders under subjects/piscine/<mod>/
    pdf_assets_dir = KIT_ROOT.parent / "public" / "assets" / "aistudio"
    piscine_pdf_map = {
        "shell00": [("Shell_00_b8b1931c.pdf", "Shell_00.pdf")],
        "shell01": [("Shell_01_e79db9db.pdf", "Shell_01.pdf")],
        "c00": [("C_00_51aee973.pdf", "C_00.pdf")],
        "c01": [("C_01_4f3d23aa.pdf", "C_01.pdf")],
        "c02": [("C_02_1dd09650.pdf", "C_02.pdf")],
        "c03": [("C_03_0bd00dcc.pdf", "C_03.pdf")],
        "c04": [("C_04_c973c492.pdf", "C_04.pdf")],
        "c05": [("C_05_853af0d2.pdf", "C_05.pdf")],
        "c06": [("C_06_56468c07.pdf", "C_06.pdf")],
        "c07": [("C_07_2531869c.pdf", "C_07.pdf")],
        "c08": [("C_08_278fd570.pdf", "C_08.pdf")],
        "c09": [("C_09_e1fa61d1.pdf", "C_09.pdf")],
        "c10": [("C_10_da7d8a90.pdf", "C_10.pdf")],
        "c11": [("C_11_a994e104.pdf", "C_11.pdf")],
        "c12": [("C_12_576145ea.pdf", "C_12.pdf")],
        "c13": [("C_13_9d7e3655.pdf", "C_13.pdf")],
        "rush_bsq": [
            ("rush00.en_171d2a09.pdf", "rush00.en.pdf"),
            ("rush01.en_48e53dd5.pdf", "rush01.en.pdf"),
            ("rush_02.en_fa91ab44.pdf", "rush_02.en.pdf"),
            ("bsq.en_2fcbe3ae.pdf", "bsq.en.pdf"),
        ],
    }
    for mod_slug, pdf_pairs in piscine_pdf_map.items():
        mod_dir = KIT_ROOT / "subjects" / "piscine" / mod_slug
        mod_dir.mkdir(parents=True, exist_ok=True)
        for src_pdf_name, dst_pdf_name in pdf_pairs:
            src_pdf = pdf_assets_dir / src_pdf_name
            dst_pdf = mod_dir / dst_pdf_name
            if src_pdf.is_file() and (not dst_pdf.is_file() or dst_pdf.stat().st_size != src_pdf.stat().st_size):
                shutil.copy2(src_pdf, dst_pdf)

    write_canonical_pools(KIT_ROOT)

    return {
        "total": piscine_count + exam_count,
        "piscine": piscine_count,
        "exams": exam_count,
        "piscine_pools": len(list((KIT_ROOT / "pools" / "piscine").glob("*.yml"))),
        "exam_pools": len(list((KIT_ROOT / "pools" / "exams").glob("*.yml"))),
    }


CANONICAL_PISCINE_ORDER: Dict[str, List[str]] = {
    "shell00": ["z", "testShell00", "exo2", "id_rsa_pub", "midls", "git_commit.sh", "git_ignore.sh", "diff", "clean", "ft_magic"],
    "shell01": ["print_groups.sh", "find_sh.sh", "count_files.sh", "mac.sh", "special_filename_MaRViN", "skip.sh", "r_dwssap.sh", "add_chelou.sh"],
    "c00": ["ft_putchar", "ft_print_alphabet", "ft_print_reverse_alphabet", "ft_print_numbers", "ft_is_negative", "ft_print_comb", "ft_print_comb2", "ft_putnbr", "ft_print_combn"],
    "c01": ["ft_ft", "ft_ultimate_ft", "ft_swap", "ft_div_mod", "ft_ultimate_div_mod", "c01_ft_putstr", "c01_ft_strlen", "ft_rev_int_tab", "ft_sort_int_tab"],
    "c02": ["ft_strcpy", "ft_strncpy", "ft_str_is_alpha", "ft_str_is_numeric", "ft_str_is_lowercase", "ft_str_is_uppercase", "ft_str_is_printable", "ft_strupcase", "ft_strlowcase", "ft_strcapitalize", "ft_strlcpy", "ft_putstr_non_printable", "ft_print_memory"],
    "c03": ["ft_strcmp", "ft_strncmp", "ft_strcat", "ft_strncat", "ft_strstr", "ft_strlcat"],
    "c04": ["ft_strlen", "ft_putstr", "ft_putnbr", "ft_atoi", "ft_putnbr_base", "ft_atoi_base"],
    "c05": ["ft_iterative_factorial", "ft_recursive_factorial", "ft_iterative_power", "ft_recursive_power", "ft_fibonacci", "ft_sqrt", "ft_is_prime", "ft_find_next_prime", "ft_ten_queens_puzzle"],
    "c06": ["ft_print_program_name", "ft_print_params", "ft_rev_params", "ft_sort_params"],
    "c07": ["ft_strdup", "ft_range", "ft_ultimate_range", "ft_strjoin", "ft_convert_base", "ft_split", "ft_split_whitespaces"],
    "c08": ["ft.h", "ft_boolean.h", "ft_abs.h", "ft_point.h", "ft_strs_to_tab", "ft_show_tab"],
    "c09": ["c09_libft", "c09_makefile", "c09_ft_split"],
    "c10": ["display_file", "cat", "tail", "hexdump"],
    "c11": ["ft_foreach", "ft_map", "ft_any", "ft_count_if", "ft_is_sort", "do-op", "ft_sort_string_tab", "ft_advanced_sort_string_tab"],
    "c12": ["ft_create_elem", "ft_list_push_front", "ft_list_size", "ft_list_last", "ft_list_push_back", "ft_list_push_strs", "ft_list_clear", "ft_list_at", "ft_list_reverse", "ft_list_foreach", "ft_list_foreach_if", "ft_list_find", "ft_list_remove_if", "ft_list_merge", "ft_list_sort", "ft_list_reverse_fun", "ft_sorted_list_insert", "ft_sorted_list_merge"],
    "c13": ["btree_create_node", "btree_apply_prefix", "btree_apply_infix", "btree_apply_suffix", "btree_insert_data", "btree_search_item", "btree_level_count", "btree_apply_by_level"],
    "rush_bsq": ["rush00", "rush01", "rush02", "bsq", "colle02", "sastantua", "match_n_match", "sudoku"],
}


def write_canonical_pools(kit_root: Path = KIT_ROOT) -> None:
    """Write authentic 42 / 1337 Piscine module pools and Exam pools."""
    mod_code_by_slug = {v: k for k, v in MODULE_SLUG_MAP.items()}
    piscine_pools_dir = kit_root / "pools" / "piscine"
    piscine_pools_dir.mkdir(parents=True, exist_ok=True)

    for mod_slug, ordered_slugs in CANONICAL_PISCINE_ORDER.items():
        mod_dir = kit_root / "subjects" / "piscine" / mod_slug
        if not mod_dir.is_dir():
            continue
        mod_code = mod_code_by_slug.get(mod_slug, mod_slug.upper())
        existing = [p.name for p in mod_dir.iterdir() if p.is_dir() and (p / "meta.yml").exists()]
        final_slugs = [s for s in ordered_slugs if s in existing] + [s for s in sorted(existing) if s not in ordered_slugs]
        exercises_list = []
        for idx, s in enumerate(final_slugs):
            m_yml = _fast_yaml_load((mod_dir / s / "meta.yml").read_text(encoding="utf-8")) or {}
            xp_val = int(m_yml.get("xp") or 100)
            exercises_list.append(
                {
                    "ex": f"ex{idx:02d}",
                    "subject_id": f"piscine/{mod_slug}/{s}",
                    "xp": xp_val,
                }
            )
        pool_payload = {
            "id": mod_slug,
            "display_name": f"1337 / 42 Piscine — {mod_code}",
            "exercises": exercises_list,
        }
        _write_if_changed(piscine_pools_dir / f"{mod_slug}.yml", _fast_yaml_dump(pool_payload))

    # Authentic 42 / 1337 Piscine & Common Core Exam Level Tiers
    lvl_0_1_warmup = ["aff_a", "maff_alpha", "ft_countdown", "ft_print_numbers", "hello", "only_z", "aff_z", "only_a", "maff_revalpha", "aff_first_param", "aff_last_param"]
    lvl_2_3_basic = ["rev_print", "rot_13", "rotone", "ulstr", "first_word", "ft_strlen", "ft_swap", "ft_strcpy", "ft_putstr", "repeat_alpha", "search_and_replace", "fizzbuzz"]
    lvl_4_5_inter = ["inter", "union", "wdmatch", "last_word", "alpha_mirror", "do_op", "ft_atoi", "ft_strdup", "max", "is_power_of_2", "print_bits", "reverse_bits", "swap_bits", "camel_to_snake", "snake_to_camel", "ft_strcmp", "ft_strcspn", "ft_strpbrk", "ft_strrev"]
    lvl_6_7_math_list = ["add_prime_sum", "epur_str", "expand_str", "ft_list_size", "ft_range", "ft_rrange", "hidenp", "lcm", "paramsum", "pgcd", "print_hex", "rstr_capitalizer", "str_capitalizer", "tab_mult", "ft_atoi_base"]
    lvl_8_10_advanced = ["fprime", "ft_itoa", "ft_split", "rev_wstr", "rostring", "sort_int_tab", "sort_list", "ft_list_remove_if", "ft_list_foreach", "brainfuck", "print_memory"]

    exam00_levels = [
        {"level": 0, "points": 25, "candidates": ["only_z", "only_a", "hello", "aff_a", "aff_z", "ft_countdown", "ft_print_numbers", "maff_alpha", "maff_revalpha"]},
        {"level": 1, "points": 25, "candidates": ["aff_first_param", "aff_last_param", "ft_strlen", "ft_swap", "ft_strcpy", "ft_putstr", "rev_print"]},
        {"level": 2, "points": 25, "candidates": ["rot_13", "rotone", "ulstr", "first_word", "repeat_alpha", "search_and_replace", "fizzbuzz"]},
        {"level": 3, "points": 25, "candidates": ["inter", "union", "wdmatch", "last_word", "alpha_mirror", "ft_atoi", "ft_strdup", "ft_strrev"]},
    ]
    exam01_levels = [
        {"level": 0, "points": 20, "candidates": lvl_0_1_warmup},
        {"level": 1, "points": 20, "candidates": lvl_2_3_basic},
        {"level": 2, "points": 20, "candidates": lvl_4_5_inter},
        {"level": 3, "points": 20, "candidates": lvl_6_7_math_list},
        {"level": 4, "points": 20, "candidates": ["fprime", "ft_itoa", "ft_split", "rev_wstr", "rostring", "sort_int_tab", "sort_list", "ft_list_remove_if", "ft_list_foreach"]},
    ]
    exam02_levels = [
        {"level": 0, "points": 16, "candidates": lvl_0_1_warmup},
        {"level": 1, "points": 16, "candidates": lvl_2_3_basic},
        {"level": 2, "points": 16, "candidates": lvl_4_5_inter},
        {"level": 3, "points": 16, "candidates": lvl_6_7_math_list},
        {"level": 4, "points": 18, "candidates": ["fprime", "ft_itoa", "ft_split", "rev_wstr", "rostring", "sort_int_tab", "sort_list", "ft_list_remove_if", "ft_list_foreach"]},
        {"level": 5, "points": 18, "candidates": ["brainfuck", "print_memory", "ft_atoi_base"]},
    ]
    final_exam_levels = [
        {"level": 0, "points": 10, "candidates": ["only_z", "only_a", "hello", "aff_a", "aff_z", "ft_countdown", "ft_print_numbers"]},
        {"level": 1, "points": 10, "candidates": ["maff_alpha", "maff_revalpha", "aff_first_param", "aff_last_param", "ft_strlen", "ft_swap", "ft_strcpy", "ft_putstr"]},
        {"level": 2, "points": 10, "candidates": ["rev_print", "rot_13", "rotone", "ulstr", "first_word", "repeat_alpha", "search_and_replace", "fizzbuzz"]},
        {"level": 3, "points": 10, "candidates": ["inter", "union", "wdmatch", "last_word", "alpha_mirror", "camel_to_snake", "snake_to_camel"]},
        {"level": 4, "points": 10, "candidates": ["do_op", "ft_atoi", "ft_strdup", "max", "is_power_of_2", "print_bits", "reverse_bits", "swap_bits", "ft_strcmp", "ft_strcspn", "ft_strpbrk", "ft_strrev"]},
        {"level": 5, "points": 10, "candidates": ["add_prime_sum", "epur_str", "expand_str", "hidenp", "paramsum", "pgcd", "lcm", "print_hex", "tab_mult"]},
        {"level": 6, "points": 10, "candidates": ["ft_list_size", "ft_range", "ft_rrange", "rstr_capitalizer", "str_capitalizer", "ft_atoi_base"]},
        {"level": 7, "points": 10, "candidates": ["fprime", "ft_itoa", "ft_split", "rev_wstr", "rostring"]},
        {"level": 8, "points": 10, "candidates": ["sort_int_tab", "sort_list", "ft_list_remove_if", "ft_list_foreach"]},
        {"level": 9, "points": 10, "candidates": ["brainfuck", "print_memory", "ft_split", "sort_list", "ft_list_remove_if"]},
    ]
    rank02_levels = [
        {"level": 0, "points": 25, "candidates": lvl_2_3_basic},
        {"level": 1, "points": 25, "candidates": lvl_4_5_inter},
        {"level": 2, "points": 25, "candidates": lvl_6_7_math_list},
        {"level": 3, "points": 25, "candidates": lvl_8_10_advanced},
    ]
    rank03_06_levels = [
        {"level": 0, "points": 25, "candidates": ["filter", "broken_gnl", "get_next_line", "ft_printf", "scanf"]},
        {"level": 1, "points": 25, "candidates": ["n_queens", "permutations", "powerset", "rip", "tsp"]},
        {"level": 2, "points": 25, "candidates": ["ft_popen", "picoshell", "sandbox", "vbc", "argo"]},
        {"level": 3, "points": 25, "candidates": ["cpp_module00", "cpp_module01", "cpp_module02", "bigint", "polyset", "vect2", "bsq", "life", "mini_serv", "mini_db"]},
    ]

    exam_pools_dir = kit_root / "pools" / "exams"
    exam_pools_dir.mkdir(parents=True, exist_ok=True)
    exam_specs = {
        "c_piscine_exam_00": ("42 / 1337 C Piscine — Exam 00 (Starter)", 14400, exam00_levels),
        "c_piscine_exam_01": ("42 / 1337 C Piscine — Exam 01 (Intermediate)", 14400, exam01_levels),
        "c_piscine_exam_02": ("42 / 1337 C Piscine — Exam 02 (Advanced)", 14400, exam02_levels),
        "c_piscine_final_exam": ("42 / 1337 C Piscine — Final Exam (8 Hours)", 28800, final_exam_levels),
        "1337_classic_exam00": ("1337 Classic Piscine — Exam 00", 14400, exam00_levels),
        "1337_classic_exam01": ("1337 Classic Piscine — Exam 01", 14400, exam01_levels),
        "1337_classic_exam02": ("1337 Classic Piscine — Exam 02", 14400, exam02_levels),
        "1337_classic_examfinal": ("1337 Classic Piscine — Final Exam", 28800, final_exam_levels),
        "classic_42_full": ("42 / 1337 Common Core — Exam Rank 02", 14400, rank02_levels),
        "cursus_rank03_06": ("42 / 1337 Common Core — Exam Ranks 03–06", 14400, rank03_06_levels),
    }
    for pool_id, (title, dur, lvls) in exam_specs.items():
        _write_if_changed(
            exam_pools_dir / f"{pool_id}.yml",
            _fast_yaml_dump(
                {
                    "name": pool_id,
                    "display_name": title,
                    "duration_seconds": dur,
                    "levels": lvls,
                }
            ),
        )




def export_clean_student_package(dest_dir: Path, category_filter: str | None = None) -> Dict[str, int]:
    """Export a clean student workspace package containing ONLY subject.en.txt, examples.txt,
    official module PDFs, public .h headers, student CLI tools (norminette, shnorm, ft_lock, bc, ifconfig),
    and an empty rendu/ workspace. Excludes all HTML files, tests.yml, meta.yml, scale.yml, and corrections.
    """
    import shutil

    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "subjects").mkdir(parents=True, exist_ok=True)
    (dest_dir / "rendu").mkdir(parents=True, exist_ok=True)
    (dest_dir / "bin").mkdir(parents=True, exist_ok=True)
    (dest_dir / "deepthought").mkdir(parents=True, exist_ok=True)

    # Copy only safe student-facing linter modules, vendored PyYAML, & CLI tools (never grader/tests/corrections)
    for mod_name in ("__init__.py", "ui_theme.py", "catalog.py", "progression.py"):
        src_mod = KIT_ROOT / "deepthought" / mod_name
        if src_mod.is_file():
            shutil.copy2(src_mod, dest_dir / "deepthought" / mod_name)
    yaml_src = KIT_ROOT / "yaml"
    if yaml_src.is_dir():
        dest_yaml = dest_dir / "yaml"
        dest_yaml.mkdir(parents=True, exist_ok=True)
        for yf in sorted(yaml_src.glob("*.py")):
            shutil.copy2(yf, dest_yaml / yf.name)
    for bin_name in ("norminette", "shnorm", "ft_lock", "bc", "ifconfig"):
        src_bin = KIT_ROOT / "bin" / bin_name
        if src_bin.is_file():
            shutil.copy2(src_bin, dest_dir / "bin" / bin_name)

    base_subjects = (KIT_ROOT / "subjects" / category_filter) if category_filter else (KIT_ROOT / "subjects")
    subj_count = 0
    for subj_txt in sorted(base_subjects.rglob("subject.en.txt")):
        rel_dir = subj_txt.parent.relative_to(KIT_ROOT / "subjects")
        out_sub = dest_dir / "subjects" / rel_dir
        out_sub.mkdir(parents=True, exist_ok=True)
        shutil.copy2(subj_txt, out_sub / "subject.en.txt")
        ex_txt = subj_txt.parent / "examples.txt"
        if ex_txt.is_file():
            shutil.copy2(ex_txt, out_sub / "examples.txt")
        for hdr_f in subj_txt.parent.rglob("*.h"):
            rel_h = hdr_f.relative_to(subj_txt.parent)
            out_h = out_sub / rel_h
            out_h.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(hdr_f, out_h)
        subj_count += 1

    for pdf_f in sorted(base_subjects.rglob("*.pdf")):
        rel_pdf = pdf_f.relative_to(KIT_ROOT / "subjects")
        out_pdf = dest_dir / "subjects" / rel_pdf
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf_f, out_pdf)

    return {"subjects_exported": subj_count}


def export_developer_review_package(
    dest_dir: Path,
    archive_base: Path | None = None,
) -> Dict[str, Any]:
    """Export the complete Developer Review Package containing all 402 exercises,
    subject.en.txt (with appended examples), examples.txt, meta.yml, tests.yml
    (with subject_example, folder_example, and near_example tiers), scale.yml,
    reference corrections/, pools/, deepthought/, bin/, bocal/, templates/, and tests/,
    while strictly removing ONLY .html files (and __pycache__ / .pyc).
    """
    import shutil
    import tarfile
    import zipfile

    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied_files = 0
    skipped_html = 0
    for src_path in sorted(KIT_ROOT.rglob("*")):
        rel = src_path.relative_to(KIT_ROOT)
        if any(part in ("__pycache__", "archives", "toolchain", "suites", "build") or part.startswith(".pytest") for part in rel.parts):
            continue
        if src_path.is_file():
            if src_path.suffix.lower() in (".html", ".htm"):
                skipped_html += 1
                continue
            if src_path.suffix.lower() in (".pyc", ".pyo"):
                continue
            out_file = dest_dir / rel
            out_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, out_file)
            copied_files += 1

    # Include full curriculum & 402-exercise catalog JSON for developer inspection
    cat_src = KIT_ROOT.parent / "src" / "data" / "exerciseCatalog402.json"
    if cat_src.is_file():
        (dest_dir / "data").mkdir(parents=True, exist_ok=True)
        shutil.copy2(cat_src, dest_dir / "data" / "exerciseCatalog402.json")
        copied_files += 1

    tar_gz_path = None
    zip_path = None
    if archive_base is not None:
        archive_base.parent.mkdir(parents=True, exist_ok=True)
        tar_gz_path = Path(f"{archive_base}.tar.gz")
        zip_path = Path(f"{archive_base}.zip")
        with tarfile.open(tar_gz_path, "w:gz") as tf:
            tf.add(dest_dir, arcname="1337-42-developer-review-pack")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(dest_dir.rglob("*")):
                if f.is_file():
                    zf.write(f, arcname=str(Path("1337-42-developer-review-pack") / f.relative_to(dest_dir)))

    return {
        "files_exported": copied_files,
        "html_removed": skipped_html,
        "subjects_exported": len(list((dest_dir / "subjects").rglob("subject.en.txt"))),
        "examples_txt_exported": len(list((dest_dir / "subjects").rglob("examples.txt"))),
        "tests_yml_exported": len(list((dest_dir / "subjects").rglob("tests.yml"))),
        "tar_gz": str(tar_gz_path) if tar_gz_path else "",
        "zip": str(zip_path) if zip_path else "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="pforge — 1337 / 42 Exercise & Pool Blueprint Scaffolder")
    parser.add_argument("--scaffold", metavar="SLUG", help="Create a new 4-component exercise skeleton")
    parser.add_argument("--type", default="c_program", choices=["c_function", "c_program", "c_header", "makefile", "shell", "python", "cpp"], help="Exercise evaluation mode")
    parser.add_argument("--category", default="exams", help="Target category path under subjects/ (e.g. exams or piscine/c00)")
    parser.add_argument("--allowed", default="write", help="Comma-separated allowed functions or commands")
    parser.add_argument("--files", default="", help="Space-separated expected files (defaults to <slug>.c or <slug>.sh)")
    parser.add_argument("--materialize-all", action="store_true", help="Materialize all 402 exercises, corrections, and pools from catalog")
    parser.add_argument("--export-student-pack", metavar="DIR", help="Export clean student package without tests, corrections, or HTML")
    parser.add_argument("--export-dev-pack", metavar="DIR", help="Export full developer review package with all 402 exercises, examples, tests, and corrections (HTML removed)")
    parser.add_argument("--archive-base", metavar="BASE_PATH", help="Optional base path for .tar.gz and .zip archives when exporting developer pack")
    parser.add_argument("--status", action="store_true", help="Display current engine structure status")
    args = parser.parse_args(argv)

    if args.export_dev_pack:
        arch = Path(args.archive_base) if args.archive_base else None
        res = export_developer_review_package(Path(args.export_dev_pack), archive_base=arch)
        print(
            f"[pforge] Exported Developer Review Package ({res['subjects_exported']} subjects, "
            f"{res['examples_txt_exported']} examples.txt, {res['tests_yml_exported']} tests.yml, "
            f"{res['files_exported']} total files, 0 HTML files) to: {args.export_dev_pack}"
        )
        if res["tar_gz"]:
            print(f"[pforge] Created TAR.GZ archive: {res['tar_gz']}")
            print(f"[pforge] Created ZIP archive   : {res['zip']}")
        return 0

    if args.export_student_pack:
        res = export_clean_student_package(Path(args.export_student_pack))
        print(f"[pforge] Exported clean student package ({res['subjects_exported']} subjects) to: {args.export_student_pack}")
        return 0

    if args.materialize_all:
        stats = materialize_all_402_exercises()
        print(
            f"[pforge] Materialized {stats['total']} exercises "
            f"(Exams: {stats['exams']}, Piscine: {stats['piscine']}) "
            f"across {stats['piscine_pools']} Piscine pools and {stats['exam_pools']} Exam pools."
        )
        return 0

    if args.status or not args.scaffold:
        exams_count = len([p for p in (KIT_ROOT / "subjects/exams").glob("*/meta.yml")])
        piscine_count = len([p for p in (KIT_ROOT / "subjects/piscine").rglob("meta.yml")])
        print(f"[pforge] 1337/42 Core Engine Root : {KIT_ROOT}")
        print(f"[pforge] Active Exam Subjects     : {exams_count}")
        print(f"[pforge] Active Piscine Subjects  : {piscine_count}")
        print(f"[pforge] Total Active Subjects    : {exams_count + piscine_count}")
        if not args.scaffold:
            return 0

    slug = args.scaffold.strip()
    default_ext = ".sh" if args.type == "shell" else (".py" if args.type == "python" else (".cpp" if args.type == "cpp" else ".c"))
    exp_files = args.files.split() if args.files.strip() else [f"{slug}{default_ext}"]
    out_dir = scaffold_exercise(slug, args.type, args.category, args.allowed, exp_files)
    print(f"[pforge] Scaffolded 4-component 1337/42 exercise blueprint at: {out_dir}")
    for fname in ["subject.en.txt", "meta.yml", "tests.yml", "scale.yml"]:
        print(f"  -> {out_dir / fname}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

