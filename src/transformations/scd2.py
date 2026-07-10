"""SCD Type 2 upsert for dimension tables (e.g. silver.repos_scd2).

Full-recompute approach: given the current dimension and a fresh snapshot,
return the new full dimension state. Pure and unit-testable; the notebook just
overwrites the table with the result. Suitable for modest dimensions (repos).

SCD2 columns: valid_from, valid_to (null = open), is_current, record_hash.
"""

from __future__ import annotations

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

SCD2_COLS = ["record_hash", "valid_from", "valid_to", "is_current"]


def add_record_hash(df: DataFrame, cols: list[str], out: str = "record_hash") -> DataFrame:
    """Deterministic SHA-256 over the tracked columns (null-safe)."""
    parts = [F.coalesce(F.col(c).cast("string"), F.lit("∅")) for c in cols]
    return df.withColumn(out, F.sha2(F.concat_ws("||", *parts), 256))


def _ts(effective_ts) -> Column:
    return (
        F.to_timestamp(F.lit(effective_ts))
        if isinstance(effective_ts, str)
        else F.lit(effective_ts)
    )


def scd2_upsert(
    current: DataFrame | None,
    incoming: DataFrame,
    key: str,
    tracked_cols: list[str],
    effective_ts,
) -> DataFrame:
    """Return the new full SCD2 state.

    - new key                → open row (is_current, valid_to null)
    - existing key, changed  → old row closed (valid_to=ts), new open row added
    - existing key, same     → unchanged
    - key absent from snapshot → left as-is (not expired)
    """
    ts = _ts(effective_ts)
    inc = (
        add_record_hash(incoming, tracked_cols)
        .withColumn("valid_from", ts)
        .withColumn("valid_to", F.lit(None).cast("timestamp"))
        .withColumn("is_current", F.lit(True))
    )

    if current is None:
        return inc

    cur_open = current.filter(F.col("is_current"))
    cur_history = current.filter(~F.col("is_current"))

    # Mark incoming rows as new/changed vs the open version.
    open_hash = cur_open.select(F.col(key).alias("_k"), F.col("record_hash").alias("_ch"))
    marked = inc.join(open_hash, inc[key] == F.col("_k"), "left")
    changed_new = marked.filter(F.col("_ch").isNull() | (F.col("_ch") != inc["record_hash"])).drop(
        "_k", "_ch"
    )

    changed_keys = changed_new.select(key).distinct()

    # Open rows whose key changed → close them.
    expired = (
        cur_open.join(
            changed_keys.withColumnRenamed(key, "_ck"), cur_open[key] == F.col("_ck"), "inner"
        )
        .drop("_ck")
        .withColumn("valid_to", ts)
        .withColumn("is_current", F.lit(False))
    )

    # Open rows that did not change → keep open.
    unchanged = cur_open.join(
        changed_keys.withColumnRenamed(key, "_uk"), cur_open[key] == F.col("_uk"), "left_anti"
    )

    return cur_history.unionByName(expired).unionByName(unchanged).unionByName(changed_new)
