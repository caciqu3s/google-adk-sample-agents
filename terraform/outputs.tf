output "github_actions_service_account_email" {
  description = "The email address of the service account created for GitHub Actions."
  value       = google_service_account.github_actions_sa.email
}

output "workload_identity_provider_name" {
  description = "The full name of the Workload Identity Provider for GitHub Actions."
  value       = google_iam_workload_identity_pool_provider.github_provider.name
} 