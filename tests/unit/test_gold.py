"""Unit tests for gold aggregations (local Spark)."""

from __future__ import annotations

import json

import pytest

from transformations.bronze import split_valid_quarantine, to_bronze
from transformations.gold import (
    contributor_activity_daily,
    event_type_summary_hourly,
    hot_repos_hourly,
)
from transformations.silver import to_silver_events

pytestmark = pytest.mark.spark


def _silver(spark, records: list[dict]):
    rows = [(json.dumps(r),) for r in records]
    valid, _ = split_valid_quarantine(to_bronze(spark.createDataFrame(rows, "value string"), "f"))
    return to_silver_events(valid)


def _event(eid, etype, login="octocat", repo="octocat/hello-world", repo_id=9, action=None, hour=8):
    payload = {"size": 1}
    if action:
        payload["action"] = action
    return {
        "id": eid,
        "type": etype,
        "actor": {"id": abs(hash(login)) % 1000, "login": login},
        "repo": {"id": repo_id, "name": repo},
        "payload": payload,
        "created_at": f"2024-01-15T{hour:02d}:30:00Z",
    }


def test_event_type_summary(spark):
    recs = [
        _event("1", "PushEvent"),
        _event("2", "PushEvent"),
        _event("3", "WatchEvent"),
    ]
    out = {r["event_type"]: r for r in event_type_summary_hourly(_silver(spark, recs)).collect()}
    assert out["PushEvent"]["event_count"] == 2
    assert out["WatchEvent"]["event_count"] == 1
    assert out["PushEvent"]["event_hour"] == 8


def test_hot_repos_counts_by_type(spark):
    recs = [
        _event("1", "WatchEvent"),
        _event("2", "WatchEvent"),
        _event("3", "ForkEvent"),
        _event("4", "PushEvent"),
    ]
    row = hot_repos_hourly(_silver(spark, recs)).collect()[0]
    assert row["repo_name"] == "octocat/hello-world"
    assert row["stars"] == 2
    assert row["forks"] == 1
    assert row["pushes"] == 1
    assert row["event_count"] == 4


def test_hot_repos_unique_actors(spark):
    recs = [
        _event("1", "PushEvent", login="alice"),
        _event("2", "PushEvent", login="bob"),
        _event("3", "PushEvent", login="alice"),
    ]
    row = hot_repos_hourly(_silver(spark, recs)).collect()[0]
    assert row["unique_actors"] == 2


def test_contributor_activity(spark):
    recs = [
        _event("1", "PushEvent", login="alice"),
        _event("2", "PullRequestEvent", login="alice", action="opened"),
        _event("3", "IssuesEvent", login="alice", action="closed"),
    ]
    row = contributor_activity_daily(_silver(spark, recs)).collect()[0]
    assert row["actor_login"] == "alice"
    assert row["total_events"] == 3
    assert row["push_events"] == 1
    assert row["prs_opened"] == 1
    assert row["issue_events"] == 1
    assert row["issues_opened"] == 0  # the issue was 'closed', not 'opened'


def test_contributor_repos_touched(spark):
    recs = [
        _event("1", "PushEvent", login="alice", repo="a/one", repo_id=1),
        _event("2", "PushEvent", login="alice", repo="a/two", repo_id=2),
    ]
    row = contributor_activity_daily(_silver(spark, recs)).collect()[0]
    assert row["repos_touched"] == 2
