# Databricks notebook source
# MAGIC %md
# MAGIC # Silver Transformation
# MAGIC `bronze.gh_events_batch` → `silver.events` (cleaned, parsed, deduplicated).
# MAGIC
# MAGIC - Incremental: processes only the `execution_date` bronze partition
# MAGIC - Idempotent MERGE on `event_id` (update + insert) — safe to re-run
# MAGIC - Repo SCD2 / actor dim / metadata enrichment: Phase 7

# COMMAND ----------
dbutils.widgets.text("env", "dev")
dbutils.widgets.text("execution_date", "")  # yyyy-MM-dd; empty = full reprocess

# COMMAND ----------
import json
import sys

_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
_src_root = "/Workspace" + _ctx.notebookPath().get().rsplit("/notebooks/", 1)[0]
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

from delta.tables import DeltaTable  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

from transformations.silver import to_silver_events  # noqa: E402
from utils.config import load_config  # noqa: E402
from utils.logging import get_logger  # noqa: E402

# COMMAND ----------
env = dbutils.widgets.get("env")
execution_date = dbutils.widgets.get("execution_date")

cfg = load_config(env)
bronze_table = cfg.table("bronze", "gh_events_batch")
silver_table = cfg.table("silver", "events")

log = get_logger("silver_transformation", env=env, execution_date=execution_date, table=silver_table)

# COMMAND ----------
# MAGIC %md ### Incremental read of bronze (current partition only)

# COMMAND ----------
bronze = spark.read.table(bronze_table)
if execution_date:
    bronze = bronze.filter(F.col("event_date") == F.to_date(F.lit(execution_date)))

silver = to_silver_events(bronze, source="batch")
row_count = silver.count()
log.info("transformed", rows=row_count, source_partition=execution_date or "ALL")

# COMMAND ----------
# MAGIC %md ### Idempotent MERGE into silver.events

# COMMAND ----------
if not spark.catalog.tableExists(silver_table):
    silver.write.format("delta").partitionBy("event_date").saveAsTable(silver_table)
    log.info("silver_created", rows=row_count, table=silver_table)
else:
    (
        DeltaTable.forName(spark, silver_table)
        .alias("t")
        .merge(silver.alias("s"), "t.event_id = s.event_id")
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
    log.info("silver_merged", source_rows=row_count, table=silver_table)

# COMMAND ----------
metrics = {"rows": row_count, "silver_table": silver_table, "execution_date": execution_date}
log.info("done", **metrics)
dbutils.notebook.exit(json.dumps(metrics))
