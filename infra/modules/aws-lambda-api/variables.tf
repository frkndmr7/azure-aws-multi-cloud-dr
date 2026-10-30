variable "aws_region" {
  type = string
}
variable "aws_account_id" {
  type = string
}
variable "table_name" {
  type = string
}
variable "table_arn" {
  type = string
}
variable "lambda_zip_path" {
  description = "Absolute path to a real Python 3.12 Linux x86_64 Lambda ZIP."
  type        = string
  validation {
    condition     = startswith(var.lambda_zip_path, "/") && fileexists(var.lambda_zip_path)
    error_message = "Set LAMBDA_ZIP_PATH to an existing absolute Lambda ZIP path."
  }
}
