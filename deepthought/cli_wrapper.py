#!/usr/bin/env python3
import os
import sys
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent

def run_examshell():
    os.execv(sys.executable, [sys.executable, str(KIT_ROOT / "bin" / "examshell")] + sys.argv[1:])

def run_moulinette():
    os.execv(sys.executable, [sys.executable, str(KIT_ROOT / "bin" / "moulinette")] + sys.argv[1:])

def run_shnorm():
    os.execv(sys.executable, [sys.executable, str(KIT_ROOT / "bin" / "shnorm")] + sys.argv[1:])
