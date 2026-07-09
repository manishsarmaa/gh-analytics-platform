output "resource_group_name" {
  description = "Main resource group."
  value       = azurerm_resource_group.main.name
}

output "storage_account_name" {
  description = "ADLS Gen2 account name — put this in configs/<env>.yaml storage.account_name."
  value       = module.storage.name
}

output "storage_dfs_endpoint" {
  description = "Primary DFS (ADLS Gen2) endpoint."
  value       = module.storage.primary_dfs_endpoint
}

output "key_vault_name" {
  description = "Key Vault name — put this in configs/<env>.yaml keyvault.name."
  value       = module.keyvault.name
}

output "key_vault_uri" {
  description = "Key Vault URI (used by ADF linked service + Databricks secret scope)."
  value       = module.keyvault.uri
}

output "eventhub_namespace" {
  description = "Event Hubs namespace name."
  value       = module.eventhub.namespace_name
}

output "databricks_workspace_url" {
  description = "Databricks workspace URL — put this in configs/<env>.yaml databricks.workspace_url."
  value       = module.databricks.workspace_url
}

output "databricks_workspace_id" {
  description = "Databricks workspace Azure resource ID (for the Databricks provider + ADF linked service)."
  value       = module.databricks.workspace_id
}

output "databricks_access_connector_id" {
  description = "Access connector resource ID (used by Unity Catalog storage credential in Phase 2)."
  value       = module.databricks.access_connector_id
}

output "data_factory_name" {
  description = "Azure Data Factory name."
  value       = module.adf.name
}

output "data_factory_identity_principal_id" {
  description = "ADF managed identity principal ID (granted Storage + Key Vault access)."
  value       = module.adf.identity_principal_id
}

# Convenience: the exact config keys to update after apply.
output "config_updates_needed" {
  description = "Copy these into configs/<env>.yaml."
  value = {
    "storage.account_name"      = module.storage.name
    "keyvault.name"             = module.keyvault.name
    "eventhub.namespace"        = module.eventhub.namespace_name
    "adf.factory_name"          = module.adf.name
    "databricks.workspace_url"  = module.databricks.workspace_url
    "azure.resource_group"      = azurerm_resource_group.main.name
  }
}
