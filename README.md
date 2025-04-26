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

This project includes Terraform configuration to deploy the agents as a service on Google Cloud Platform (GCP), likely using Cloud Run.

**Prerequisites:**

1.  **Terraform:** Install Terraform (https://developer.hashicorp.com/terraform/install).
2.  **Google Cloud SDK (`gcloud`):** Install the gcloud CLI (https://cloud.google.com/sdk/docs/install) and authenticate:
    ```bash
    gcloud auth login
    gcloud auth application-default login
    ```
3.  **GCP Project:** Have a GCP project created with billing enabled. Ensure the necessary APIs are enabled (e.g., Cloud Run API, Cloud Build API, Artifact Registry API, Secret Manager API). You might need to enable them manually or Terraform might prompt you.
4.  **Permissions:** Ensure the authenticated user or service account has sufficient permissions (e.g., Cloud Run Admin, Secret Manager Admin, Artifact Registry Admin, Service Account User) in the target GCP project.

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
    *   Create a `terraform.tfvars` file in the `terraform` directory.
    *   Define the required variables in this file. Essential variables typically include:
        ```hcl
        project_id = "your-gcp-project-id"
        region     = "your-gcp-region"  # e.g., "us-central1"
        
        # You might need other variables depending on the specific Terraform configuration.
        # Check terraform/variables.tf for a complete list.
        ```
    *   **Important:** Do not commit `terraform.tfvars` to version control if it contains sensitive information. Add it to your `.gitignore` if not already present.

4.  **Plan the Deployment:**
    ```bash
    terraform plan -var-file="terraform.tfvars"
    ```
    Review the plan to see the resources Terraform will create.

5.  **Apply the Deployment:**
    ```bash
    terraform apply -var-file="terraform.tfvars"
    ```
    Type `yes` when prompted to confirm.

6.  **Access the Service:** Terraform will output the URL of the deployed Cloud Run service upon successful completion.

**Destroying Infrastructure:**

To remove the deployed resources from GCP:

```bash
terraform destroy -var-file="terraform.tfvars"
```
Type `yes` when prompted to confirm. 