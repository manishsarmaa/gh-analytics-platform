"""Unit tests for bronze transformations (local Spark)."""

from __future__ import annotations

import json

import pytest

from transformations.bronze import BRONZE_SCHEMA, split_valid_quarantine, to_bronze

pytestmark = pytest.mark.spark


def _lines(spark, records: list[dict | str]):
    """Build a single-column `value` DataFrame of raw JSON lines."""
    rows = [(r if isinstance(r, str) else json.dumps(r),) for r in records]
    return spark.createDataFrame(rows, "value string")


def _valid_event(**overrides) -> dict:
    event = {
        "id": "1001",
        "type": "PushEvent",
        "actor": {"id": 42, "login": "octocat"},
        "repo": {"id": 7, "name": "octocat/hello-world"},
        "payload": {"size": 2, "ref": "refs/heads/main"},
        "created_at": "2024-01-15T12:30:00Z",
    }
    event.update(overrides)
    return event


def test_to_bronze_extracts_fields(spark):
    df = to_bronze(
        _lines(spark, [_valid_event()]),
        source_file="f.json.gz",
        ingestion_ts="2024-01-15T13:00:00Z",
    )
    row = df.collect()[0]
    assert row["event_id"] == "1001"
    assert row["event_type"] == "PushEvent"
    assert row["actor_id"] == 42
    assert row["actor_login"] == "octocat"
    assert row["repo_id"] == 7
    assert row["repo_name"] == "octocat/hello-world"
    assert row["source_file"] == "f.json.gz"
    assert str(row["event_date"]) == "2024-01-15"
    assert row["_dq_reason"] is None


def test_payload_preserved_as_json_string(spark):
    df = to_bronze(_lines(spark, [_valid_event()]), "f")
    payload = json.loads(df.collect()[0]["payload"])
    assert payload["ref"] == "refs/heads/main"
    assert payload["size"] == 2


def test_valid_rows_match_bronze_schema(spark):
    valid, _ = split_valid_quarantine(to_bronze(_lines(spark, [_valid_event()]), "f"))
    assert [f.name for f in valid.schema.fields] == [f.name for f in BRONZE_SCHEMA.fields]


@pytest.mark.parametrize(
    "bad, reason",
    [
        (_valid_event(id=None), "missing_event_id"),
        (_valid_event(type=None), "missing_event_type"),
        (_valid_event(repo={"id": None, "name": "x/y"}), "missing_repo_id"),
        (_valid_event(repo={"id": 1, "name": None}), "missing_repo_name"),
        (_valid_event(created_at="not-a-timestamp"), "invalid_event_timestamp"),
    ],
)
def test_invalid_rows_quarantined_with_reason(spark, bad, reason):
    valid, quarantine = split_valid_quarantine(to_bronze(_lines(spark, [bad]), "f"))
    assert valid.count() == 0
    q = quarantine.collect()
    assert len(q) == 1
    assert q[0]["dq_reason"] == reason
    assert q[0]["raw_record"] is not None  # raw kept for replay


def test_mixed_batch_splits_valid_and_bad(spark):
    records = [_valid_event(id="1"), _valid_event(id="2"), _valid_event(id=None)]
    valid, quarantine = split_valid_quarantine(to_bronze(_lines(spark, records), "f"))
    assert valid.count() == 2
    assert quarantine.count() == 1


def test_dedup_by_event_id(spark):
    records = [_valid_event(id="dup"), _valid_event(id="dup"), _valid_event(id="unique")]
    valid, _ = split_valid_quarantine(to_bronze(_lines(spark, records), "f"))
    ids = sorted(r["event_id"] for r in valid.collect())
    assert ids == ["dup", "unique"]
