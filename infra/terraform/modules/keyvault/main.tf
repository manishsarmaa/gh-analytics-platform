# Key Vault with RBAC authorization. Secrets (GitHub PAT, Databricks PAT) are
# added manually post-apply; the Event Hubs connection string is seeded by
# Terraform in the root module. Access is granted via the rbac module.

resource "azurerm_key_vault" "this" {
  name                = var.key_vault_name
  resource_group_name = var.resource_group_name
  location            = var.location
  tenant_id           = var.tenant_id
  sku_name            = "standard"

  enable_rbac_authorization = true

  # Trial-friendly: allow clean teardown/recreate.
  purge_protection_enabled   = false
  soft_delete_retention_days = 7

  tags = var.tags
}
