"""Unit tests for the DQ runner (local Spark)."""

from __future__ import annotations

import pytest

from dq.runner import (
    CRITICAL,
    check_accepted_values,
    check_not_null,
    check_row_count_min,
    check_unique,
    has_critical_failure,
    results_to_rows,
)

pytestmark = pytest.mark.spark


@pytest.fixture
def df(spark):
    return spark.createDataFrame(
        [(1, "a", "PushEvent"), (2, "b", "WatchEvent"), (3, None, "PushEvent")],
        "id long, name string, event_type string",
    )


def test_row_count_min_pass_and_fail(df):
    assert check_row_count_min(df, 3).passed
    assert not check_row_count_min(df, 4).passed


def test_not_null_detects_null(df):
    ok = check_not_null(df, ["id"])
    bad = check_not_null(df, ["name"])
    assert ok.passed
    assert not bad.passed
    assert "name" in bad.observed


def test_unique_detects_duplicates(spark):
    dup = spark.createDataFrame([(1,), (1,), (2,)], "id long")
    assert check_unique(dup, "id").observed == "1 dups"
    assert not check_unique(dup, "id").passed


def test_accepted_values(df):
    ok = check_accepted_values(df, "event_type", ["PushEvent", "WatchEvent"])
    bad = check_accepted_values(df, "event_type", ["PushEvent"])
    assert ok.passed
    assert not bad.passed  # WatchEvent out of set


def test_has_critical_failure(df):
    results = [check_row_count_min(df, 99, severity=CRITICAL)]
    assert has_critical_failure(results)
    assert not has_critical_failure([check_row_count_min(df, 1)])


def test_results_to_rows_adds_context(df):
    rows = results_to_rows([check_row_count_min(df, 1)], layer="bronze", table="t", run_id="r1")
    assert rows[0]["layer"] == "bronze"
    assert rows[0]["run_id"] == "r1"
    assert rows[0]["passed"] is True
    assert rows[0]["check_type"] == "row_count"
