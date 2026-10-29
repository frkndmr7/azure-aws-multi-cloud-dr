include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_repo_root()}/infra/modules/azure-cosmos"
}

inputs = {
  project_name    = "multicloud-dr"
  environment     = "dev"
  location        = "westeurope"
  cosmos_location = "swedencentral"
  # Set COSMOS_ACCOUNT_NAME to a globally unique account name before deployment.
  cosmos_account_name   = get_env("COSMOS_ACCOUNT_NAME", "")
  cosmos_database_name  = "urlshortener"
  cosmos_container_name = "urls"
  free_tier_enabled     = true
  container_throughput  = 400
}
