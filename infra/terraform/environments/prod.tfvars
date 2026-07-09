subscription_id    = "d5f98fab-893f-45ce-9fdc-c3399ba9f46f"
env                = "prod"
location           = "centralindia"
prefix             = "ghanalytics"
notification_email = "dbdaproject787@gmail.com"

# Standard enables a dedicated "streaming" consumer group + longer retention.
eventhub_sku             = "Standard"
eventhub_partition_count = 4

landing_retention_days = 90
