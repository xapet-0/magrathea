"""
deepthought.test_telemetry
Backend Reporting Data Contract for Magrathea's Internal Test Engineering System (Section 12).
Strictly distinguishes metric provenance states:
- "MEASURED"    : Derived from actual current execution artifacts (.gcda/.gcno/JSON reports)
- "CONFIGURED"  : Static build/compiler configuration setting
- "ESTIMATED"   : Reserved (never used for test/coverage/mutation outcomes)
- "UNAVAILABLE" : Underlying tool or artifact corrupted / missing dependency
- "NOT_RUN"     : Target has not been executed yet (value is None, NEVER converted to 0)

Also detects stale artifacts (`is_stale = True` when any production or unit-test C source
has `st_mtime` newer than the artifact timestamp) so old results are never presented as current.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


PRODUCTION_C_FILES = [
    "trusted_harness/dt_arena.c",
    "trusted_harness/dt_arena.h",
    "third_party/tsoding_arena/arena.h",
    "deepthought/sandbox_harness.c",
    "trusted_harness/dt_sandbox_harness.h",
    "trusted_harness/dt_diagnostics.c",
    "trusted_harness/dt_diagnostics.h",
    "trusted_harness/dt_compiler_guard.c",
    "trusted_harness/dt_compiler_guard.h",
    "trusted_harness/dt_harness_util.c",
    "trusted_harness/dt_harness_util.h",
]

UNIT_TEST_C_FILES = [
    "tests/unit/arena/test_arena_criterion.c",
    "tests/unit/memory/test_memory_harness_criterion.c",
    "tests/unit/diagnostics/test_diagnostics_criterion.c",
    "tests/unit/compiler/test_compiler_guard_criterion.c",
    "tests/unit/harness/test_harness_util_criterion.c",
]


def compute_source_revision(kit_root: Path) -> tuple[str, float]:
    """Compute a deterministic SHA-256 digest and max mtime across all tracked C production and test files."""
    h = hashlib.sha256()
    max_mtime = 0.0
    for rel in sorted(PRODUCTION_C_FILES + UNIT_TEST_C_FILES):
        p = kit_root / rel
        if p.is_file():
            st = p.stat()
            if st.st_mtime > max_mtime:
                max_mtime = st.st_mtime
            h.update(rel.encode("utf-8") + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()[:16], max_mtime


def _metric_envelope(
    origin: str,
    value: Any,
    *,
    artifact_path: str | None = None,
    timestamp_iso: str | None = None,
    stale: bool = False,
) -> dict[str, Any]:
    return {
        "origin": origin,  # MEASURED | CONFIGURED | ESTIMATED | UNAVAILABLE | NOT_RUN
        "value": value,
        "artifact": artifact_path,
        "timestamp": timestamp_iso,
        "stale": stale,
    }


def collect_internal_test_telemetry(kit_root: Path) -> dict[str, Any]:
    """Read live backend test, coverage, and mutation artifacts without fabricating or zero-filling missing data."""
    rev_hash, latest_src_mtime = compute_source_revision(kit_root)

    unit_bin = kit_root / "build/tests/unit_tests"
    unit_json = kit_root / "reports/criterion_unit_results.json"
    cov_json = kit_root / "reports/coverage_summary.json"
    mut_json = kit_root / "reports/mutation_summary.json"

    # 1. Build status
    if unit_bin.is_file():
        bin_st = unit_bin.stat()
        bin_stale = bin_st.st_mtime < latest_src_mtime
        bin_ts = dt.datetime.fromtimestamp(bin_st.st_mtime, tz=dt.timezone.utc).isoformat()
        build_metric = _metric_envelope(
            "MEASURED",
            {"built": True, "size_bytes": bin_st.st_size, "executable": "build/tests/unit_tests"},
            artifact_path="build/tests/unit_tests",
            timestamp_iso=bin_ts,
            stale=bin_stale,
        )
    else:
        build_metric = _metric_envelope("NOT_RUN", None, artifact_path="build/tests/unit_tests")

    # 2. Criterion unit test execution
    test_run_id = None
    if unit_json.is_file():
        try:
            ust = unit_json.stat()
            u_stale = ust.st_mtime < latest_src_mtime
            u_ts = dt.datetime.fromtimestamp(ust.st_mtime, tz=dt.timezone.utc).isoformat()
            udata = json.loads(unit_json.read_text(encoding="utf-8"))
            test_run_id = f"cr-{rev_hash}-{int(ust.st_mtime)}"
            unit_metric = _metric_envelope(
                "MEASURED",
                {
                    "total_tests": udata.get("total_tests"),
                    "passed": udata.get("passed"),
                    "failed": udata.get("failed"),
                    "errored": udata.get("errored"),
                    "skipped": udata.get("skipped"),
                    "duration_ms": udata.get("duration_ms"),
                    "all_passed": (
                        udata.get("total_tests", 0) > 0
                        and udata.get("failed", 0) == 0
                        and udata.get("errored", 0) == 0
                    ),
                },
                artifact_path="reports/criterion_unit_results.json",
                timestamp_iso=u_ts,
                stale=u_stale,
            )
        except Exception as exc:
            unit_metric = _metric_envelope(
                "UNAVAILABLE",
                {"error": str(exc)},
                artifact_path="reports/criterion_unit_results.json",
            )
    else:
        unit_metric = _metric_envelope("NOT_RUN", None, artifact_path="reports/criterion_unit_results.json")

    # 3. Line & Branch Coverage
    if cov_json.is_file():
        try:
            cst = cov_json.stat()
            c_stale = cst.st_mtime < latest_src_mtime
            c_ts = dt.datetime.fromtimestamp(cst.st_mtime, tz=dt.timezone.utc).isoformat()
            cdata = json.loads(cov_json.read_text(encoding="utf-8"))
            line_cov_metric = _metric_envelope(
                "MEASURED",
                {
                    "lines_covered": cdata.get("line_covered"),
                    "lines_total": cdata.get("line_total"),
                    "line_percent": cdata.get("line_percent"),
                    "gcno_count": cdata.get("gcno_count"),
                    "gcda_count": cdata.get("gcda_count"),
                },
                artifact_path="reports/coverage_summary.json",
                timestamp_iso=c_ts,
                stale=c_stale,
            )
            branch_cov_metric = _metric_envelope(
                "MEASURED",
                {
                    "branches_covered": cdata.get("branch_covered"),
                    "branches_executed": cdata.get("branch_executed"),
                    "branches_total": cdata.get("branch_total"),
                    "branch_percent": cdata.get("branch_percent"),
                },
                artifact_path="reports/coverage_summary.json",
                timestamp_iso=c_ts,
                stale=c_stale,
            )
        except Exception as exc:
            line_cov_metric = _metric_envelope("UNAVAILABLE", {"error": str(exc)}, artifact_path="reports/coverage_summary.json")
            branch_cov_metric = _metric_envelope("UNAVAILABLE", {"error": str(exc)}, artifact_path="reports/coverage_summary.json")
    else:
        line_cov_metric = _metric_envelope("NOT_RUN", None, artifact_path="reports/coverage_summary.json")
        branch_cov_metric = _metric_envelope("NOT_RUN", None, artifact_path="reports/coverage_summary.json")

    # 4. Mutation campaign
    mutation_campaign_id = None
    if mut_json.is_file():
        try:
            mst = mut_json.stat()
            m_stale = mst.st_mtime < latest_src_mtime
            m_ts = dt.datetime.fromtimestamp(mst.st_mtime, tz=dt.timezone.utc).isoformat()
            mdata = json.loads(mut_json.read_text(encoding="utf-8"))
            mutation_campaign_id = mdata.get("campaign_id")
            mutation_metric = _metric_envelope(
                "MEASURED",
                {
                    "total_mutants": mdata.get("total_mutants"),
                    "valid_non_equivalent": mdata.get("valid_non_equivalent_mutants"),
                    "killed_by_assertion": mdata.get("killed_by_assertion"),
                    "killed_by_sanitizer": mdata.get("killed_by_sanitizer"),
                    "killed_by_build_failure": mdata.get("killed_by_build_failure"),
                    "survived_non_equivalent": mdata.get("survived_non_equivalent"),
                    "equivalent_mutants": mdata.get("equivalent_mutants"),
                    "mutation_score_percent": mdata.get("mutation_score_percent"),
                },
                artifact_path="reports/mutation_summary.json",
                timestamp_iso=m_ts,
                stale=m_stale,
            )
        except Exception as exc:
            mutation_metric = _metric_envelope("UNAVAILABLE", {"error": str(exc)}, artifact_path="reports/mutation_summary.json")
    else:
        mutation_metric = _metric_envelope("NOT_RUN", None, artifact_path="reports/mutation_summary.json")

    return {
        "schema_version": "1.0",
        "domain": "MAGRATHEA_INTERNAL_UNIT_TESTING",
        "note": "Internal C/C++ platform unit test telemetry; strictly distinct from student exercise grading.",
        "test_run_id": test_run_id,
        "source_revision": rev_hash,
        "test_target": "tests_run (build/tests/unit_tests)",
        "build_configuration": _metric_envelope(
            "CONFIGURED",
            {
                "compiler": "gcc (Debian 12.2.0-14+deb12u1) 12.2.0",
                "cflags": "-Wall -Wextra -Werror -std=c11 -g -O1 --coverage -DDT_COVERAGE_INSTRUMENTED",
            },
        ),
        "tool_versions": _metric_envelope(
            "CONFIGURED",
            {
                "gcc": "12.2.0",
                "gcov": "12.2.0",
                "gcovr": "6.0-magrathea-bridge (backed by GNU gcov 12.2.0)",
                "criterion": "2.4.2-magrathea-compat (offline-vendored C11 library)",
                "gnu_make": "4.3",
                "python": "3.11.2",
            },
        ),
        "mutation_campaign_id": mutation_campaign_id,
        "metrics": {
            "build_status": build_metric,
            "unit_tests": unit_metric,
            "line_coverage": line_cov_metric,
            "branch_coverage": branch_cov_metric,
            "mutation_testing": mutation_metric,
        },
    }


def run_internal_unit_test_pipeline(kit_root: Path) -> tuple[bool, str, dict[str, Any]]:
    """Invoke `make tests_coverage` in the backend and return (ok, raw_output, updated_telemetry)."""
    proc = subprocess.run(
        ["make", "tests_coverage"],
        cwd=str(kit_root),
        capture_output=True,
        text=True,
        errors="replace",
    )
    combined_out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    telemetry = collect_internal_test_telemetry(kit_root)
    return (proc.returncode == 0), combined_out.strip(), telemetry
