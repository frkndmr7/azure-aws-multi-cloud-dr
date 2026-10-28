resource "azurerm_resource_group" "this" {
  name     = "rg-${var.project_name}-${var.environment}"
  location = var.location

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_cosmosdb_account" "this" {
  name                             = var.cosmos_account_name
  location                         = azurerm_resource_group.this.location
  resource_group_name              = azurerm_resource_group.this.name
  offer_type                       = "Standard"
  kind                             = "GlobalDocumentDB"
  free_tier_enabled                = var.free_tier_enabled
  automatic_failover_enabled       = false
  multiple_write_locations_enabled = false

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.this.location
    failover_priority = 0
    zone_redundant    = false
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_cosmosdb_sql_database" "this" {
  name                = var.cosmos_database_name
  resource_group_name = azurerm_resource_group.this.name
  account_name        = azurerm_cosmosdb_account.this.name

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_cosmosdb_sql_container" "this" {
  name                = var.cosmos_container_name
  resource_group_name = azurerm_resource_group.this.name
  account_name        = azurerm_cosmosdb_account.this.name
  database_name       = azurerm_cosmosdb_sql_database.this.name
  partition_key_paths = ["/id"]
  throughput          = var.container_throughput

  lifecycle {
    prevent_destroy = true
  }
}
