subscription_id    = "d5f98fab-893f-45ce-9fdc-c3399ba9f46f"
env                = "dev"
location           = "centralindia"
prefix             = "ghanalytics"
notification_email = "dbdaproject787@gmail.com"

# Standard tier enables the Kafka endpoint (required for Spark Structured
# Streaming on serverless) + a dedicated "streaming" consumer group.
# (Basic has no Kafka endpoint; the serverless consumer can't load the AMQP JAR.)
eventhub_sku             = "Standard"
eventhub_partition_count = 2

landing_retention_days = 90

# First-party AzureDatabricks SP object id (this tenant) — grants KV read for
# the KV-backed secret scope. From: az ad sp show --id 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d --query id -o tsv
azure_databricks_sp_object_id = "4ba406a7-7648-445e-b060-ca119f167f46"
