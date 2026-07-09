output "role_assignment_ids" {
  value = [
    azurerm_role_assignment.adf_storage.id,
    azurerm_role_assignment.adf_keyvault.id,
    azurerm_role_assignment.databricks_storage.id,
    azurerm_role_assignment.user_keyvault.id,
    azurerm_role_assignment.user_storage.id,
  ]
}
