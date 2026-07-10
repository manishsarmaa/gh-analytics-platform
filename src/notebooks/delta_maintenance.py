# Databricks notebook source
# MAGIC %md
# MAGIC # Delta Maintenance — OPTIMIZE + Z-ORDER + VACUUM
# MAGIC Compacts small files and clusters each table on its common filter columns,
# MAGIC then reclaims tombstoned files. Runs daily (Phase 11 trigger).

# COMMAND ----------
dbutils.widgets.text("env", "dev")
dbutils.widgets.text("vacuum_retention_hours", "168")  # 7 days (Delta default floor)

# COMMAND ----------
import json
import sys

_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
_src_root = "/Workspace" + _ctx.notebookPath().get().rsplit("/notebooks/", 1)[0]
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

from utils.config import load_config  # noqa: E402
from utils.logging import get_logger  # noqa: E402

# COMMAND ----------
env = dbutils.widgets.get("env")
retention_hours = float(dbutils.widgets.get("vacuum_retention_hours"))
cfg = load_config(env)
log = get_logger("delta_maintenance", env=env)

# table (layer, name) -> Z-ORDER columns (common filter/join keys)
PLAN = {
    ("bronze", "gh_events_batch"): ["repo_id"],
    ("silver", "events"): ["repo_id", "event_type"],
    ("silver", "repos_scd2"): ["repo_id"],
    ("gold", "hot_repos_hourly"): ["repo_id"],
    ("gold", "event_type_summary_hourly"): ["event_type"],
    ("gold", "contributor_activity_daily"): ["actor_id"],
    ("gold", "language_trends_daily"): ["primary_language"],
    ("gold", "topic_trends_daily"): ["topic"],
}

# COMMAND ----------
# MAGIC %md ### OPTIMIZE + ZORDER

# COMMAND ----------
metrics = {}
for (layer, name), zcols in PLAN.items():
    table = cfg.table(layer, name)
    if not spark.catalog.tableExists(table):
        continue
    spark.sql(f"OPTIMIZE {table} ZORDER BY ({', '.join(zcols)})")
    log.info("optimized", table=table, zorder=zcols)
    metrics[table] = "optimized"

# COMMAND ----------
# MAGIC %md ### VACUUM (reclaim files past retention)

# COMMAND ----------
for (layer, name), _ in PLAN.items():
    table = cfg.table(layer, name)
    if not spark.catalog.tableExists(table):
        continue
    spark.sql(f"VACUUM {table} RETAIN {retention_hours} HOURS")
    log.info("vacuumed", table=table, retain_hours=retention_hours)

log.info("done", tables=len(metrics))
dbutils.notebook.exit(json.dumps({"maintained": list(metrics)}))
