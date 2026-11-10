"""
deepthought.correction.tests
Provides `gen_tests`, `quote`, `random_word`, `random_string`, and `random_int` called by
authentic 1337/42 ExamPoolRevanced generator.py scripts.
Automatically invokes `compile_expected_program()` in the caller module if defined.
"""
from __future__ import annotations

import json
import os
import random
import shlex
import string
import sys
from pathlib import Path
from typing import Any, Callable


def quote(s: Any) -> str:
    """Shell-quote an argument string for Deepthought test commands."""
    return shlex.quote(str(s))


def random_word(min_len: int = 3, max_len: int = 12) -> str:
    length = random.randint(min_len, max(min_len, max_len))
    return "".join(random.choices(string.ascii_lowercase, k=length))


def random_string(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def random_int(min_val: int = 0, max_val: int = 1000) -> int:
    return random.randint(min_val, max_val)


def quotelist(items: list[Any]) -> str:
    return " ".join(quote(x) for x in items)


def nl(s: str = "") -> str:
    return f"{s}\n"


def random_words(count: int = 5, min_len: int = 3, max_len: int = 10) -> list[str]:
    return [random_word(min_len, max_len) for _ in range(count)]


def gen_tests(tests_spec: dict[Any, Callable[[], Any]]) -> list[dict[str, Any]]:
    random.seed(42)
    caller_globals = sys._getframe(1).f_globals
    comp_fn = caller_globals.get("compile_expected_program")
    if callable(comp_fn):
        comp_fn()

    generated: list[dict[str, Any]] = []
    for key, fn in tests_spec.items():
        key_str = str(key).strip()
        if "-" in key_str:
            parts = key_str.split("-", 1)
            start, end = int(parts[0]), int(parts[1])
            indices = range(start, end + 1)
        else:
            indices = [int(key_str)]
        for idx in indices:
            res = fn() or {}
            items = res if isinstance(res, list) else [res]
            for item in items:
                if not isinstance(item, dict):
                    continue
                cmd_val = item.get("cmd", "")
                out_val = item.get("output", "")
                if isinstance(out_val, bytes):
                    out_val = out_val.decode("utf-8", errors="replace")
                generated.append(
                    {
                        "index": len(generated) + 1,
                        "name": f"test{len(generated) + 1}",
                        "fn_name": getattr(fn, "__name__", f"test_{idx}"),
                        "cmd": str(cmd_val),
                        "output": str(out_val),
                    }
                )

    clean_fn = caller_globals.get("clean")
    if callable(clean_fn):
        try:
            clean_fn()
        except Exception:
            pass

    out_path = Path(os.environ.get("DT_TESTS_OUT", "__dt_generated_tests.json"))
    out_path.write_text(json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8")
    return generated
