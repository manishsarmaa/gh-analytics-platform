provider "azurerm" {
  subscription_id = var.subscription_id

  features {
    key_vault {
      # Trial-friendly: allow full cleanup when destroying.
      purge_soft_delete_on_destroy    = true
      recover_soft_deleted_key_vaults = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}
