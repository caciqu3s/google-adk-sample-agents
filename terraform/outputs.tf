output "github_actions_service_account_email" {
  description = "The email address of the service account created for GitHub Actions."
  value       = google_service_account.github_actions_sa.email
}

output "workload_identity_provider_name" {
  description = "The full name of the Workload Identity Provider for GitHub Actions."
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

output "agent_db_user_name" {
  description = "The username for the agent database user."
  value       = google_sql_user.agent_db_user.name
}

output "agent_db_password_secret_name" {
  description = "The name of the Secret Manager secret containing the agent DB user password."
  value       = google_secret_manager_secret.agent_db_password_secret.secret_id
}

output "agent_db_password_secret_version_name" {
  description = "The full resource name of the latest agent DB password secret version."
  value       = google_secret_manager_secret_version.agent_db_password_secret_version.id
  sensitive   = true # Mark the version name itself as potentially sensitive
} 