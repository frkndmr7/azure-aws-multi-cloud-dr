variable "resource_group_name" { type = string }
variable "location" { type = string }
variable "cosmos_account_name" { type = string }
variable "cosmos_database_name" { type = string }
variable "cosmos_container_name" { type = string }
variable "cosmos_endpoint" { type = string }
variable "function_app_name" {
  type = string
  validation {
    condition     = length(trimspace(var.function_app_name)) > 0
    error_message = "Provide an approved globally unique Function App name."
  }
}
variable "storage_account_name" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.storage_account_name))
    error_message = "Provide an approved globally unique Storage account name."
  }
}
