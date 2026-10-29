include "root" {
  path = find_in_parent_folders("root.hcl")
}

dependency "cosmos" {
  config_path = "../cosmos"
}

terraform {
  source = "${get_repo_root()}/infra/modules/azure-container-app"
}

inputs = {
  resource_group_name           = dependency.cosmos.outputs.resource_group_name
  location                      = "swedencentral"
  environment_name              = "cae-mcdr-dev"
  container_app_name            = "ca-mcdr-api-dev"
  container_image               = get_env("CONTAINER_APP_IMAGE", "")
  deployment_stage              = "bootstrap"
  enable_cosmos_role_assignment = false
  enable_active_writer          = false
  allowed_ingress_cidrs         = [for cidr in split(",", get_env("CONTAINER_APP_ALLOWED_CIDRS", "")) : trimspace(cidr) if trimspace(cidr) != ""]
  cosmos_endpoint               = dependency.cosmos.outputs.cosmos_endpoint
  cosmos_account_name           = dependency.cosmos.outputs.cosmos_account_name
  cosmos_database_name          = dependency.cosmos.outputs.cosmos_database_name
  cosmos_container_name         = dependency.cosmos.outputs.cosmos_container_name
  cosmos_role_definition_id     = "/subscriptions/${get_env("ARM_SUBSCRIPTION_ID", "")}/resourceGroups/${dependency.cosmos.outputs.resource_group_name}/providers/Microsoft.DocumentDB/databaseAccounts/${dependency.cosmos.outputs.cosmos_account_name}/sqlRoleDefinitions/64acc96d-9604-43c7-ae7a-aae0a97b0d78"
}
