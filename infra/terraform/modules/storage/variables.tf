variable "storage_account_name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "containers" {
  description = "Container names to create."
  type        = list(string)
}

variable "landing_container" {
  description = "Container the lifecycle expiry rule targets."
  type        = string
  default     = "landing"
}

variable "landing_retention_days" {
  type    = number
  default = 90
}

variable "tags" {
  type    = map(string)
  default = {}
}
