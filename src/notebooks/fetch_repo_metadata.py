# Databricks notebook source
# MAGIC %md
# MAGIC # Fetch Repo Metadata → silver.repos_scd2 (SCD Type 2)
# MAGIC Enriches the most-active repos from `silver.events` with GitHub REST API
# MAGIC metadata (language, stars, forks, topics, ...) and upserts an SCD2 repo
# MAGIC dimension. Rate-limit aware (5000 req/hr authenticated).
# MAGIC
# MAGIC Secret: `github-pat` from the `gh-analytics-kv` scope.

# COMMAND ----------
dbutils.widgets.text("env", "dev")
dbutils.widgets.text("batch_size", "100")

# COMMAND ----------
import sys
import time

import requests

_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
_src_root = "/Workspace" + _ctx.notebookPath().get().rsplit("/notebooks/", 1)[0]
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql import types as T  # noqa: E402

from transformations.scd2 import scd2_upsert  # noqa: E402
from utils.config import load_config  # noqa: E402
from utils.logging import get_logger  # noqa: E402

# COMMAND ----------
env = dbutils.widgets.get("env")
batch_size = int(dbutils.widgets.get("batch_size"))

cfg = load_config(env)
silver_events = cfg.table("silver", "events")
repos_table = cfg.table("silver", "repos_scd2")
log = get_logger("fetch_repo_metadata", env=env, table=repos_table)

GITHUB_PAT = dbutils.secrets.get(cfg.get("databricks", "secret_scope"), "github-pat")
TRACKED = ["repo_name", "primary_language", "stargazers_count", "forks_count", "open_issues_count", "topics", "is_fork"]

# COMMAND ----------
# MAGIC %md ### Pick the most-active repos to enrich

# COMMAND ----------
targets = [
    (r["repo_id"], r["repo_name"])
    for r in (
        spark.read.table(silver_events)
        # Rank by DISTINCT actors, not raw events: spam repos flood many events
        # from 1-2 accounts (and get deleted -> 404); real repos have many
        # distinct contributors. Non-bot actors only.
        .filter(~F.col("is_bot"))
        .groupBy("repo_id", "repo_name")
        .agg(F.countDistinct("actor_id").alias("actors"), F.count("*").alias("activity"))
        .filter(F.col("actors") >= 3)
        .orderBy(F.desc("actors"), F.desc("activity"))
        .limit(batch_size)
        .collect()
    )
]
log.info("targets_selected", count=len(targets))

# COMMAND ----------
# MAGIC %md ### Fetch from GitHub REST API (rate-limit aware)

# COMMAND ----------
from collections import Counter  # noqa: E402

SESSION = requests.Session()
SESSION.headers.update({"Authorization": f"Bearer {GITHUB_PAT}", "Accept": "application/vnd.github+json"})

# Operational telemetry (surfaced in the notebook exit; serverless has no stdout).
_statuses: Counter = Counter()
_sample_err = None


def fetch_repo(repo_id: int, repo_name: str) -> dict | None:
    global _sample_err
    try:
        resp = SESSION.get(f"https://api.github.com/repos/{repo_name}", timeout=30)
    except Exception as e:  # network/egress issue surfaces here
        _statuses["EXC"] += 1
        _sample_err = _sample_err or f"EXC {type(e).__name__}: {str(e)[:150]}"
        return None

    _statuses[resp.status_code] += 1
    if resp.status_code == 200:
        d = resp.json()
        return {
            "repo_id": repo_id,
            "repo_name": repo_name,
            "primary_language": d.get("language"),
            "stargazers_count": d.get("stargazers_count"),
            "forks_count": d.get("forks_count"),
            "open_issues_count": d.get("open_issues_count"),
            "topics": ",".join(sorted(d.get("topics") or [])),
            "description": d.get("description"),
            "is_fork": bool(d.get("fork")),
            "size_kb": d.get("size"),
        }
    if resp.status_code == 404:
        return None  # repo deleted/renamed since the event
    if resp.status_code in (403, 429) and resp.headers.get("X-RateLimit-Remaining") == "0":
        reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
        wait = max(0, reset - time.time()) + 1
        log.info("rate_limited", sleep_s=int(wait))
        time.sleep(wait)
        return fetch_repo(repo_id, repo_name)
    _sample_err = _sample_err or f"{resp.status_code}: {resp.text[:150]}"
    return None


records = []
for rid, rname in targets:
    rec = fetch_repo(rid, rname)
    if rec:
        records.append(rec)
    time.sleep(0.05)  # gentle pacing

log.info("fetch_diag", targets=len(targets), statuses=dict(_statuses), sample_err=_sample_err)

log.info("fetched", ok=len(records), attempted=len(targets))

# COMMAND ----------
# MAGIC %md ### Build snapshot → SCD2 upsert → overwrite

# COMMAND ----------
schema = T.StructType(
    [
        T.StructField("repo_id", T.LongType()),
        T.StructField("repo_name", T.StringType()),
        T.StructField("primary_language", T.StringType()),
        T.StructField("stargazers_count", T.IntegerType()),
        T.StructField("forks_count", T.IntegerType()),
        T.StructField("open_issues_count", T.IntegerType()),
        T.StructField("topics", T.StringType()),
        T.StructField("description", T.StringType()),
        T.StructField("is_fork", T.BooleanType()),
        T.StructField("size_kb", T.IntegerType()),
    ]
)
incoming = spark.createDataFrame(records, schema)

current = spark.read.table(repos_table) if spark.catalog.tableExists(repos_table) else None
effective_ts = spark.sql("select current_timestamp() as t").collect()[0]["t"]
new_state = scd2_upsert(current, incoming, key="repo_id", tracked_cols=TRACKED, effective_ts=effective_ts)

(new_state.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(repos_table))

total = spark.read.table(repos_table)
metrics = {
    "rows_total": total.count(),
    "current": total.filter("is_current").count(),
    "historical": total.filter("not is_current").count(),
    "fetched": len(records),
    "targets": len(targets),
    "statuses": dict(_statuses),
    "sample_err": _sample_err,
}
log.info("done", **metrics)
dbutils.notebook.exit(str(metrics))
