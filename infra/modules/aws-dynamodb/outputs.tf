output "table_name" {
  description = "DynamoDB table name."
  value       = aws_dynamodb_table.urls.name
}

output "table_arn" {
  description = "DynamoDB table ARN for narrowly scoped IAM policies."
  value       = aws_dynamodb_table.urls.arn
}
