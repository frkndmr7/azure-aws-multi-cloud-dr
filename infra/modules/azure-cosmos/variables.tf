variable "project_name" {
  description = "Short project name used in the resource group name."
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,39}$", var.project_name))
    error_message = "project_name must contain 1-40 lowercase letters, digits or hyphens and start with a letter or digit."
  }
}

variable "environment" {
  description = "Environment name used in the resource group name."
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,19}$", var.environment))
    error_message = "environment must contain 1-20 lowercase letters, digits or hyphens and start with a letter or digit."
  }
}

variable "location" {
  description = "Azure region of the resource group."
  type        = string
  default     = "westeurope"
}

variable "cosmos_location" {
  description = "Single Azure region for the Cosmos DB account."
  type        = string
  default     = "westeurope"
}

variable "cosmos_account_name" {
  description = "Globally unique Cosmos DB account name."
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,42}[a-z0-9]$", var.cosmos_account_name))
    error_message = "cosmos_account_name must be 3-44 lowercase letters, digits or hyphens, starting and ending with a letter or digit."
  }
}

variable "cosmos_database_name" {
  description = "Cosmos DB SQL database name."
  type        = string
  default     = "urlshortener"
  validation {
    condition     = length(var.cosmos_database_name) > 0 && length(var.cosmos_database_name) <= 255 && !can(regex("[/\\\\#?]|[ .]$", var.cosmos_database_name))
    error_message = "cosmos_database_name must be 1-255 characters, exclude /, backslash, # and ?, and not end in a space or dot."
  }
}

variable "cosmos_container_name" {
  description = "Cosmos DB SQL container name."
  type        = string
  default     = "urls"
  validation {
    condition     = length(var.cosmos_container_name) > 0 && length(var.cosmos_container_name) <= 255 && !can(regex("[/\\\\#?]|[ .]$", var.cosmos_container_name))
    error_message = "cosmos_container_name must be 1-255 characters, exclude /, backslash, # and ?, and not end in a space or dot."
  }
}

variable "free_tier_enabled" {
  description = "Request the Cosmos DB Free Tier discount when eligible."
  type        = bool
  default     = true
}

variable "container_throughput" {
  description = "Dedicated provisioned container throughput in RU/s (not serverless)."
  type        = number
  default     = 400
  validation {
    condition     = var.container_throughput >= 400 && var.container_throughput % 100 == 0
    error_message = "container_throughput must be at least 400 RU/s and a multiple of 100."
  }
}
