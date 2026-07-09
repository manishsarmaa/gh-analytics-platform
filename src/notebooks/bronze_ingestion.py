# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze Ingestion
# MAGIC Landing `.json.gz` (GH Archive) → `gh_analytics_dev.bronze.gh_events_batch`.
# MAGIC
# MAGIC - Schema-enforced by construction (JSON-path extraction, no inference)
# MAGIC - Invalid rows → `ops.quarantine` (dead-letter), never dropped silently
# MAGIC - Idempotent MERGE on `event_id` — re-running the same hour is a no-op
# MAGIC
# MAGIC Parameters are passed by ADF via `baseParameters`.

# COMMAND ----------
dbutils.widgets.text("env", "dev")
dbutils.widgets.text("landing_path", "")
dbutils.widgets.text("source_file", "")
dbutils.widgets.text("execution_date", "")

# COMMAND ----------
# MAGIC %md ### Make the synced `src` package tree importable + load helpers

# COMMAND ----------
import json
import sys

# When deployed via DAB, this notebook lives at .../files/src/notebooks/... and
# the shared modules at .../files/src/. Put that root on the path.
_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
_nb_path = _ctx.notebookPath().get()
_src_root = "/Workspace" + _nb_path.rsplit("/notebooks/", 1)[0]
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

from delta.tables import DeltaTable  # noqa: E402

from transformations.bronze import split_valid_quarantine, to_bronze  # noqa: E402
from utils.config import load_config  # noqa: E402
from utils.logging import get_logger  # noqa: E402

# COMMAND ----------
env = dbutils.widgets.get("env")
landing_path = dbutils.widgets.get("landing_path")
source_file = dbutils.widgets.get("source_file") or landing_path
execution_date = dbutils.widgets.get("execution_date")

cfg = load_config(env)
bronze_table = cfg.table("bronze", "gh_events_batch")
quarantine_table = cfg.table("ops", "quarantine")

log = get_logger("bronze_ingestion", env=env, execution_date=execution_date, table=bronze_table)
log.info("start", landing_path=landing_path, source_file=source_file)

if not landing_path:
    raise ValueError("landing_path widget is required")

# COMMAND ----------
# MAGIC %md ### Read landing → transform → split valid / quarantine

# COMMAND ----------
raw = spark.read.text(landing_path)  # Spark auto-decompresses .json.gz
bronze = to_bronze(raw, source_file=source_file)
valid, quarantine = split_valid_quarantine(bronze)

valid_count = valid.count()
quarantine_count = quarantine.count()
log.info("transformed", valid=valid_count, quarantined=quarantine_count)

# COMMAND ----------
# MAGIC %md ### Quarantine bad rows (append)

# COMMAND ----------
if quarantine_count > 0:
    (
        quarantine.write.format("delta")
        .mode("append")
        .option("mergeSchema", "true")
        .saveAsTable(quarantine_table)
    )
    log.info("quarantine_written", rows=quarantine_count, table=quarantine_table)

# COMMAND ----------
# MAGIC %md ### Idempotent MERGE into bronze (insert-only on new event_id)

# COMMAND ----------
if not spark.catalog.tableExists(bronze_table):
    (
        valid.write.format("delta")
        .partitionBy("event_date")
        .saveAsTable(bronze_table)
    )
    log.info("bronze_created", rows=valid_count, table=bronze_table)
else:
    (
        DeltaTable.forName(spark, bronze_table)
        .alias("t")
        .merge(valid.alias("s"), "t.event_id = s.event_id")
        .whenNotMatchedInsertAll()
        .execute()
    )
    log.info("bronze_merged", source_rows=valid_count, table=bronze_table)

# COMMAND ----------
metrics = {
    "valid": valid_count,
    "quarantined": quarantine_count,
    "bronze_table": bronze_table,
    "execution_date": execution_date,
}
log.info("done", **metrics)
dbutils.notebook.exit(json.dumps(metrics))
