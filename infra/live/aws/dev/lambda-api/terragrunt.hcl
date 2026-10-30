include "root" {
  path = find_in_parent_folders("root.hcl")
}

dependency "dynamodb" {
  config_path = "../dynamodb"
}

terraform {
  source = "${get_repo_root()}/infra/modules/aws-lambda-api"
}

inputs = {
  aws_region      = "eu-west-1"
  aws_account_id  = "109678733855"
  table_name      = dependency.dynamodb.outputs.table_name
  table_arn       = dependency.dynamodb.outputs.table_arn
  lambda_zip_path = get_env("LAMBDA_ZIP_PATH", "")
}
