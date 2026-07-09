# Least-privilege role assignments.
#
# principal_type is set explicitly so Azure skips the AAD existence check that
# can otherwise fail immediately after a managed identity is created (the SP
# may not have replicated yet).

# --- ADF managed identity -> Storage (Copy Activity writes to landing) ---
resource "azurerm_role_assignment" "adf_storage" {
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.adf_principal_id
  principal_type       = "ServicePrincipal"
}

# --- ADF managed identity -> Key Vault (linked services fetch secrets) ---
resource "azurerm_role_assignment" "adf_keyvault" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.adf_principal_id
  principal_type       = "ServicePrincipal"
}

# --- Databricks access connector -> Storage (Unity Catalog / clusters) ---
resource "azurerm_role_assignment" "databricks_storage" {
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.databricks_connector_principal_id
  principal_type       = "ServicePrincipal"
}

# --- Current user -> Key Vault (add PAT secrets via CLI/portal) ---
resource "azurerm_role_assignment" "user_keyvault" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.current_user_object_id
  principal_type       = "User"
}

# --- Current user -> Storage (browse/manage data during dev) ---
resource "azurerm_role_assignment" "user_storage" {
  scope                = var.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.current_user_object_id
  principal_type       = "User"
}
