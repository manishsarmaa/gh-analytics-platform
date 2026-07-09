variable "storage_account_id" {
  type = string
}

variable "key_vault_id" {
  type = string
}

variable "adf_principal_id" {
  type = string
}

variable "databricks_connector_principal_id" {
  type = string
}

variable "current_user_object_id" {
  type = string
}

variable "azure_databricks_sp_object_id" {
  description = <<-EOT
    Object ID of the first-party 'AzureDatabricks' service principal. Granted
    read access to Key Vault so a KV-backed secret scope can resolve secrets.
    Leave empty to skip. Obtain with:
      az ad sp show --id 2ff814a6-3304-4ab8-85cb-cd0e6f879c1d --query id -o tsv
  EOT
  type        = string
  default     = ""
}
