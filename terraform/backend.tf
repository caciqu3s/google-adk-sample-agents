
terraform {
  backend "gcs" {
    bucket = "poc-ai-agents-tfstate-bucket"
    prefix = "terraform/state"
  }
}