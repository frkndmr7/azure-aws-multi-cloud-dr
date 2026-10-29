resource "azurerm_container_app_environment" "this" {
  name                       = var.environment_name
  location                   = var.location
  resource_group_name        = var.resource_group_name
  log_analytics_workspace_id = null
  logs_destination           = null # Stream logs only; no persistent workspace.

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}

resource "azurerm_container_app" "this" {
  name                         = var.container_app_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  lifecycle {
    prevent_destroy = true

    precondition {
      condition     = var.deployment_stage == "bootstrap" || var.enable_cosmos_role_assignment
      error_message = "Cosmos stages require the managed identity role assignment to be enabled and applied beforehand."
    }
    precondition {
      condition     = var.deployment_stage == "serving" || !var.enable_active_writer
      error_message = "Active writing is allowed only in the serving stage."
    }
    precondition {
      condition     = var.deployment_stage != "serving" || length(var.allowed_ingress_cidrs) > 0
      error_message = "Serving requires at least one approved ingress CIDR."
    }
  }

  identity {
    type = "SystemAssigned"
  }

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "api"
      image  = var.container_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "REPOSITORY_BACKEND"
        value = var.deployment_stage == "bootstrap" ? "memory" : "cosmos"
      }
      env {
        name  = "COSMOS_ENDPOINT"
        value = var.cosmos_endpoint
      }
      env {
        name  = "COSMOS_DATABASE"
        value = var.cosmos_database_name
      }
      env {
        name  = "COSMOS_CONTAINER"
        value = var.cosmos_container_name
      }
      env {
        name  = "CLOUD_ROLE"
        value = "azure"
      }
      env {
        name  = "WRITER_MODE"
        value = var.enable_active_writer ? "active" : "frozen"
      }
    }
  }

  dynamic "ingress" {
    for_each = var.deployment_stage == "serving" ? [1] : []
    content {
      external_enabled           = true
      allow_insecure_connections = false
      target_port                = 8000
      transport                  = "auto"

      dynamic "ip_security_restriction" {
        for_each = toset(var.allowed_ingress_cidrs)
        content {
          name             = "allow-${substr(sha256(ip_security_restriction.value), 0, 12)}"
          action           = "Allow"
          ip_address_range = ip_security_restriction.value
        }
      }

      traffic_weight {
        latest_revision = true
        percentage      = 100
      }
    }
  }
}

resource "azurerm_cosmosdb_sql_role_assignment" "container_app" {
  count               = var.enable_cosmos_role_assignment ? 1 : 0
  resource_group_name = var.resource_group_name
  account_name        = var.cosmos_account_name
  role_definition_id  = var.cosmos_role_definition_id
  principal_id        = azurerm_container_app.this.identity[0].principal_id
  scope               = "${split("/sqlRoleDefinitions/", var.cosmos_role_definition_id)[0]}/dbs/${var.cosmos_database_name}/colls/${var.cosmos_container_name}"

  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = can(regex("/resourceGroups/${var.resource_group_name}/providers/Microsoft[.]DocumentDB/databaseAccounts/${var.cosmos_account_name}/sqlRoleDefinitions/[0-9a-fA-F-]{36}$", var.cosmos_role_definition_id))
      error_message = "Cosmos role definition must belong to the configured account and resource group."
    }
  }
}
