"""Bronze-layer transformations for GH Archive events.

Pure PySpark functions (no I/O) so they can be unit-tested on a local Spark.
The notebook (``src/notebooks/bronze_ingestion.py``) handles read/MERGE/write.

Design choices:
- Read raw events as **text** (one JSON object per line) and extract fields with
  ``get_json_object``. This keeps ``payload`` as a raw JSON string (its shape
  varies by event type) and avoids expensive, drift-prone schema inference —
  bronze schema is therefore *stable and enforced by construction*.
- Rows missing any required field are not dropped: they are tagged with a
  ``_dq_reason`` and routed to the quarantine (dead-letter) path.
"""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql import types as T

# Enforced bronze schema (documentation + MERGE target contract).
BRONZE_SCHEMA = T.StructType(
    [
        T.StructField("event_id", T.StringType(), False),
        T.StructField("event_type", T.StringType(), False),
        T.StructField("actor_id", T.LongType(), True),
        T.StructField("actor_login", T.StringType(), True),
        T.StructField("repo_id", T.LongType(), False),
        T.StructField("repo_name", T.StringType(), False),
        T.StructField("payload", T.StringType(), True),
        T.StructField("event_timestamp", T.TimestampType(), False),
        T.StructField("event_date", T.DateType(), True),
        T.StructField("ingestion_timestamp", T.TimestampType(), True),
        T.StructField("source_file", T.StringType(), True),
    ]
)

# Required (not-null) fields; a null in any of these quarantines the row.
_REQUIRED = ["event_id", "event_type", "repo_id", "repo_name", "event_timestamp"]


def _dq_reason_col():
    """First failing required-field check, else null (= valid row)."""
    reason = F.lit(None).cast("string")
    # Build the chain in reverse so the first listed field wins.
    for field in reversed(_REQUIRED):
        label = "invalid_event_timestamp" if field == "event_timestamp" else f"missing_{field}"
        reason = F.when(F.col(field).isNull(), F.lit(label)).otherwise(reason)
    return reason


def to_bronze(
    raw_lines: DataFrame,
    source_file: str,
    ingestion_ts: str | None = None,
) -> DataFrame:
    """Map raw GH Archive JSON lines to the bronze schema (+ ``_dq_reason``, ``_raw``).

    Args:
        raw_lines: DataFrame with a single string column ``value`` (one JSON
            event per row), e.g. from ``spark.read.text(landing_path)``.
        source_file: lineage tag stored on every row.
        ingestion_ts: optional fixed timestamp (ISO string) for deterministic
            tests; defaults to ``current_timestamp()``.
    """

    def g(path: str):
        return F.get_json_object(F.col("value"), path)

    ingest = F.lit(ingestion_ts).cast("timestamp") if ingestion_ts else F.current_timestamp()

    df = raw_lines.select(
        F.col("value").alias("_raw"),
        g("$.id").alias("event_id"),
        g("$.type").alias("event_type"),
        g("$.actor.id").cast("long").alias("actor_id"),
        g("$.actor.login").alias("actor_login"),
        g("$.repo.id").cast("long").alias("repo_id"),
        g("$.repo.name").alias("repo_name"),
        g("$.payload").alias("payload"),
        F.to_timestamp(g("$.created_at")).alias("event_timestamp"),
        F.lit(source_file).alias("source_file"),
    )
    df = (
        df.withColumn("event_date", F.to_date("event_timestamp"))
        .withColumn("ingestion_timestamp", ingest)
        .withColumn("_dq_reason", _dq_reason_col())
    )
    return df


def split_valid_quarantine(df: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Split ``to_bronze`` output into (valid bronze rows, quarantine rows).

    Valid rows conform to ``BRONZE_SCHEMA`` (helper columns dropped, deduped by
    ``event_id``). Quarantine rows keep the raw record + failure reason.
    """
    valid = (
        df.filter(F.col("_dq_reason").isNull())
        .select([f.name for f in BRONZE_SCHEMA.fields])
        .dropDuplicates(["event_id"])
    )
    quarantine = df.filter(F.col("_dq_reason").isNotNull()).select(
        F.col("event_id"),
        F.col("source_file"),
        F.col("ingestion_timestamp"),
        F.col("_dq_reason").alias("dq_reason"),
        F.col("_raw").alias("raw_record"),
    )
    return valid, quarantine
