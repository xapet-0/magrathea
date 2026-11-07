#!/usr/bin/env python3
"""
deepthought.progression — Idempotent XP & Level Progression Engine for 1337 / 42.

Guarantees:
1. Deterministic XP calculation per exercise based on module tier and complexity.
2. Zero XP awarded on failed evaluations (KO / grade < 100).
3. Strict Idempotency: re-evaluating an already validated exercise awards +0 XP
   (prevents duplicate XP farming across repeated Moulinette / ExamShell runs).
4. Authentic 42 / 1337 Intra level progression curve.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

MODULE_BASE_XP: Dict[str, int] = {
    "Shell 00": 100,
    "Shell 01": 120,
    "C 00": 100,
    "C 01": 110,
    "C 02": 125,
    "C 03": 135,
    "C 04": 150,
    "C 05": 175,
    "C 06": 140,
    "C 07": 200,
    "C 08": 180,
    "C 09": 220,
    "C 10": 260,
    "C 11": 240,
    "C 12": 300,
    "C 13": 320,
    "Rush 00–02 & BSQ": 420,
    "Piscine Exams 00–Final": 250,
    "Exam Rank 02": 400,
    "Exam Rank 03": 450,
    "Exam Rank 04": 500,
    "Exam Rank 05": 550,
    "Exam Rank 06": 600,
    "1337 Network & Shell Pool": 180,
}


def calculate_exercise_xp(
    module_code: str = "",
    ex_type: str = "c_program",
    estimated_hours: float = 1.0,
) -> int:
    """Compute deterministic XP value (> 0) for any 1337 / 42 exercise."""
    base = MODULE_BASE_XP.get(module_code, 150)
    type_bonus = {
        "c_function": 0,
        "c_program": 15,
        "c_header": -10,
        "makefile": 30,
        "shell": 10,
        "cpp": 50,
        "python": 10,
    }.get(ex_type, 0)
    hour_bonus = int(round(max(0.5, float(estimated_hours or 1.0)) * 20))
    return max(50, base + type_bonus + hour_bonus)


def compute_42_level(total_xp: int) -> float:
    """Compute 42 / 1337 Intra level from cumulative XP (420 XP = Level 1.00)."""
    if total_xp <= 0:
        return 0.0
    # Smooth sub-linear curve matching Piscine / Common Core progression (0 -> 21)
    lvl = math.pow(total_xp / 420.0, 0.72)
    return round(min(21.0, lvl), 2)


@dataclass
class XPAwardResult:
    subject_id: str
    passed: bool
    grade: int
    configured_xp: int
    awarded_xp: int
    total_xp: int
    level: float
    already_validated: bool
    status_code: str


class XPTracker:
    """Persistent, idempotent XP ledger backed by JSON on disk."""

    def __init__(self, ledger_path: Path) -> None:
        self.ledger_path = Path(ledger_path)

    def _load(self) -> Dict[str, Any]:
        if self.ledger_path.exists():
            try:
                data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data.setdefault("total_xp", 0)
                    data.setdefault("level", 0.0)
                    data.setdefault("validated_exercises", {})
                    data.setdefault("history", [])
                    return data
            except (OSError, json.JSONDecodeError):
                try:
                    shutil.copy2(self.ledger_path, self.ledger_path.with_suffix(".corrupt.bak"))
                except OSError:
                    pass
        return {
            "total_xp": 0,
            "level": 0.0,
            "validated_exercises": {},
            "history": [],
        }

    def _save(self, state: Dict[str, Any]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.ledger_path.with_name(f".{self.ledger_path.name}.{os.getpid()}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(state, indent=2, ensure_ascii=False))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, self.ledger_path)

    def get_state(self) -> Dict[str, Any]:
        return self._load()

    def record_evaluation(
        self,
        subject_id: str,
        *,
        passed: bool,
        grade: int,
        configured_xp: int = 150,
    ) -> XPAwardResult:
        """
        Record an exercise grading outcome with strict idempotency:
        - Failed evaluation (not passed or grade < 100) -> +0 XP ('KO_ZERO_XP')
        - Already validated exercise -> +0 XP ('IDEMPOTENT_ALREADY_VALIDATED')
        - First-time pass (grade >= 100) -> +configured_xp ('FIRST_PASS_XP_AWARDED')
        """
        norm_id = subject_id.strip().strip("/")
        xp_val = max(1, int(configured_xp))
        state = self._load()
        validated = state["validated_exercises"]
        already_done = norm_id in validated

        if not passed or grade < 100:
            awarded = 0
            code = "KO_ZERO_XP"
        elif already_done:
            awarded = 0
            code = "IDEMPOTENT_ALREADY_VALIDATED"
        else:
            awarded = xp_val
            code = "FIRST_PASS_XP_AWARDED"
            validated[norm_id] = {
                "xp": xp_val,
                "first_passed_at": int(time.time()),
                "grade": grade,
            }
            state["total_xp"] = int(state.get("total_xp", 0)) + awarded
            state["level"] = compute_42_level(state["total_xp"])

        state["history"].append(
            {
                "subject_id": norm_id,
                "passed": bool(passed),
                "grade": int(grade),
                "awarded_xp": awarded,
                "total_xp": int(state.get("total_xp", 0)),
                "status_code": code,
                "ts": int(time.time()),
            }
        )
        # Keep history bounded to last 500 entries
        if len(state["history"]) > 500:
            state["history"] = state["history"][-500:]
        self._save(state)

        return XPAwardResult(
            subject_id=norm_id,
            passed=bool(passed),
            grade=int(grade),
            configured_xp=xp_val,
            awarded_xp=awarded,
            total_xp=int(state.get("total_xp", 0)),
            level=float(state.get("level", 0.0)),
            already_validated=already_done,
            status_code=code,
        )


# ---------------------------------------------------------------------------
# Student Profile — persistent cross-session state in ~/.42_student_profile.json
# ---------------------------------------------------------------------------

def _resolve_profile_path(path: Optional[Path] = None) -> Path:
    """Resolve the student profile path dynamically at call time so redirected HOME or FT_STUDENT_PROFILE is honored."""
    if path is not None:
        return Path(path)
    env_override = os.environ.get("FT_STUDENT_PROFILE", "").strip()
    if env_override:
        return Path(env_override)
    return Path.home() / ".42_student_profile.json"


_PROFILE_PATH = Path.home() / ".42_student_profile.json"

# XP thresholds at which each Common Core Rank is unlocked (cumulative)
_RANK_XP_THRESHOLDS: Dict[int, int] = {
    0: 0,
    1: 0,      # Rank 00 & 01 are Piscine — always unlocked
    2: 400,    # Rank 02 exam cleared
    3: 850,    # Rank 03 exam cleared
    4: 1350,   # Rank 04 exam cleared
    5: 1900,   # Rank 05 exam cleared
    6: 2500,   # Rank 06 exam cleared (graduation)
}

# Pool slugs that unlock each rank
_RANK_POOLS: Dict[int, list[str]] = {
    2: ["rank02", "exam_rank_02", "c_piscine_exam_00", "c_piscine_final_exam"],
    3: ["rank03", "exam_rank_03"],
    4: ["rank04", "exam_rank_04"],
    5: ["rank05", "exam_rank_05"],
    6: ["rank06", "exam_rank_06"],
}


@dataclass
class StudentProfile:
    """Persistent student profile stored at ~/.42_student_profile.json."""

    login: str = "student"
    total_xp: int = 0
    level: float = 0.0
    piscine_rank: int = 0       # 0 = Piscine (pre-Common Core)
    common_core_rank: int = 0   # 2..6 once exams are passed
    completed_pools: list[str] = None  # type: ignore[assignment]
    last_updated: int = 0

    def __post_init__(self) -> None:
        if self.completed_pools is None:
            self.completed_pools = []

    @property
    def xp(self) -> int:
        """Alias for total_xp to preserve backward compatibility with callers."""
        return self.total_xp

    # ------------------------------------------------------------------ I/O
    @staticmethod
    def load(path: Optional[Path] = None) -> "StudentProfile":
        """Load profile from disk; create a fresh one if missing/corrupt."""
        resolved = _resolve_profile_path(path)
        if resolved.exists():
            try:
                raw = json.loads(resolved.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return StudentProfile(
                        login=str(raw.get("login", "student")),
                        total_xp=int(raw.get("total_xp", 0)),
                        level=float(raw.get("level", 0.0)),
                        piscine_rank=int(raw.get("piscine_rank", 0)),
                        common_core_rank=int(raw.get("common_core_rank", 0)),
                        completed_pools=list(raw.get("completed_pools", [])),
                        last_updated=int(raw.get("last_updated", 0)),
                    )
            except (OSError, json.JSONDecodeError, ValueError):
                pass
        return StudentProfile()

    def save(self, path: Optional[Path] = None) -> None:
        """Atomically write the profile to disk."""
        resolved = _resolve_profile_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self.last_updated = int(time.time())
        tmp = resolved.with_name(f".{resolved.name}.{os.getpid()}.tmp")
        tmp.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, resolved)

    # ------------------------------------------------------------------ XP
    def award_xp(self, xp: int, pool_slug: str = "") -> None:
        """Add XP and recompute level and rank."""
        self.total_xp = max(0, self.total_xp + xp)
        self.level = compute_42_level(self.total_xp)
        if pool_slug and pool_slug not in self.completed_pools:
            self.completed_pools.append(pool_slug)
        # Recompute common_core_rank
        for rank in range(6, 1, -1):
            if any(p in self.completed_pools for p in _RANK_POOLS.get(rank, [])):
                self.common_core_rank = rank
                break

    # ------------------------------------------------------------------ Display
    def xp_bar(self, width: int = 20) -> str:
        """Return a text XP progress bar for the current level segment."""
        frac = self.level - math.floor(self.level)
        filled = int(frac * width)
        bar = "█" * filled + "░" * (width - filled)
        pct = int(frac * 100)
        rank_label = f"Rank {self.common_core_rank:02d}" if self.common_core_rank >= 2 else "Piscine"
        return (
            f"Level {self.level:05.2f} | {rank_label} | XP: {self.total_xp:,} "
            f"| [{bar}] {pct:3d}%"
        )


def load_student_profile(login: str = "student") -> StudentProfile:
    """Convenience function — loads profile and sets login if not already set."""
    profile = StudentProfile.load()
    if profile.login == "student" and login and login != "student":
        profile.login = login
    return profile
