"""Unit tests for silver transformations (local Spark)."""

from __future__ import annotations

import json

import pytest

from transformations.bronze import split_valid_quarantine, to_bronze
from transformations.silver import to_silver_events

pytestmark = pytest.mark.spark


def _bronze(spark, records: list[dict]):
    rows = [(json.dumps(r),) for r in records]
    raw = spark.createDataFrame(rows, "value string")
    valid, _ = split_valid_quarantine(to_bronze(raw, source_file="f"))
    return valid


def _event(**overrides) -> dict:
    e = {
        "id": "1",
        "type": "PushEvent",
        "actor": {"id": 1, "login": "octocat"},
        "repo": {"id": 9, "name": "octocat/hello-world"},
        "payload": {"size": 3, "ref": "refs/heads/main"},
        "created_at": "2024-01-15T08:30:00Z",
    }
    e.update(overrides)
    return e


def test_silver_promotes_action(spark):
    rec = _event(id="2", type="PullRequestEvent", payload={"action": "opened", "number": 12})
    row = to_silver_events(_bronze(spark, [rec])).collect()[0]
    assert row["event_action"] == "opened"
    assert row["pr_or_issue_number"] == 12


def test_silver_push_size_and_ref(spark):
    row = to_silver_events(_bronze(spark, [_event()])).collect()[0]
    assert row["push_size"] == 3
    assert row["ref"] == "refs/heads/main"
    assert row["event_hour"] == 8


def test_silver_repo_owner_split(spark):
    row = to_silver_events(_bronze(spark, [_event()])).collect()[0]
    assert row["repo_owner"] == "octocat"


@pytest.mark.parametrize(
    "login, expected",
    [("dependabot[bot]", True), ("octocat", False), ("renovate[bot]", True)],
)
def test_silver_bot_detection(spark, login, expected):
    rec = _event(actor={"id": 5, "login": login})
    row = to_silver_events(_bronze(spark, [rec])).collect()[0]
    assert row["is_bot"] is expected


def test_silver_dedup_by_event_id(spark):
    recs = [_event(id="dup"), _event(id="dup"), _event(id="x")]
    out = to_silver_events(_bronze(spark, recs))
    assert out.count() == 2


def test_silver_source_tag(spark):
    row = to_silver_events(_bronze(spark, [_event()]), source="stream").collect()[0]
    assert row["source"] == "stream"
