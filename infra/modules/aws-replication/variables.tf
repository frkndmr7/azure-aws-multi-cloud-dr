variable "aws_region" { type = string }
variable "aws_account_id" { type = string }
variable "table_arn" { type = string }
variable "table_name" { type = string }
variable "lambda_zip_path" {
  type = string
  validation {
    condition     = startswith(var.lambda_zip_path, "/") && fileexists(var.lambda_zip_path)
    error_message = "Provide an existing absolute consumer ZIP path."
  }
}
