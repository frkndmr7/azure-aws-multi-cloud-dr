variable "resource_group_name" {
  description = "Existing resource group containing the Container Apps environment."
  type        = string
}

variable "location" {
  description = "Azure region for the Container Apps environment."
  type        = string
  default     = "swedencentral"
}

variable "environment_name" {
  description = "Container Apps environment name."
  type        = string
}

variable "container_app_name" {
  description = "Container App name."
  type        = string
}

variable "container_image" {
  description = "Existing public GHCR image reference pinned to a sha256 digest."
  type        = string
  validation {
    condition     = can(regex("^ghcr[.]io/[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$", var.container_image))
    error_message = "Provide an existing public ghcr.io image pinned to a sha256 digest."
  }
}

variable "deployment_stage" {
  description = "Deployment stage: bootstrap, cosmos_frozen or serving."
  type        = string
  default     = "bootstrap"
  validation {
    condition     = contains(["bootstrap", "cosmos_frozen", "serving"], var.deployment_stage)
    error_message = "deployment_stage must be bootstrap, cosmos_frozen or serving."
  }
}

variable "enable_cosmos_role_assignment" {
  description = "Create the identity's Cosmos assignment after bootstrap has been applied."
  type        = bool
  default     = false
}

variable "enable_active_writer" {
  description = "Explicitly enable writing in the serving stage only."
  type        = bool
  default     = false
}

variable "allowed_ingress_cidrs" {
  description = "Approved IPv4 CIDRs allowed to access every application endpoint."
  type        = list(string)
  default     = []
  validation {
    condition = alltrue([
      for cidr in var.allowed_ingress_cidrs :
      can(cidrhost(cidr, 0)) && can(regex("^[0-9]+[.][0-9]+[.][0-9]+[.][0-9]+/([8-9]|[12][0-9]|3[0-2])$", cidr))
    ])
    error_message = "Each approved IPv4 CIDR must have a prefix from /8 through /32."
  }
}

variable "cosmos_endpoint" {
  description = "Existing Cosmos DB endpoint."
  type        = string
}

variable "cosmos_account_name" {
  description = "Existing Cosmos DB account name."
  type        = string
}

variable "cosmos_database_name" {
  description = "Existing Cosmos DB SQL database name."
  type        = string
}

variable "cosmos_container_name" {
  description = "Existing Cosmos DB SQL container name."
  type        = string
}

variable "cosmos_role_definition_id" {
  description = "Full resource ID of the existing Cosmos DB data-plane role definition."
  type        = string
}
