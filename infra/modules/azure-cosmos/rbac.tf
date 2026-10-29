resource "azurerm_cosmosdb_sql_role_definition" "url_writer" {
  name                = "URL Shortener Data Writer"
  role_definition_id  = "64acc96d-9604-43c7-ae7a-aae0a97b0d78"
  type                = "CustomRole"
  resource_group_name = azurerm_resource_group.this.name
  account_name        = azurerm_cosmosdb_account.this.name
  assignable_scopes   = [azurerm_cosmosdb_account.this.id]

  permissions {
    data_actions = [
      "Microsoft.DocumentDB/databaseAccounts/readMetadata",
      "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/read",
      "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/create",
    ]
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_cosmosdb_sql_role_assignment" "local_developer" {
  name                = "69030702-3198-45d0-b74a-5f9d8c814142"
  resource_group_name = azurerm_resource_group.this.name
  account_name        = azurerm_cosmosdb_account.this.name
  role_definition_id  = azurerm_cosmosdb_sql_role_definition.url_writer.id
  principal_id        = var.local_developer_principal_id
  scope               = "${azurerm_cosmosdb_account.this.id}/dbs/${azurerm_cosmosdb_sql_database.this.name}/colls/${azurerm_cosmosdb_sql_container.this.name}"

  lifecycle {
    prevent_destroy = true
  }
}
