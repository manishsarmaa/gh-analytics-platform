# Databricks notebook source
# MAGIC %md
# MAGIC # Data Quality Checks
# MAGIC Runs custom checks for a layer and appends results to `ops.dq_results`.
# MAGIC Raises on any **critical** failure so the ADF activity fails → alert.
# MAGIC
# MAGIC Great Expectations suites are added on top in Phase 9.

# COMMAND ----------
dbutils.widgets.text("env", "dev")
dbutils.widgets.dropdown("layer", "bronze", ["bronze", "silver", "gold"])
dbutils.widgets.text("execution_date", "")
dbutils.widgets.text("run_id", "")

# COMMAND ----------
import sys

_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
_src_root = "/Workspace" + _ctx.notebookPath().get().rsplit("/notebooks/", 1)[0]
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

from pyspark.sql import functions as F  # noqa: E402

from dq.runner import (  # noqa: E402
    check_accepted_values,
    check_not_null,
    check_row_count_min,
    check_unique,
    has_critical_failure,
    results_to_rows,
)
from utils.config import load_config  # noqa: E402
from utils.logging import get_logger  # noqa: E402

# COMMAND ----------
env = dbutils.widgets.get("env")
layer = dbutils.widgets.get("layer")
execution_date = dbutils.widgets.get("execution_date")
run_id = dbutils.widgets.get("run_id") or f"{layer}-{execution_date}"

cfg = load_config(env)
results_table = cfg.table("ops", "dq_results")
log = get_logger("dq_checks", env=env, layer=layer, execution_date=execution_date, run_id=run_id)

# COMMAND ----------
# MAGIC %md ### Layer-specific check suite

# COMMAND ----------
_KNOWN_EVENT_TYPES = [
    "PushEvent", "PullRequestEvent", "IssuesEvent", "IssueCommentEvent",
    "WatchEvent", "ForkEvent", "CreateEvent", "DeleteEvent", "ReleaseEvent",
    "PullRequestReviewEvent", "PullRequestReviewCommentEvent", "CommitCommentEvent",
    "GollumEvent", "MemberEvent", "PublicEvent",
]


def suite_for(layer: str, df):
    if layer == "bronze":
        return [
            check_row_count_min(df, 1),
            check_not_null(df, ["event_id", "event_type", "repo_id", "repo_name", "event_timestamp"]),
            check_unique(df, "event_id"),
        ]
    if layer == "silver":
        return [
            check_row_count_min(df, 1),
            check_not_null(df, ["event_id", "event_type", "repo_id"]),
            check_unique(df, "event_id"),
            check_accepted_values(df, "event_type", _KNOWN_EVENT_TYPES),
        ]
    # gold
    return [check_row_count_min(df, 1)]


_LAYER_TABLE = {
    "bronze": ("bronze", "gh_events_batch"),
    "silver": ("silver", "events"),
    "gold": ("gold", "event_type_summary_hourly"),
}

# COMMAND ----------
schema, name = _LAYER_TABLE[layer]
table = cfg.table(schema, name)
df = spark.read.table(table)
if execution_date and "event_date" in df.columns:
    df = df.filter(F.col("event_date") == F.to_date(F.lit(execution_date)))

results = suite_for(layer, df)

# Great Expectations suite (runs only where great-expectations is installed —
# the DQ tasks get it via the job's `dq` environment; graceful elsewhere).
try:
    from dq.expectations.suites import suite_for as gx_suite_for
    from dq.gx_runner import run_suite

    # GX runs on a bounded pandas sample (its Spark backend persists internally,
    # which serverless rejects). The custom Spark checks above are the full-table
    # gate; GX adds declarative expectation coverage on the sample.
    sample_pdf = df.limit(20000).toPandas()
    gx_results = run_suite(sample_pdf, gx_suite_for(layer))
    results = results + gx_results
    log.info("gx_ran", checks=len(gx_results), sample_rows=len(sample_pdf))
except ImportError:
    log.info("gx_skipped", reason="great-expectations not installed")

for r in results:
    log.info("check", name=r.check_name, passed=r.passed, observed=r.observed, severity=r.severity)

# COMMAND ----------
# MAGIC %md ### Persist results to ops.dq_results

# COMMAND ----------
rows = results_to_rows(
    results, layer=layer, table=table, run_id=run_id, execution_date=execution_date
)
(
    spark.createDataFrame(rows)
    .withColumn("checked_at", F.current_timestamp())
    .write.format("delta")
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable(results_table)
)
log.info("dq_results_written", table=results_table, checks=len(rows))

# COMMAND ----------
# MAGIC %md ### Fail loudly on critical breach (ADF picks this up)

# COMMAND ----------
if has_critical_failure(results):
    failed = [r.check_name for r in results if not r.passed and r.severity == "critical"]
    log.error("critical_dq_failure", failed=failed)
    raise Exception(f"Critical DQ failure in {layer} ({table}): {failed}")

log.info("dq_passed", layer=layer, checks=len(rows))
dbutils.notebook.exit(f"DQ OK: {len(rows)} checks on {layer}")
