data "google_billing_account" "account" {
  billing_account = var.billing_account
}

resource "google_project" "agents_project" {
  name       = "PoC AI Agents Project"
  project_id = var.project_id
  org_id     = var.org_id
  billing_account = data.google_billing_account.account.id
}

resource "google_project_service" "service_usage" {
  project = google_project.agents_project.project_id
  service = "serviceusage.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "resource_manager" {
  project = google_project.agents_project.project_id
  service = "cloudresourcemanager.googleapis.com"

  depends_on = [google_project_service.service_usage]
  disable_on_destroy = false
}

resource "google_project_service" "iam" {
  project = google_project.agents_project.project_id
  service = "iam.googleapis.com"

  depends_on = [google_project_service.resource_manager]
  disable_on_destroy = false
}

resource "google_project_service" "sqladmin" {
  project = google_project.agents_project.project_id
  service = "sqladmin.googleapis.com"

  depends_on = [google_project_service.iam]
  disable_on_destroy = false
}

resource "google_project_service" "secretmanager" {
  project = google_project.agents_project.project_id
  service = "secretmanager.googleapis.com"

  depends_on = [google_project_service.sqladmin]
  disable_on_destroy = false
}

resource "google_project_service" "storage" {
  project = google_project.agents_project.project_id
  service = "storage.googleapis.com"

  depends_on = [google_project_service.iam]
  disable_on_destroy = false
}

resource "google_storage_bucket" "tfstate_bucket" {
  project       = google_project.agents_project.project_id
  name          = "poc-ai-agents-tfstate-bucket"
  location      = var.region
  force_destroy = true
  autoclass {
    enabled = true
  }
}

resource "random_password" "db_password" {
  length           = 16
  special          = true
  override_special = "_%@"
}

resource "google_secret_manager_secret" "db_password_secret" {
  project   = google_project.agents_project.project_id
  secret_id = "db-password"

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "db_password_secret_version" {
  secret      = google_secret_manager_secret.db_password_secret.id
  secret_data = random_password.db_password.result
}

resource "google_sql_database_instance" "main_instance" {
  project          = google_project.agents_project.project_id
  name             = "main-instance"
  database_version = "POSTGRES_15"
  region           = var.region

  depends_on = [google_project_service.sqladmin]

  settings {
    tier = "db-f1-micro" # Choose an appropriate tier for your needs

    ip_configuration {
      ipv4_enabled = true
      # Consider using private IP for production:
      # private_network = google_compute_network.private_network.id
    }

    backup_configuration {
      enabled            = false
    }
  }

  deletion_protection = false # Set to true for production environments
}

resource "google_sql_database" "main_db" {
  project  = google_project.agents_project.project_id
  instance = google_sql_database_instance.main_instance.name
  name     = "main_db"
}

resource "google_sql_user" "db_user" {
  project  = google_project.agents_project.project_id
  instance = google_sql_database_instance.main_instance.name
  name     = "db_user"
  password = random_password.db_password.result
}

# --- GitHub Actions Service Account and Workload Identity Federation ---

resource "google_service_account" "github_actions_sa" {
  project      = google_project.agents_project.project_id
  account_id   = var.github_actions_sa_id
  display_name = var.github_actions_sa_display_name
  depends_on = [
    google_project_service.iam # Ensure IAM API is enabled
  ]
}

# Grant roles necessary for Terraform Apply AND ADK Deploy
# Adjust these based on the exact needs of your TF config and agents
resource "google_project_iam_member" "github_actions_sa_roles" {
  for_each = toset([
    "roles/run.admin",                   # Deploy Cloud Run services (ADK + TF if managing Run)
    "roles/iam.serviceAccountUser",      # Impersonate service accounts (itself for WIF)
    "roles/artifactregistry.writer",     # Push container images (ADK deploy)
    "roles/cloudbuild.builds.editor",    # ADK deploy often uses Cloud Build
    "roles/secretmanager.admin",         # Manage secrets (TF + potentially ADK)
    "roles/storage.admin",               # Manage GCS buckets (TF state, potentially others)
    "roles/serviceusage.serviceUsageAdmin" # Enable APIs (TF)
  ])
  project = google_project.agents_project.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_actions_sa.email}"

  depends_on = [
    google_service_account.github_actions_sa,
    # Depend on API enablement resources
    google_project_service.service_usage,
    google_project_service.resource_manager,
    google_project_service.iam,
    google_project_service.sqladmin,
    google_project_service.secretmanager,
    google_project_service.storage,
    # Add dependencies for APIs used by specific roles if needed
    # e.g., google_project_service.run, google_project_service.artifactregistry
  ]
}

# Workload Identity Federation Pool
resource "google_iam_workload_identity_pool" "github_pool" {
  project                   = google_project.agents_project.project_id
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Workload Identity Pool for GitHub Actions"
  depends_on = [
    google_project_service.iam # Ensure IAM API is enabled
  ]
}

# Workload Identity Federation Provider for GitHub
resource "google_iam_workload_identity_pool_provider" "github_provider" {
  project                                = google_project.agents_project.project_id
  workload_identity_pool_id              = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  display_name                       = "GitHub Actions Provider"
  description                        = "OIDC Provider for GitHub Actions"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  # Define OIDC configuration
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  # attribute_condition = null # Removed: Not required if no condition is needed

  depends_on = [
    google_iam_workload_identity_pool.github_pool
  ]
}

# Allow GitHub Actions from the specified repo to impersonate the Service Account
resource "google_service_account_iam_member" "github_actions_wif_binding" {
  service_account_id = google_service_account.github_actions_sa.name # Use the fully qualified name
  role               = "roles/iam.workloadIdentityUser"
  # principalSet allows targeting specific GitHub repo/branch/etc.
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_repo}" 
  # More specific targeting (e.g., only main branch):
  # member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/subject/repo:${var.github_repo}:ref:refs/heads/main" 

  depends_on = [
    google_service_account.github_actions_sa,
    google_iam_workload_identity_pool_provider.github_provider
  ]
}