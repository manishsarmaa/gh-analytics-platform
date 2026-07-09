# =============================================================================
# GH Analytics Platform — Azure infrastructure (Phase 1)
#
# Composition root. Creates the resource group and wires the modules:
#   storage · keyvault · eventhub · databricks · adf · rbac
#
# Global-unique names get a random suffix (override via var.name_suffix).
# =============================================================================

data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 5
  special = false
  upper   = false
  numeric = true
}

locals {
  suffix = var.name_suffix != "" ? var.name_suffix : random_string.suffix.result

  tags = merge(
    {
      project    = "gh-analytics-platform"
      env        = var.env
      managed_by = "terraform"
    },
    var.tags,
  )

  # Storage account: lowercase alphanumeric only, <= 24 chars.
  storage_account_name  = "${var.prefix}${var.env}${local.suffix}"
  key_vault_name        = "ghan-${var.env}-kv-${local.suffix}"
  eventhub_namespace    = "ghan-${var.env}-ehns-${local.suffix}"
  data_factory_name     = "ghan-${var.env}-adf-${local.suffix}"
  databricks_workspace  = "ghan-${var.env}-dbw"
  access_connector_name = "ghan-${var.env}-dbw-ac"

  containers = ["landing", "bronze", "silver", "gold", "checkpoints", "quarantine"]
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${var.prefix}-${var.env}"
  location = var.location
  tags     = local.tags
}

module "storage" {
  source = "./modules/storage"

  storage_account_name   = local.storage_account_name
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  containers             = local.containers
  landing_retention_days = var.landing_retention_days
  landing_container      = "landing"
  tags                   = local.tags
}

module "keyvault" {
  source = "./modules/keyvault"

  key_vault_name      = local.key_vault_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  tags                = local.tags
}

module "eventhub" {
  source = "./modules/eventhub"

  namespace_name      = local.eventhub_namespace
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = var.eventhub_sku
  hub_name            = "gh-events"
  partition_count     = var.eventhub_partition_count
  consumer_group      = "streaming"
  tags                = local.tags
}

module "databricks" {
  source = "./modules/databricks"

  workspace_name        = local.databricks_workspace
  access_connector_name = local.access_connector_name
  resource_group_name   = azurerm_resource_group.main.name
  location              = azurerm_resource_group.main.location
  managed_rg_name       = "rg-${var.prefix}-${var.env}-dbw-managed"
  tags                  = local.tags
}

module "adf" {
  source = "./modules/adf"

  factory_name        = local.data_factory_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.tags
}

module "rbac" {
  source = "./modules/rbac"

  storage_account_id                = module.storage.id
  key_vault_id                      = module.keyvault.id
  adf_principal_id                  = module.adf.identity_principal_id
  databricks_connector_principal_id = module.databricks.access_connector_principal_id
  current_user_object_id            = data.azurerm_client_config.current.object_id
  azure_databricks_sp_object_id     = var.azure_databricks_sp_object_id
}

# ---------------------------------------------------------------------------
# Seed the Event Hubs connection string into Key Vault (as code).
# RBAC role assignments (module.rbac) take a moment to propagate, so wait
# before the current principal writes the secret. If this ever races on a
# first apply, a second `terraform apply` resolves it.
# ---------------------------------------------------------------------------
resource "time_sleep" "wait_for_kv_rbac" {
  depends_on      = [module.rbac]
  create_duration = "60s"
}

resource "azurerm_key_vault_secret" "eventhub_connection" {
  name         = "eventhub-connection-string"
  value        = module.eventhub.primary_connection_string
  key_vault_id = module.keyvault.id

  depends_on = [time_sleep.wait_for_kv_rbac]
}
