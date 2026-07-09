variable "workspace_name" {
  type = string
}

variable "access_connector_name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "managed_rg_name" {
  description = "Name for the Databricks-managed resource group."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
