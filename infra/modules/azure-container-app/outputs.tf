output "container_app_fqdn" {
  description = "Container App ingress FQDN, subject to IP allow rules."
  value       = try(azurerm_container_app.this.ingress[0].fqdn, null)
}

output "managed_identity_principal_id" {
  description = "System-assigned Container App identity principal ID."
  value       = azurerm_container_app.this.identity[0].principal_id
}
