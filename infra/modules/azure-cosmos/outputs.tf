output "resource_group_name" {
  description = "Azure resource group name."
  value       = azurerm_resource_group.this.name
}

output "cosmos_account_name" {
  description = "Cosmos DB account name."
  value       = azurerm_cosmosdb_account.this.name
}

output "cosmos_endpoint" {
  description = "Cosmos DB endpoint for COSMOS_ENDPOINT."
  value       = azurerm_cosmosdb_account.this.endpoint
}

output "cosmos_database_name" {
  description = "SQL database name for COSMOS_DATABASE."
  value       = azurerm_cosmosdb_sql_database.this.name
}

output "cosmos_container_name" {
  description = "SQL container name for COSMOS_CONTAINER."
  value       = azurerm_cosmosdb_sql_container.this.name
}
