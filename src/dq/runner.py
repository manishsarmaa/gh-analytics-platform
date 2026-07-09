"""Lightweight data-quality checks.

Custom, unit-testable checks that every layer notebook can run and log to
``ops.dq_results``. A *critical* failure should fail the pipeline (so ADF
alerts); a *warning* is recorded but non-blocking.

Great Expectations suites are layered on top of this in Phase 9 — the result
shape (``CheckResult``) stays the API so the sink table is unchanged.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

CRITICAL = "critical"
WARNING = "warning"


@dataclass(frozen=True)
class CheckResult:
    check_name: str
    check_type: str
    severity: str
    passed: bool
    observed: str
    expected: str
    details: str = ""


def check_row_count_min(df: DataFrame, minimum: int, severity: str = CRITICAL) -> CheckResult:
    n = df.count()
    return CheckResult(
        "row_count_min",
        "row_count",
        severity,
        n >= minimum,
        observed=str(n),
        expected=f">={minimum}",
    )


def check_not_null(df: DataFrame, columns: list[str], severity: str = CRITICAL) -> CheckResult:
    counts = (
        df.agg(*[F.sum(F.col(c).isNull().cast("long")).alias(c) for c in columns])
        .collect()[0]
        .asDict()
    )
    failing = {c: int(v) for c, v in counts.items() if v}
    return CheckResult(
        "not_null:" + ",".join(columns),
        "not_null",
        severity,
        passed=len(failing) == 0,
        observed=str(failing or "no nulls"),
        expected="0 nulls",
    )


def check_unique(df: DataFrame, key: str, severity: str = CRITICAL) -> CheckResult:
    total = df.count()
    distinct = df.select(key).distinct().count()
    dups = total - distinct
    return CheckResult(
        f"unique:{key}",
        "unique",
        severity,
        passed=dups == 0,
        observed=f"{dups} dups",
        expected="0 dups",
    )


def check_accepted_values(
    df: DataFrame, column: str, allowed: Iterable[str], severity: str = WARNING
) -> CheckResult:
    bad = df.filter(F.col(column).isNotNull() & ~F.col(column).isin(list(allowed))).count()
    return CheckResult(
        f"accepted_values:{column}",
        "accepted_values",
        severity,
        passed=bad == 0,
        observed=f"{bad} out-of-set",
        expected="all in set",
    )


def has_critical_failure(results: Iterable[CheckResult]) -> bool:
    """True if any critical check failed — the notebook raises on this."""
    return any((not r.passed) and r.severity == CRITICAL for r in results)


def results_to_rows(results: Iterable[CheckResult], **context) -> list[dict]:
    """Flatten results + run context into dict rows for the dq_results table."""
    return [
        {
            "check_name": r.check_name,
            "check_type": r.check_type,
            "severity": r.severity,
            "passed": r.passed,
            "observed": r.observed,
            "expected": r.expected,
            "details": r.details,
            **context,
        }
        for r in results
    ]
