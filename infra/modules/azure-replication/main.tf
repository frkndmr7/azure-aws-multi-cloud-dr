data "azurerm_client_config" "current" {}

locals {
  account_id   = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/${var.resource_group_name}/providers/Microsoft.DocumentDB/databaseAccounts/${var.cosmos_account_name}"
  db_scope     = "${local.account_id}/dbs/${var.cosmos_database_name}"
  source_scope = "${local.db_scope}/colls/${var.cosmos_container_name}"
}

resource "azurerm_cosmosdb_sql_container" "outbox" {
  name                = "replication-outbox"
  resource_group_name = var.resource_group_name
  account_name        = var.cosmos_account_name
  database_name       = var.cosmos_database_name
  partition_key_paths = ["/id"]
  throughput          = 400
  lifecycle { prevent_destroy = true }
}
resource "azurerm_user_assigned_identity" "worker" {
  name                = "id-mcdr-replication-dev"
  resource_group_name = var.resource_group_name
  location            = var.location
}
resource "azurerm_cosmosdb_sql_role_definition" "reader" {
  name                = "Replication Change Feed Reader"
  resource_group_name = var.resource_group_name
  account_name        = var.cosmos_account_name
  type                = "CustomRole"
  assignable_scopes   = [local.account_id]
  permissions {
    data_actions = ["Microsoft.DocumentDB/databaseAccounts/readMetadata", "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/readChangeFeed"]
  }
}
resource "azurerm_cosmosdb_sql_role_definition" "store" {
  name                = "Replication Outbox Store"
  resource_group_name = var.resource_group_name
  account_name        = var.cosmos_account_name
  type                = "CustomRole"
  assignable_scopes   = [local.account_id]
  permissions {
    data_actions = ["Microsoft.DocumentDB/databaseAccounts/readMetadata", "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/executeQuery", "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/readChangeFeed", "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/read", "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/create", "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/replace"]
  }
}
resource "azurerm_cosmosdb_sql_role_assignment" "reader" {
  resource_group_name = var.resource_group_name
  account_name        = var.cosmos_account_name
  role_definition_id  = azurerm_cosmosdb_sql_role_definition.reader.id
  principal_id        = azurerm_user_assigned_identity.worker.principal_id
  scope               = local.source_scope
}
resource "azurerm_cosmosdb_sql_role_assignment" "outbox" {
  resource_group_name = var.resource_group_name
  account_name        = var.cosmos_account_name
  role_definition_id  = azurerm_cosmosdb_sql_role_definition.store.id
  principal_id        = azurerm_user_assigned_identity.worker.principal_id
  scope               = "${local.db_scope}/colls/${azurerm_cosmosdb_sql_container.outbox.name}"
}
resource "azurerm_storage_account" "host" {
  name                            = var.storage_account_name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
}
resource "azurerm_role_assignment" "host_blob" {
  scope                = azurerm_storage_account.host.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_user_assigned_identity.worker.principal_id
}
resource "azurerm_service_plan" "worker" {
  name                = "asp-mcdr-replication-dev"
  resource_group_name = var.resource_group_name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "Y1"
}
resource "azurerm_linux_function_app" "worker" {
  name                          = var.function_app_name
  resource_group_name           = var.resource_group_name
  location                      = var.location
  service_plan_id               = azurerm_service_plan.worker.id
  storage_account_name          = azurerm_storage_account.host.name
  storage_uses_managed_identity = true
  enabled                       = false
  public_network_access_enabled = false
  https_only                    = true
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.worker.id]
  }
  site_config {
    application_stack { python_version = "3.12" }
  }
  app_settings = {
    AzureWebJobsStorage__clientId = azurerm_user_assigned_identity.worker.client_id
    COSMOS_ENDPOINT               = var.cosmos_endpoint
    COSMOS_DATABASE               = var.cosmos_database_name
    COSMOS_SOURCE_CONTAINER       = var.cosmos_container_name
    COSMOS_OUTBOX_CONTAINER       = azurerm_cosmosdb_sql_container.outbox.name
    COSMOS_CHECKPOINT_CONTAINER   = azurerm_cosmosdb_sql_container.outbox.name
    DISPATCHER_ENABLED            = "false"
    PRODUCER_ENABLED              = "false"
    AZURE_CLIENT_ID               = azurerm_user_assigned_identity.worker.client_id
  }
  depends_on = [azurerm_role_assignment.host_blob, azurerm_cosmosdb_sql_role_assignment.reader, azurerm_cosmosdb_sql_role_assignment.outbox]
}
