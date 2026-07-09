output "id" {
  value = azurerm_data_factory.this.id
}

output "name" {
  value = azurerm_data_factory.this.name
}

output "identity_principal_id" {
  value = azurerm_data_factory.this.identity[0].principal_id
}
