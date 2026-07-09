# Azure Data Factory with a system-assigned managed identity.
#
# Git integration is NOT configured here: linking to GitHub requires an
# interactive OAuth authorization that can't be done through Terraform. We wire
# it up once in ADF Studio in Phase 4 (documented as a manual step).

resource "azurerm_data_factory" "this" {
  name                = var.factory_name
  resource_group_name = var.resource_group_name
  location            = var.location

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}
