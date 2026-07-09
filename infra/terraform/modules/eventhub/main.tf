# Event Hubs namespace + gh-events hub for the streaming path.
#
# NOTE on Basic SKU: only the built-in "$Default" consumer group is allowed and
# max message retention is 1 day. The custom consumer group is therefore created
# only when SKU != Basic; on Basic the streaming consumer reads "$Default".

locals {
  is_basic = var.sku == "Basic"
  # Basic caps retention at 1 day.
  message_retention = local.is_basic ? 1 : var.message_retention
}

resource "azurerm_eventhub_namespace" "this" {
  name                = var.namespace_name
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = var.sku
  capacity            = 1

  tags = var.tags
}

resource "azurerm_eventhub" "this" {
  name                = var.hub_name
  namespace_name      = azurerm_eventhub_namespace.this.name
  resource_group_name = var.resource_group_name
  partition_count     = var.partition_count
  message_retention   = local.message_retention
}

# Producer (Event Hubs producer) + consumer (Structured Streaming) share this
# rule. Its connection string is stored in Key Vault by the root module.
resource "azurerm_eventhub_authorization_rule" "app" {
  name                = "gh-events-app"
  namespace_name      = azurerm_eventhub_namespace.this.name
  eventhub_name       = azurerm_eventhub.this.name
  resource_group_name = var.resource_group_name

  listen = true
  send   = true
  manage = false
}

resource "azurerm_eventhub_consumer_group" "streaming" {
  count = local.is_basic ? 0 : 1

  name                = var.consumer_group
  namespace_name      = azurerm_eventhub_namespace.this.name
  eventhub_name       = azurerm_eventhub.this.name
  resource_group_name = var.resource_group_name
}
