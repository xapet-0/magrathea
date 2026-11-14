#!/usr/bin/env python3
"""Shared path display and 5-gate Mouli-pipeline scorecard helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deepthought.grader import GradeReport
    from deepthought.ui_theme import ThemeEngine


_GATE4_MARKERS = (
    "Segmentation fault",
    "Bus error",
    "Abort",
    "Floating point",
    "Timeout",
    "Output limit",
    "Redzone KO",
    "Leak KO",
    "Free KO",
    "Strict KO",
    "Exit 42",
    "Exit 43",
)


def tilde_path(p: Path | str) -> str:
    """Format an absolute path using '~' without dereferencing exNN symlinks."""
    try:
        expanded = str(Path(p).expanduser())
        resolved = os.path.abspath(expanded)
    except Exception:
        resolved = str(p)
    home = os.path.abspath(str(Path.home()))
    if resolved == home:
        return "~"
    if resolved.startswith(home + "/"):
        return "~" + resolved[len(home) :]
    return resolved


def classify_five_gates(
    status: str, passed: bool
) -> tuple[bool, bool, bool, bool, bool]:
    """Return (gate1_fail, gate2_fail, gate3_fail, gate4_fail, gate5_fail)."""
    g1_fail = (
        "Nothing turned in" in status
        or "main() in function" in status
        or "Extraneous file" in status
    )
    g2_fail = "Cheating" in status or "Norme error" in status
    g3_fail = status.startswith("Does not compile") or "Makefile" in status
    g4_fail = any(marker in status for marker in _GATE4_MARKERS)
    g5_fail = not passed and not (g1_fail or g2_fail or g3_fail or g4_fail)
    return g1_fail, g2_fail, g3_fail, g4_fail, g5_fail


def render_five_gate_scorecard(
    report: GradeReport,
    theme: ThemeEngine,
    is_exam: bool = False,
    norm_enabled: bool = False,
    *,
    header: str = "5-gate moulinette pipeline",
    gate5_desc: str = "deepthought torture matrix & cat -e diff",
    style: str = "dots",
) -> str:
    """Render the 5-gate grading scorecard cleanly for CLI and exam outputs."""
    st = report.status
    g1_fail, g2_fail, g3_fail, g4_fail, g5_fail = classify_five_gates(st, report.passed)
    show_norm = (not is_exam) or norm_enabled

    if style == "badges":
        norm_tag = " + 42 Norminette" if norm_enabled else ""
        gates = [
            (
                "Gate 1",
                "Turn-in Files & Entry-Point Check (no leftover main)",
                not g1_fail,
                g1_fail,
            ),
            (
                "Gate 2",
                f"ELF Symbol Whitelist (nm -u){norm_tag}",
                not (g1_fail or g2_fail),
                g2_fail,
            ),
            (
                "Gate 3",
                "Strict Compilation (cc -Wall -Wextra -Werror)",
                not (g1_fail or g2_fail or g3_fail),
                g3_fail,
            ),
            (
                "Gate 4",
                "Process Sandbox, 2.0s Timeout & Signal Isolation",
                not (g1_fail or g2_fail or g3_fail or g4_fail),
                g4_fail,
            ),
            (
                "Gate 5",
                "Deepthought Torture Matrix & cat -e Diff Oracle",
                report.passed,
                g5_fail,
            ),
        ]
        lines = [theme.c("  5-GATE MOULINETTE PIPELINE SCORECARD:", "primary", "bold")]
        stopped = False
        for g_id, g_desc, is_ok, is_fail in gates:
            if stopped:
                badge = theme.c("[SKIP]", "muted")
                desc_s = theme.c(g_desc, "muted")
            elif is_fail:
                badge = theme.c("[FAIL]", "err", "bold")
                desc_s = theme.c(f"{g_desc}  <-- {st}", "err", "bold")
                stopped = True
            elif is_ok:
                badge = theme.c("[PASS]", "ok", "bold")
                desc_s = g_desc
            else:
                badge = theme.c("[SKIP]", "muted")
                desc_s = theme.c(g_desc, "muted")
            lines.append(f"    {badge} {theme.c(g_id, 'accent', 'bold')}: {desc_s}")
        return "\n".join(lines)

    norm_tag = " + norminette" if show_norm else ""
    gates = [
        ("gate 1", "turn-in files & entry point", not g1_fail, g1_fail),
        (
            "gate 2",
            f"elf symbol whitelist (nm -u){norm_tag}",
            not (g1_fail or g2_fail),
            g2_fail,
        ),
        (
            "gate 3",
            "strict compilation (cc -Wall -Wextra -Werror)",
            not (g1_fail or g2_fail or g3_fail),
            g3_fail,
        ),
        (
            "gate 4",
            "process sandbox & signal isolation",
            not (g1_fail or g2_fail or g3_fail or g4_fail),
            g4_fail,
        ),
        ("gate 5", gate5_desc, report.passed, g5_fail),
    ]
    lines = [f"{theme.c('===>', 'accent', 'bold')} {theme.bold(header)}"]
    stopped = False
    for g_id, g_desc, is_ok, is_fail in gates:
        dots = "." * max(2, 48 - len(g_desc))
        if stopped:
            status_s = theme.c("SKIP", "muted")
        elif is_fail:
            status_s = f"{theme.c('KO', 'err', 'bold')} ({st})"
            stopped = True
        elif is_ok:
            status_s = theme.c("OK", "ok", "bold")
        else:
            status_s = theme.c("SKIP", "muted")
        lines.append(
            f"  {theme.c(g_id, 'muted')}  {g_desc} {theme.c(dots, 'muted')} {status_s}"
        )
    return "\n".join(lines)
