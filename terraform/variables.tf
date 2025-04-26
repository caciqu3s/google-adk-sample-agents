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