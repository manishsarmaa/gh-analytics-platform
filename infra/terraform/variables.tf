variable "subscription_id" {
  description = "Azure subscription ID to deploy into."
  type        = string
}

variable "env" {
  description = "Environment name (dev/prod). Drives resource names."
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env must be 'dev' or 'prod'."
  }
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "centralindia"
}

variable "prefix" {
  description = "Global naming prefix for resources."
  type        = string
  default     = "ghanalytics"
}

variable "name_suffix" {
  description = "Suffix appended to globally-unique resource names. Leave empty to auto-generate a random 5-char suffix."
  type        = string
  default     = ""
}

variable "notification_email" {
  description = "Email for ADF failure alerts (used later by pipelines)."
  type        = string
}

variable "eventhub_sku" {
  description = "Event Hubs namespace SKU. Basic is cheapest; Standard adds custom consumer groups + capture."
  type        = string
  default     = "Basic"
  validation {
    condition     = contains(["Basic", "Standard"], var.eventhub_sku)
    error_message = "eventhub_sku must be 'Basic' or 'Standard'."
  }
}

variable "eventhub_partition_count" {
  description = "Partitions for the gh-events hub."
  type        = number
  default     = 2
}

variable "landing_retention_days" {
  description = "Delete landing-zone blobs older than this many days (lifecycle policy)."
  type        = number
  default     = 90
}

variable "tags" {
  description = "Extra tags merged onto every resource."
  type        = map(string)
  default     = {}
}
