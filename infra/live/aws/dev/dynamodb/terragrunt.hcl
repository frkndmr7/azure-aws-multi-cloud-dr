include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_repo_root()}/infra/modules/aws-dynamodb"
}

inputs = {
  aws_region     = "eu-west-1"
  aws_account_id = "109678733855"
  table_name     = "mcdr-dev-urls"
}
