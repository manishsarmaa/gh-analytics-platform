"""Silver-layer transformations.

`silver.events` is the cleaned, deduplicated, parsed event table built from
bronze. Payload (a raw JSON string in bronze) is mined for the handful of
cross-event-type fields that downstream gold aggregations need; the full
payload is retained for ad-hoc use.

Repo SCD2 + actor dimension + external metadata enrichment are added in Phase 7.
Pure functions only — I/O and MERGE live in the notebook.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

# Bot actors end with "[bot]" (e.g. dependabot[bot]).
_BOT_SUFFIX = r"\[bot\]$"


def to_silver_events(bronze: DataFrame, source: str = "batch") -> DataFrame:
    """Parse + enrich bronze events into the silver.events shape (deduped).

    Args:
        bronze: rows conforming to ``BRONZE_SCHEMA``.
        source: provenance tag (``batch`` or ``stream``) for lineage/union.
    """

    def p(path: str):
        return F.get_json_object(F.col("payload"), path)

    df = bronze.select(
        "event_id",
        "event_type",
        # Most event types carry an `action` (opened/closed/started/...).
        p("$.action").alias("event_action"),
        "actor_id",
        "actor_login",
        F.col("actor_login").rlike(_BOT_SUFFIX).alias("is_bot"),
        "repo_id",
        "repo_name",
        F.split("repo_name", "/").getItem(0).alias("repo_owner"),
        # Common, event-type-specific fields worth promoting out of payload.
        p("$.ref").alias("ref"),
        p("$.ref_type").alias("ref_type"),
        p("$.size").cast("int").alias("push_size"),
        F.coalesce(p("$.number"), p("$.pull_request.number"))
        .cast("int")
        .alias("pr_or_issue_number"),
        p("$.pull_request.merged").cast("boolean").alias("pr_merged"),
        "payload",
        "event_timestamp",
        "event_date",
        F.hour("event_timestamp").alias("event_hour"),
        "ingestion_timestamp",
        "source_file",
    )
    df = (
        df.withColumn("source", F.lit(source))
        .withColumn("silver_processed_at", F.current_timestamp())
        .dropDuplicates(["event_id"])
    )
    return df
