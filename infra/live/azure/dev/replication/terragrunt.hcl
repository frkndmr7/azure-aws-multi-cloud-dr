include "root" {
  path = find_in_parent_folders("root.hcl")
}
dependency "cosmos" {
  config_path = "../cosmos"
}
terraform {
  source = "${get_repo_root()}/infra/modules/azure-replication"
}
inputs = {
  resource_group_name   = dependency.cosmos.outputs.resource_group_name
  location              = "swedencentral"
  cosmos_account_name   = dependency.cosmos.outputs.cosmos_account_name
  cosmos_database_name  = dependency.cosmos.outputs.cosmos_database_name
  cosmos_container_name = dependency.cosmos.outputs.cosmos_container_name
  cosmos_endpoint       = dependency.cosmos.outputs.cosmos_endpoint
  function_app_name     = get_env("REPLICATION_FUNCTION_NAME", "")
  storage_account_name  = get_env("REPLICATION_STORAGE_NAME", "")
}
