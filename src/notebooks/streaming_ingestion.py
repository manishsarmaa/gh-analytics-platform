# Databricks notebook source
# MAGIC %md
# MAGIC # Streaming Ingestion (Event Hubs → bronze.gh_events_stream → silver.events)
# MAGIC Structured Streaming from the Event Hubs **Kafka endpoint** (needs EH
# MAGIC Standard tier). `foreachBatch` reuses the batch transforms, so streaming
# MAGIC and batch share one code path and MERGE into the same `silver.events`.
# MAGIC
# MAGIC Runs as a Databricks Workflow (NOT ADF). `trigger=availableNow` processes
# MAGIC the backlog then stops (cheap demo); switch to `processingTime` for live.

# COMMAND ----------
dbutils.widgets.text("env", "dev")
dbutils.widgets.dropdown("trigger_mode", "availableNow", ["availableNow", "continuous30s"])

# COMMAND ----------
import sys

_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
_src_root = "/Workspace" + _ctx.notebookPath().get().rsplit("/notebooks/", 1)[0]
if _src_root not in sys.path:
    sys.path.insert(0, _src_root)

from delta.tables import DeltaTable  # noqa: E402

from transformations.bronze import split_valid_quarantine, to_bronze  # noqa: E402
from transformations.silver import to_silver_events  # noqa: E402
from utils.config import load_config  # noqa: E402
from utils.logging import get_logger  # noqa: E402

# COMMAND ----------
env = dbutils.widgets.get("env")
trigger_mode = dbutils.widgets.get("trigger_mode")

cfg = load_config(env)
stream_bronze = cfg.table("bronze", "gh_events_stream")
silver_table = cfg.table("silver", "events")
quarantine_table = cfg.table("ops", "quarantine")
checkpoint = cfg.abfss("checkpoints", "bronze_stream")
namespace = cfg.get("eventhub", "namespace")
hub = cfg.get("eventhub", "hub_name")
log = get_logger("streaming_ingestion", env=env, table=stream_bronze)

conn = dbutils.secrets.get(cfg.get("databricks", "secret_scope"), "eventhub-connection-string")
jaas = (
    "kafkashaded.org.apache.kafka.common.security.plain.PlainLoginModule required "
    f'username="$ConnectionString" password="{conn}";'
)

# COMMAND ----------
raw = (
    spark.readStream.format("kafka")
    .option("kafka.bootstrap.servers", f"{namespace}.servicebus.windows.net:9093")
    .option("kafka.security.protocol", "SASL_SSL")
    .option("kafka.sasl.mechanism", "PLAIN")
    .option("kafka.sasl.jaas.config", jaas)
    .option("subscribe", hub)
    # EH requires the Kafka consumer group to exist (created on Standard tier).
    .option("kafka.group.id", cfg.get("eventhub", "consumer_group"))
    .option("startingOffsets", "earliest")
    .option("maxOffsetsPerTrigger", "2000")
    .load()
)


# COMMAND ----------
def _merge(target, df, when_matched_update=False):
    if not spark.catalog.tableExists(target):
        df.write.format("delta").partitionBy("event_date").saveAsTable(target)
        return
    merge = (
        DeltaTable.forName(spark, target)
        .alias("t")
        .merge(df.alias("s"), "t.event_id = s.event_id")
    )
    if when_matched_update:
        merge = merge.whenMatchedUpdateAll()
    merge.whenNotMatchedInsertAll().execute()


def process_batch(batch_df, batch_id):
    events = batch_df.selectExpr("CAST(value AS STRING) AS value")
    bronze = to_bronze(events, source_file="eventhub")
    valid, quarantine = split_valid_quarantine(bronze)

    _merge(stream_bronze, valid)  # bronze.gh_events_stream (insert-only)
    _merge(silver_table, to_silver_events(valid, source="stream"), when_matched_update=True)

    if quarantine.count() > 0:
        quarantine.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(
            quarantine_table
        )
    log.info("micro_batch", batch_id=batch_id, valid=valid.count())


# COMMAND ----------
writer = (
    raw.writeStream.foreachBatch(process_batch)
    .option("checkpointLocation", checkpoint)
    .queryName("gh_events_stream")
)
query = (
    writer.trigger(availableNow=True).start()
    if trigger_mode == "availableNow"
    else writer.trigger(processingTime="30 seconds").start()
)
query.awaitTermination()
