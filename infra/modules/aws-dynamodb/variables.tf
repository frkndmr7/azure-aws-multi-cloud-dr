variable "aws_region" {
  description = "AWS region for the DynamoDB table."
  type        = string
}

variable "aws_account_id" {
  description = "Expected AWS account ID; prevents operations in a different account."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id must be a 12-digit AWS account ID."
  }
}

variable "table_name" {
  description = "Name of the DynamoDB table."
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z0-9_.-]{3,255}$", var.table_name))
    error_message = "table_name must be 3-255 letters, digits, dots, underscores or hyphens."
  }
}
