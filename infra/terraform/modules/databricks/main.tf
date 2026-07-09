# Azure Databricks (Premium) workspace + Access Connector.
#
# The Access Connector is a managed identity that Unity Catalog uses to reach
# ADLS Gen2 (configured as a UC storage credential in Phase 2). It is granted
# Storage Blob Data Contributor by the rbac module.

resource "azurerm_databricks_workspace" "this" {
  name                        = var.workspace_name
  resource_group_name         = var.resource_group_name
  location                    = var.location
  sku                         = "premium"
  managed_resource_group_name = var.managed_rg_name

  tags = var.tags
}

resource "azurerm_databricks_access_connector" "this" {
  name                = var.access_connector_name
  resource_group_name = var.resource_group_name
  location            = var.location

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}
