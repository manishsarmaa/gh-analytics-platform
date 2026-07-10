# Databricks notebook source
# MAGIC %md
# MAGIC # Gold Aggregation
# MAGIC `silver.events` → gold aggregate tables.
# MAGIC
# MAGIC Event-only tables (this phase): `event_type_summary_hourly`,
# MAGIC `hot_repos_hourly`, `contributor_activity_daily`.
# MAGIC Metadata-dependent tables (`language_trends_daily`, `topic_trends_daily`)
# MAGIC are added in Phase 8.
# MAGIC
# MAGIC Idempotent: recomputes the `execution_date` day and overwrites just that
# MAGIC partition (`replaceWhere`), so re-runs are safe.

# COMMAND ----------
dbutils.widgets.text("env", "dev")
dbutils.widgets.text("execution_date", "")  # yyyy-MM-dd; empty = full rebuild

# COMMAND ----------
import json
import sys

_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
_src_root = "/Workspace" + _ctx.notebookPath().get().rsplit("/notebooks/", 1)[0]
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

from pyspark.sql import functions as F  # noqa: E402

from transformations.gold import (  # noqa: E402
    contributor_activity_daily,
    event_type_summary_hourly,
    hot_repos_hourly,
    language_trends_daily,
    topic_trends_daily,
)
from utils.config import load_config  # noqa: E402
from utils.logging import get_logger  # noqa: E402

# COMMAND ----------
env = dbutils.widgets.get("env")
execution_date = dbutils.widgets.get("execution_date")

cfg = load_config(env)
silver_table = cfg.table("silver", "events")
log = get_logger("gold_aggregation", env=env, execution_date=execution_date)

TABLES = {
    "event_type_summary_hourly": event_type_summary_hourly,
    "hot_repos_hourly": hot_repos_hourly,
    "contributor_activity_daily": contributor_activity_daily,
}

# COMMAND ----------
events = spark.read.table(silver_table)
if execution_date:
    events = events.filter(F.col("event_date") == F.to_date(F.lit(execution_date)))
log.info("silver_read", rows=events.count(), partition=execution_date or "ALL")


# COMMAND ----------
def write_gold(df, name: str) -> int:
    table = cfg.table("gold", name)
    writer = df.write.format("delta").partitionBy("event_date")
    if not spark.catalog.tableExists(table):
        writer.mode("overwrite").saveAsTable(table)
    elif execution_date:
        writer.mode("overwrite").option(
            "replaceWhere", f"event_date = '{execution_date}'"
        ).saveAsTable(table)
    else:
        writer.mode("overwrite").saveAsTable(table)
    return spark.read.table(table).count()


# COMMAND ----------
metrics = {}
for name, fn in TABLES.items():
    df = fn(events)
    rows_written = df.count()
    total = write_gold(df, name)
    metrics[name] = {"written": rows_written, "table_total": total}
    log.info("gold_written", table=name, rows=rows_written, table_total=total)

# COMMAND ----------
# MAGIC %md ### Metadata-dependent trends (only if silver.repos_scd2 exists)

# COMMAND ----------
repos_table = cfg.table("silver", "repos_scd2")
if spark.catalog.tableExists(repos_table):
    repos = spark.read.table(repos_table)
    for name, fn in {
        "language_trends_daily": language_trends_daily,
        "topic_trends_daily": topic_trends_daily,
    }.items():
        df = fn(events, repos)
        rows_written = df.count()
        total = write_gold(df, name)
        metrics[name] = {"written": rows_written, "table_total": total}
        log.info("gold_written", table=name, rows=rows_written, table_total=total)
else:
    log.info("trends_skipped", reason=f"{repos_table} not found — run repo metadata refresh first")

# COMMAND ----------
log.info("done", **{"execution_date": execution_date, "tables": list(metrics)})
dbutils.notebook.exit(json.dumps(metrics))
