#!/usr/bin/env python3
"""Thin CLI entrypoints dispatching to bin/examshell, bin/moulinette, and bin/shnorm."""

import os
from pathlib import Path
import sys

KIT_ROOT = Path(__file__).resolve().parent.parent


def run_examshell() -> None:
    """Execute the standalone examshell CLI entrypoint."""
    os.execv(
        sys.executable,
        [sys.executable, str(KIT_ROOT / "bin" / "examshell")] + sys.argv[1:],
    )


def run_moulinette() -> None:
    """Execute the standalone moulinette CLI entrypoint."""
    os.execv(
        sys.executable,
        [sys.executable, str(KIT_ROOT / "bin" / "moulinette")] + sys.argv[1:],
    )


def run_shnorm() -> None:
    """Execute the standalone shnorm CLI entrypoint."""
    os.execv(
        sys.executable,
        [sys.executable, str(KIT_ROOT / "bin" / "shnorm")] + sys.argv[1:],
    )
