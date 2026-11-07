"""Authoritative Exam Catalog, Ordering, Prerequisite Graph & Timing Policy Validator.

Provides a single source of truth for:
- Exam pool schema validation (unique IDs, level ordering, positive point totals, unit-bearing durations).
- Prerequisite cycle detection (DFS 3-color graph check).
- Deterministic ordering: pool_group ('piscine' -> 'cursus') -> rank_order -> pool name -> level index.
- Slug alias resolution preserving established official 42 / 1337 mappings.
- Timing policy loading and duration validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml


BASE_DIR = Path(__file__).resolve().parent.parent
POOLS_DIR = BASE_DIR / "pools" / "exams"
SLUGS_FILE = BASE_DIR / "pools" / "official_42_slugs.yml"
TIMING_POLICY_FILE = BASE_DIR / "pools" / "timing_policy.yml"
SUBJECTS_EXAMS_DIR = BASE_DIR / "subjects" / "exams"
SUBJECTS_PISCINE_DIR = BASE_DIR / "subjects" / "piscine"

POOL_GROUP_ORDER = {
    "piscine": 0,
    "cursus": 1,
}


class CatalogValidationError(ValueError):
    """Raised when an exam pool or catalog violates schema, duration, or graph invariants."""


@dataclass(frozen=True)
class LevelSpec:
    level: int
    points: int
    candidates: tuple[str, ...]


@dataclass(frozen=True)
class ExamPoolSpec:
    name: str
    display_name: str
    pool_group: str
    rank_order: int
    duration_seconds: int
    prerequisites: tuple[str, ...]
    levels: tuple[LevelSpec, ...]
    source_path: Path = field(default=Path())


def load_timing_policy(policy_path: Path | None = None) -> dict[str, Any]:
    path = policy_path or TIMING_POLICY_FILE
    if not path.is_file():
        return {
            "exam_durations": {
                "standard_exam_seconds": 14400,
                "final_exam_seconds": 28800,
                "min_allowed_seconds": 1,
                "max_allowed_seconds": 86400,
            },
            "cooldown_policy": {
                "step_seconds": 30,
                "reset_on_level_pass": True,
            },
            "sandbox_timeouts": {
                "per_test_seconds": 2.0,
                "socket_test_seconds": 5.0,
                "build_and_norm_seconds": 10.0,
            },
        }
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CatalogValidationError(f"Malformed timing policy in {path}")
    return data


def validate_duration_seconds(duration: Any, context: str = "exam") -> int:
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        raise CatalogValidationError(f"Invalid non-numeric duration for {context}: {duration!r}")
    if int(duration) != duration:
        raise CatalogValidationError(f"Duration must be an integer number of seconds for {context}: {duration!r}")
    val = int(duration)
    if val <= 0:
        raise CatalogValidationError(f"Duration must be > 0 seconds for {context} (got {val})")
    policy = load_timing_policy().get("exam_durations", {})
    max_sec = int(policy.get("max_allowed_seconds", 86400))
    if val > max_sec:
        raise CatalogValidationError(f"Duration {val}s exceeds max_allowed_seconds ({max_sec}s) for {context}")
    return val


def validate_pool_dict(
    data: dict[str, Any],
    *,
    source_path: Path | None = None,
    known_exercise_slugs: set[str] | None = None,
) -> ExamPoolSpec:
    ctx = str(source_path or data.get("name", "<unknown_pool>"))
    if not isinstance(data, dict):
        raise CatalogValidationError(f"Pool definition in {ctx} must be a YAML mapping")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise CatalogValidationError(f"Pool in {ctx} is missing a non-empty string 'name'")

    display_name = str(data.get("display_name") or name)
    pool_group = str(data.get("pool_group") or ("piscine" if "piscine" in name or "1337" in name or "day09" in name else "cursus"))
    if pool_group not in POOL_GROUP_ORDER:
        raise CatalogValidationError(f"Pool '{name}' has invalid pool_group '{pool_group}'")

    rank_order_raw = data.get("rank_order", 999)
    if isinstance(rank_order_raw, bool) or not isinstance(rank_order_raw, int):
        raise CatalogValidationError(f"Pool '{name}' has invalid rank_order {rank_order_raw!r}")

    if "duration_seconds" not in data:
        raise CatalogValidationError(f"Pool '{name}' is missing explicit unit-bearing 'duration_seconds'")
    duration_seconds = validate_duration_seconds(data["duration_seconds"], context=f"pool '{name}'")

    prereqs_raw = data.get("prerequisites", [])
    if not isinstance(prereqs_raw, list) or not all(isinstance(p, str) and p.strip() for p in prereqs_raw):
        raise CatalogValidationError(f"Pool '{name}' prerequisites must be a list of pool IDs")

    levels_raw = data.get("levels")
    if not isinstance(levels_raw, list) or not levels_raw:
        raise CatalogValidationError(f"Pool '{name}' must define a non-empty 'levels' list")

    levels: list[LevelSpec] = []
    seen_level_indices: set[int] = set()
    for idx, lvl in enumerate(levels_raw):
        if not isinstance(lvl, dict):
            raise CatalogValidationError(f"Pool '{name}' level #{idx} must be a mapping")
        lvl_num = lvl.get("level")
        if isinstance(lvl_num, bool) or not isinstance(lvl_num, int) or lvl_num < 0:
            raise CatalogValidationError(f"Pool '{name}' has invalid level number {lvl_num!r}")
        if lvl_num in seen_level_indices:
            raise CatalogValidationError(f"Pool '{name}' has duplicate level index {lvl_num}")
        if lvl_num != idx:
            raise CatalogValidationError(
                f"Pool '{name}' levels must be contiguous and ordered 0..N-1 (expected {idx}, got {lvl_num})"
            )
        seen_level_indices.add(lvl_num)

        pts = lvl.get("points", 0)
        if isinstance(pts, bool) or not isinstance(pts, int) or pts <= 0:
            raise CatalogValidationError(f"Pool '{name}' level {lvl_num} must have positive integer points")

        cands = lvl.get("candidates")
        if not isinstance(cands, list) or not cands:
            raise CatalogValidationError(f"Pool '{name}' level {lvl_num} must have a non-empty candidates list")

        clean_cands: list[str] = []
        seen_cands: set[str] = set()
        for c in cands:
            if not isinstance(c, str) or not c.strip():
                raise CatalogValidationError(f"Pool '{name}' level {lvl_num} contains an empty candidate slug")
            if c in seen_cands:
                raise CatalogValidationError(f"Pool '{name}' level {lvl_num} contains duplicate candidate '{c}'")
            if known_exercise_slugs is not None and c not in known_exercise_slugs:
                raise CatalogValidationError(
                    f"Pool '{name}' level {lvl_num} references non-existent exercise '{c}'"
                )
            seen_cands.add(c)
            clean_cands.append(c)

        levels.append(LevelSpec(level=lvl_num, points=pts, candidates=tuple(clean_cands)))

    return ExamPoolSpec(
        name=name,
        display_name=display_name,
        pool_group=pool_group,
        rank_order=rank_order_raw,
        duration_seconds=duration_seconds,
        prerequisites=tuple(prereqs_raw),
        levels=tuple(levels),
        source_path=source_path or Path(),
    )


def validate_prerequisite_graph(pools: dict[str, ExamPoolSpec]) -> None:
    """Validate that all prerequisite references exist and the graph is a DAG (no cycles)."""
    for name, spec in pools.items():
        for prereq in spec.prerequisites:
            if prereq not in pools:
                raise CatalogValidationError(
                    f"Pool '{name}' declares unknown prerequisite pool '{prereq}'"
                )

    # 0 = unvisited, 1 = visiting (on current recursion stack), 2 = visited
    state: dict[str, int] = {name: 0 for name in pools}
    path_stack: list[str] = []

    def dfs(node: str) -> None:
        state[node] = 1
        path_stack.append(node)
        for prereq in pools[node].prerequisites:
            if state[prereq] == 1:
                cycle_start = path_stack.index(prereq)
                cycle_str = " -> ".join(path_stack[cycle_start:] + [prereq])
                raise CatalogValidationError(f"Prerequisite cycle detected: {cycle_str}")
            if state[prereq] == 0:
                dfs(prereq)
        path_stack.pop()
        state[node] = 2

    for name in sorted(pools):
        if state[name] == 0:
            dfs(name)


def load_authoritative_catalog(
    pools_dir: Path | None = None,
    subjects_exams_dir: Path | None = None,
) -> list[ExamPoolSpec]:
    """Load, validate, and deterministically order all exam pools (`pool_group` -> `rank_order` -> `name`)."""
    p_dir = pools_dir or POOLS_DIR
    s_dir = subjects_exams_dir or SUBJECTS_EXAMS_DIR

    known_slugs: set[str] | None = None
    if s_dir.is_dir():
        known_slugs = {
            d.name for d in s_dir.iterdir() if d.is_dir() and (d / "meta.yml").is_file()
        }

    pools_by_id: dict[str, ExamPoolSpec] = {}
    for yml_path in sorted(p_dir.glob("*.yml")):
        raw = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
        spec = validate_pool_dict(raw, source_path=yml_path, known_exercise_slugs=known_slugs)
        if spec.name in pools_by_id:
            raise CatalogValidationError(
                f"Duplicate pool ID '{spec.name}' in {yml_path} and {pools_by_id[spec.name].source_path}"
            )
        if yml_path.stem != spec.name:
            raise CatalogValidationError(
                f"Pool filename '{yml_path.name}' does not match internal pool name '{spec.name}'"
            )
        pools_by_id[spec.name] = spec

    validate_prerequisite_graph(pools_by_id)

    ordered = sorted(
        pools_by_id.values(),
        key=lambda s: (POOL_GROUP_ORDER.get(s.pool_group, 99), s.rank_order, s.name),
    )
    return ordered
