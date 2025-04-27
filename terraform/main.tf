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

resource "google_project_service" "cloudbilling" {
  project = google_project.agents_project.project_id
  service = "cloudbilling.googleapis.com"

  # Depend on core services being enabled
  depends_on = [google_project_service.service_usage, google_project_service.resource_manager]
  disable_on_destroy = false # Keep enabled unless project is destroyed
}

resource "google_project_service" "networkmanagement" {
  project = google_project.agents_project.project_id
  service = "networkmanagement.googleapis.com"

  # Depend on core services being enabled
  depends_on = [google_project_service.service_usage, google_project_service.resource_manager]
  disable_on_destroy = false # Keep enabled unless project is destroyed
}

# --- AI/ML APIs ---

resource "google_project_service" "vertex_ai" {
  project = google_project.agents_project.project_id
  service = "aiplatform.googleapis.com"

  depends_on = [google_project_service.service_usage, google_project_service.resource_manager]
  disable_on_destroy = false
}

resource "google_project_service" "generative_language" {
  project = google_project.agents_project.project_id
  service = "generativelanguage.googleapis.com"

  depends_on = [google_project_service.service_usage, google_project_service.resource_manager]
  disable_on_destroy = false
}

resource "google_project_service" "run_api" {
  project = google_project.agents_project.project_id
  service = "run.googleapis.com"

  depends_on = [google_project_service.service_usage, google_project_service.resource_manager]
  disable_on_destroy = false
}

resource "google_project_service" "artifact_registry" {
  project = google_project.agents_project.project_id
  service = "artifactregistry.googleapis.com"

  depends_on = [google_project_service.service_usage, google_project_service.resource_manager]
  disable_on_destroy = false
}

