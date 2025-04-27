# Google ADK Sample Agents Collection

This repository contains a collection of sample agents built using Google's Agent Development Kit (ADK). Each agent demonstrates different capabilities and integrations.

## Available Agents

*   **Weather & Time Agent (`weather_agent`)**: Provides current weather and time information for a given city using Google Maps APIs.
*   **Vegas Agent (`vegas_agent`)**: Demonstrates interactions related to Las Vegas, potentially including searching for events, places, or other location-based information (likely using Google Maps and possibly other APIs like Ticketmaster).

## Setup

1.  **Install Poetry** (if you haven't already):
    *   Follow the official installation guide: https://python-poetry.org/docs/#installation
    *   Alternatively, use pipx: `pipx install poetry`
    *   Or pip (not recommended for isolation): `pip install poetry`

2.  **Set up the Project Environment & Install Dependencies**:
    *   Navigate to the project directory in your terminal.
    *   Run `poetry install`. This command will create a virtual environment if one doesn't exist and install all the project dependencies listed in `pyproject.toml`.
    *   To activate the virtual environment for subsequent commands in the same shell session (optional but often convenient), run `poetry shell`.

3.  **Configure API Keys**:
    *   Copy the `.env.example` file (if it exists) or create a new file named `.env` in the project root directory.
    *   Add the necessary API keys required by the agents you intend to use. Common keys include:
        ```dotenv
        # For Gemini Models
        GOOGLE_API_KEY=YOUR_GEMINI_API_KEY
        
        # For Google Maps APIs (Geocoding, Timezone, Weather, Places)
        GOOGLE_MAPS_API_KEY=YOUR_MAPS_API_KEY
        
        # Potentially for other services like Ticketmaster (used by vegas_agent)
        # TICKETMASTER_API_KEY=YOUR_TICKETMASTER_KEY 
        ```
    *   Refer to the specific agent's code within the `agents/` directory if you are unsure which keys are needed.

## Usage

To run all agents from this collection through the ADK development UI, execute the following command from the project root directory (this uses the `run-agents` task defined in `pyproject.toml` via `poethepoet`):

```bash
poetry run poe run-agents
```

This command will start the ADK web server. Then open http://localhost:8000 in your browser. You can select and interact with the different agents from the web interface.

## Development

The ADK web interface provides a convenient way to test and debug the agents. You can:

*   Select specific agents to interact with.
*   Send test prompts.
*   View agent responses and internal thought processes.
*   Debug agent behavior.
*   Monitor agent state.

## Deployment (GCP with Terraform)

This project includes Terraform configuration to deploy necessary infrastructure and optionally the agents as services on Google Cloud Platform (GCP). Terraform is configured to create a dedicated Service Account and Workload Identity Federation pool/provider for secure authentication from the GitHub Actions CI/CD pipeline.

**Prerequisites:**

1.  **Terraform:** Install Terraform (https://developer.hashicorp.com/terraform/install).
2.  **Google Cloud SDK (`gcloud`):** Install the gcloud CLI (https://cloud.google.com/sdk/docs/install) and authenticate with user credentials that have permissions to create projects (if needed), manage IAM, enable APIs, and manage the resources defined in `terraform/main.tf` (Service Accounts, WIF, Cloud SQL, GCS, Secret Manager, etc.). This is especially important for the *initial* apply.
    ```bash
    gcloud auth login
    gcloud auth application-default login
    ```
3.  **GCP Project & Billing:** Have a GCP project ID and an associated Billing Account ID ready. Terraform can create the project if it doesn't exist, or use an existing one. **Ensure the Cloud Billing API (`cloudbilling.googleapis.com`) is enabled for your project.** You can enable it in the GCP Console under "APIs & Services".
4.  **GitHub Repository:** Know your GitHub repository name in the format `owner/repo-name`.
5.  **Permissions for Initial Apply:** The user running the *initial* `terraform apply` needs permissions not only on the project but also **on the Billing Account** (e.g., `roles/billing.admin`) to grant the necessary viewer role to the GitHub Actions service account.

**Deployment Steps:**

1.  **Navigate to the Terraform directory:**
    ```bash
    cd terraform
    ```

2.  **Initialize Terraform:**
    ```bash
    terraform init
    ```

3.  **Configure Variables:**
    *   Create a `terraform.tfvars` file in the `terraform` directory (copy from `terraform.tfvars.example` if provided, or create new).
    *   Define the required variables. Check `terraform/variables.tf` for the full list and descriptions. Key variables include:
        ```hcl
        project_id       = "your-gcp-project-id"
        region           = "your-gcp-region"        # e.g., "us-central1"
        billing_account  = "your-billing-account-id"
        org_id           = "your-organization-id"   # Optional: Only if creating project in an org
        github_repo      = "your-github-owner/your-repo-name" # For WIF binding
        
        # API Keys - Note: These are NOT directly used by Terraform yet.
        # See CI/CD setup section for handling keys.
        # google_api_key        = "YOUR_GEMINI_API_KEY"
        # google_maps_api_key = "YOUR_MAPS_API_KEY"
        # ticketmaster_api_key  = "YOUR_TICKETMASTER_KEY"
        ```
    *   **Important:** Ensure `terraform.tfvars` is in your `.gitignore`.

4.  **Plan the Deployment:**
    ```bash
    terraform plan -var-file="terraform.tfvars"
    ```
    Review the plan, especially the first time, to see the IAM roles and WIF resources being created.

5.  **Apply the Deployment (Initial & Subsequent):**
    ```bash
    terraform apply -var-file="terraform.tfvars"
    ```
    *   The **first time** you run `apply`, you must use your own authenticated gcloud user credentials. This creates the Service Account and WIF resources needed by the CI/CD pipeline.
    *   Subsequent applies can be run manually or via the CI/CD pipeline (which will use the created SA).
    *   Type `yes` when prompted to confirm.

6.  **Configure GitHub Secrets:**
    *   After the first successful `terraform apply`, get the outputs:
        ```bash
        terraform output
        ```
    *   Create/Update the following secrets in your GitHub repository (`Settings` > `Secrets and variables` > `Actions`):
        *   `GCP_PROJECT_ID`: Set to your `project_id`.
        *   `GCP_REGION`: Set to your `region`.
        *   `GCP_SA_EMAIL`: Use the value from the `github_actions_service_account_email` Terraform output.
        *   `WIF_PROVIDER`: Use the value from the `workload_identity_provider_name` Terraform output.
        *   `TF_VAR_project_id`, `TF_VAR_region`, `TF_VAR_billing_account`, `TF_VAR_org_id`: Set these to match your `terraform.tfvars` values (needed by the Terraform plan/apply steps in the workflow).
        *   `GOOGLE_API_KEY`, `GOOGLE_MAPS_API_KEY`, `TICKETMASTER_API_KEY` (if needed): Add your actual API keys here. **Note:** These are used directly by the `adk deploy` step in the current CI/CD workflow. For better security, modify the Terraform code to store these in Secret Manager and update the Cloud Run service definition (either via Terraform or within the `adk deploy` step if it supports secret mounting) to use Secret Manager.

**Destroying Infrastructure:**

To remove the deployed resources from GCP:

```bash
terraform destroy -var-file="terraform.tfvars"
```
Type `yes` when prompted to confirm. 