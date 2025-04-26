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