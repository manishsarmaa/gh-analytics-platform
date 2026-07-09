# ADLS Gen2 storage account (hierarchical namespace) + medallion containers
# + landing-zone lifecycle policy.

resource "azurerm_storage_account" "this" {
  name                     = var.storage_account_name
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS" # cheapest; sufficient for a trial/dev lake
  account_kind             = "StorageV2"
  is_hns_enabled           = true  # hierarchical namespace = ADLS Gen2
  min_tls_version          = "TLS1_2"

  # NOTE: azurerm 3.x uses this attribute name (emits a harmless deprecation
  # warning). Rename to `https_traffic_only_enabled` when upgrading to v4.0.
  enable_https_traffic_only = true

  blob_properties {
    delete_retention_policy {
      days = 7
    }
  }

  tags = var.tags
}

resource "azurerm_storage_container" "this" {
  for_each = toset(var.containers)

  name                  = each.value
  storage_account_name  = azurerm_storage_account.this.name
  container_access_type = "private"
}

# Expire raw landing files after N days (immutable raw zone, controlled cost).
resource "azurerm_storage_management_policy" "lifecycle" {
  storage_account_id = azurerm_storage_account.this.id

  rule {
    name    = "expire-landing"
    enabled = true

    filters {
      prefix_match = ["${var.landing_container}/"]
      blob_types   = ["blockBlob"]
    }

    actions {
      base_blob {
        delete_after_days_since_modification_greater_than = var.landing_retention_days
      }
    }
  }

  depends_on = [azurerm_storage_container.this]
}
