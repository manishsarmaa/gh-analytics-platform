output "namespace_name" {
  value = azurerm_eventhub_namespace.this.name
}

output "hub_name" {
  value = azurerm_eventhub.this.name
}

output "consumer_group" {
  description = "Consumer group the streaming job should read from."
  value       = var.sku == "Basic" ? "$Default" : var.consumer_group
}

output "primary_connection_string" {
  description = "Entity-scoped connection string (listen+send)."
  value       = azurerm_eventhub_authorization_rule.app.primary_connection_string
  sensitive   = true
}
