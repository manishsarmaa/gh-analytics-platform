variable "namespace_name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "sku" {
  type    = string
  default = "Basic"
}

variable "hub_name" {
  type    = string
  default = "gh-events"
}

variable "partition_count" {
  type    = number
  default = 2
}

variable "message_retention" {
  description = "Retention in days (forced to 1 on Basic SKU)."
  type        = number
  default     = 1
}

variable "consumer_group" {
  description = "Custom consumer group (only created on Standard+)."
  type        = string
  default     = "streaming"
}

variable "tags" {
  type    = map(string)
  default = {}
}
