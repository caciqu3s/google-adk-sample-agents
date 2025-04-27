variable "project_id" {
  description = "The GCP project ID to deploy resources into."
  type        = string
}

variable "region" {
  description = "The GCP region to deploy resources into."
  type        = string
}

variable "billing_account" {
  description = "The GCP billing account ID associated with the project."
  type        = string
}

variable "org_id" {
  description = "The GCP organization ID. Required if creating the project within an organization."
  type        = string
  default     = null # Make it optional if project already exists or is not in an org
}

variable "github_repo" {
  description = "Your GitHub repository in the format \"owner/repo-name\"."
  type        = string
  # Example: "my-github-username/agent-demo"
}

variable "github_actions_sa_id" {
  description = "The desired ID for the GitHub Actions service account (e.g., \"github-actions-deployer\")."
  type        = string
  default     = "github-actions-deployer"
}

variable "github_actions_sa_display_name" {
  description = "The display name for the GitHub Actions service account."
  type        = string
  default     = "GitHub Actions Deployer SA"
}