resource "google_project_service" "cloud_build" {
  project = google_project.agents_project.project_id
  service = "cloudbuild.googleapis.com" # gcloud run deploy --source uses Cloud Build

  depends_on = [google_project_service.service_usage, google_project_service.resource_manager]
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

resource "random_password" "agent_db_password" {
  length           = 16
  special          = true
  override_special = "_%@"
}

resource "google_secret_manager_secret" "agent_db_password_secret" {
  project   = google_project.agents_project.project_id
  secret_id = "agent-db-password"

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "agent_db_password_secret_version" {
  secret      = google_secret_manager_secret.agent_db_password_secret.id
  secret_data = random_password.agent_db_password.result

  depends_on = [google_secret_manager_secret.agent_db_password_secret]
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
      ssl_mode     = "ENCRYPTED_ONLY"
      # Consider using private IP for production:
      # private_network = google_compute_network.private_network.id
      authorized_networks {
        value = "189.29.149.20/32"
        name  = "local-dev-ip"
      }
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

# --- Agent SQL User ---

resource "google_sql_user" "agent_db_user" {
  project  = google_project.agents_project.project_id
  instance = google_sql_database_instance.main_instance.name
  name     = "agent_user" # Or your desired username
  password = random_password.agent_db_password.result

  # Depends on the instance existing and the password being generated/stored
  depends_on = [
    google_sql_database_instance.main_instance,
    google_secret_manager_secret_version.agent_db_password_secret_version
  ]
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
    "roles/artifactregistry.repoAdmin",  # Create Artifact Registry repos (needed for gcloud run deploy --source)
    "roles/cloudbuild.builds.editor",    # ADK deploy often uses Cloud Build (gcloud run deploy --source uses it too)
    "roles/secretmanager.admin",         # Manage secrets (TF + potentially ADK)
    "roles/storage.admin",               # Manage GCS buckets (TF state, potentially others)
    # "roles/sqladmin.admin",           # Removed: Not needed for SA, TF handles SQL admin
    "roles/serviceusage.serviceUsageAdmin", # Enable APIs (TF)
    "roles/iam.workloadIdentityPoolViewer", # Allow SA to read WIF pool state for Terraform refresh
    "roles/iam.securityReviewer",          # Allow SA to read IAM policies (e.g., its own) for Terraform refresh
    "roles/cloudsql.viewer"              # Allow SA to read Cloud SQL instance state for Terraform refresh
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
    google_project_service.run_api,
    google_project_service.artifact_registry,
    google_project_service.cloud_build
  ]
}

# --- Grant Project IAM Admin Role to SA ---
# This is necessary for the SA to manage its own roles via Terraform
resource "google_project_iam_member" "github_actions_sa_project_iam_admin" {
  project = google_project.agents_project.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.github_actions_sa.email}"

  depends_on = [
    google_service_account.github_actions_sa,
    google_project_service.resource_manager # Ensure Resource Manager API is enabled
  ]
}

# Grant Billing Viewer role ON THE BILLING ACCOUNT
resource "google_billing_account_iam_member" "github_actions_sa_billing_viewer" {
  billing_account_id = var.billing_account
  role               = "roles/billing.viewer"
  member             = "serviceAccount:${google_service_account.github_actions_sa.email}"

  # Depends on the SA existing
  depends_on = [google_service_account.github_actions_sa]
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

# --- Cloud SQL Managed Client SSL Certificates ---

# Create a Cloud SQL managed SSL certificate for db_user
resource "google_sql_ssl_cert" "db_user_cert" {
  project     = google_project.agents_project.project_id
  instance    = google_sql_database_instance.main_instance.name
  common_name = "db_user" # Can be any identifier, often match user

  depends_on = [google_sql_database_instance.main_instance]
}

# Create a Cloud SQL managed SSL certificate for agent_user
resource "google_sql_ssl_cert" "agent_user_cert" {
  project     = google_project.agents_project.project_id
  instance    = google_sql_database_instance.main_instance.name
  common_name = "agent_user" # Can be any identifier, often match user

  depends_on = [google_sql_database_instance.main_instance]
}

# --- Store Cloud SQL Managed SSL Certificates in Secret Manager ---

# Secret for the Server CA Certificate (Provided by Cloud SQL)
resource "google_secret_manager_secret" "sql_server_ca_cert" {
  project   = google_project.agents_project.project_id
  secret_id = "sql-server-ca-cert" # Keep the same name for consistency

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "sql_server_ca_cert_version" {
  secret      = google_secret_manager_secret.sql_server_ca_cert.id
  # Use the server_ca_cert output from one of the certs (it's the same for the instance)
  secret_data = google_sql_ssl_cert.agent_user_cert.server_ca_cert
  depends_on  = [google_sql_ssl_cert.agent_user_cert] # Depends on cert creation
}

# --- Secrets for db_user (Cloud SQL Managed Cert) ---

# Secret for db_user Client Certificate
resource "google_secret_manager_secret" "sql_client_cert_db_user" {
  project   = google_project.agents_project.project_id
  secret_id = "sql-client-cert-db-user" # Keep the same name

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "sql_client_cert_db_user_version" {
  secret      = google_secret_manager_secret.sql_client_cert_db_user.id
  secret_data = google_sql_ssl_cert.db_user_cert.cert
  depends_on  = [google_sql_ssl_cert.db_user_cert]
}

# Secret for db_user Client Private Key
resource "google_secret_manager_secret" "sql_client_key_db_user" {
  project   = google_project.agents_project.project_id
  secret_id = "sql-client-key-db-user" # Keep the same name

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "sql_client_key_db_user_version" {
  secret      = google_secret_manager_secret.sql_client_key_db_user.id
  secret_data = google_sql_ssl_cert.db_user_cert.private_key
  depends_on  = [google_sql_ssl_cert.db_user_cert]
}

# --- Secrets for agent_user (Cloud SQL Managed Cert) ---

# Secret for agent_user Client Certificate
resource "google_secret_manager_secret" "sql_client_cert_agent_user" {
  project   = google_project.agents_project.project_id
  secret_id = "sql-client-cert-agent-user" # Keep the same name

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "sql_client_cert_agent_user_version" {
  secret      = google_secret_manager_secret.sql_client_cert_agent_user.id
  secret_data = google_sql_ssl_cert.agent_user_cert.cert
  depends_on  = [google_sql_ssl_cert.agent_user_cert]
}

# Secret for agent_user Client Private Key
resource "google_secret_manager_secret" "sql_client_key_agent_user" {
  project   = google_project.agents_project.project_id
  secret_id = "sql-client-key-agent-user" # Keep the same name

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "sql_client_key_agent_user_version" {
  secret      = google_secret_manager_secret.sql_client_key_agent_user.id
  secret_data = google_sql_ssl_cert.agent_user_cert.private_key
  depends_on  = [google_sql_ssl_cert.agent_user_cert]
}

# --- End of Cloud SQL SSL/Secret Manager Additions ---