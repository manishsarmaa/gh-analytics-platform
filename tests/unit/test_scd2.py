"""Unit tests for SCD Type 2 upsert (local Spark)."""

from __future__ import annotations

import pytest

from transformations.scd2 import scd2_upsert

pytestmark = pytest.mark.spark

TRACKED = ["repo_name", "language", "stars"]
T1 = "2024-01-15T00:00:00Z"
T2 = "2024-01-16T00:00:00Z"


def _snap(spark, rows):
    return spark.createDataFrame(rows, "repo_id long, repo_name string, language string, stars int")


def test_initial_load_all_current(spark):
    inc = _snap(spark, [(1, "a/one", "Python", 10), (2, "b/two", "Go", 5)])
    out = scd2_upsert(None, inc, "repo_id", TRACKED, T1)
    assert out.count() == 2
    assert out.filter("is_current").count() == 2
    assert out.filter("valid_to is null").count() == 2


def test_unchanged_snapshot_no_new_versions(spark):
    inc = _snap(spark, [(1, "a/one", "Python", 10)])
    v1 = scd2_upsert(None, inc, "repo_id", TRACKED, T1)
    v2 = scd2_upsert(v1, inc, "repo_id", TRACKED, T2)
    assert v2.count() == 1  # no change → still one row
    assert v2.filter("is_current").count() == 1


def test_changed_attribute_creates_new_version(spark):
    v1 = scd2_upsert(None, _snap(spark, [(1, "a/one", "Python", 10)]), "repo_id", TRACKED, T1)
    # stars changed 10 -> 20
    v2 = scd2_upsert(v1, _snap(spark, [(1, "a/one", "Python", 20)]), "repo_id", TRACKED, T2)
    rows = {(_r["is_current"], _r["stars"]): _r for _r in v2.collect()}
    assert v2.count() == 2
    assert v2.filter("is_current").count() == 1
    # the current row has the new value; the closed row has the old value + valid_to set
    current = v2.filter("is_current").collect()[0]
    closed = v2.filter("not is_current").collect()[0]
    assert current["stars"] == 20 and current["valid_to"] is None
    assert closed["stars"] == 10 and closed["valid_to"] is not None


def test_new_repo_added_over_time(spark):
    v1 = scd2_upsert(None, _snap(spark, [(1, "a/one", "Python", 10)]), "repo_id", TRACKED, T1)
    v2 = scd2_upsert(v1, _snap(spark, [(2, "b/two", "Rust", 3)]), "repo_id", TRACKED, T2)
    # repo 1 not in snapshot → stays current; repo 2 added
    assert v2.filter("is_current").count() == 2
    assert {r["repo_id"] for r in v2.filter("is_current").collect()} == {1, 2}


def test_absent_repo_not_expired(spark):
    v1 = scd2_upsert(
        None,
        _snap(spark, [(1, "a/one", "Python", 10), (2, "b/two", "Go", 5)]),
        "repo_id",
        TRACKED,
        T1,
    )
    # snapshot only has repo 1 changed; repo 2 absent must remain current
    v2 = scd2_upsert(v1, _snap(spark, [(1, "a/one", "Python", 99)]), "repo_id", TRACKED, T2)
    repo2 = v2.filter("repo_id = 2").collect()
    assert len(repo2) == 1 and repo2[0]["is_current"] is True
