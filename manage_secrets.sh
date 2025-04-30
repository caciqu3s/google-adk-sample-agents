#!/bin/bash

# --- Configuration ---
# Default deploy.json file path (can be overridden by the first argument)
DEFAULT_DEPLOY_JSON="agents/deploy.json"

# --- Helper Functions ---
print_usage() {
  echo "Usage: $0 [path_to_deploy_json]"
  echo "  [path_to_deploy_json]: Optional path to the deploy.json file (defaults to './agents/deploy.json')."
  echo
  echo "This script reads secret definitions from the specified deploy.json file,"
  echo "fetches the corresponding secret values from Google Cloud Secret Manager"
  echo "using the currently configured gcloud project, and outputs 'export' commands."
  echo "To use, run: source <(./manage_secrets.sh)"
}

# --- Argument Parsing ---
# Project ID is now determined automatically
DEPLOY_JSON_FILE="${1:-$DEFAULT_DEPLOY_JSON}" # deploy.json path is now the first optional arg

# --- Pre-checks ---
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud command not found. Please install the Google Cloud SDK." >&2
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "Error: jq command not found. Please install jq (e.g., 'brew install jq' or 'sudo apt-get install jq')." >&2
    exit 1
fi

# Get current gcloud project config
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [[ -z "$PROJECT_ID" ]]; then
  echo "Error: No active GCP project configured in gcloud." >&2
  echo "Please run 'gcloud config set project YOUR_PROJECT_ID'" >&2
  exit 1
fi

if [[ ! -f "$DEPLOY_JSON_FILE" ]]; then
  echo "Error: Deployment config file not found at '$DEPLOY_JSON_FILE'" >&2
  exit 1
fi

echo "# Starting Secret Fetch for Local Environment" >&2
echo "# Auto-detected Project ID: $PROJECT_ID" >&2
echo "# Using deploy.json: $DEPLOY_JSON_FILE" >&2
echo "# Run 'source <(./manage_secrets.sh)' to load secrets." >&2
echo >&2 # Add a newline to stderr for separation

# --- Main Logic ---
processed_count=0
error_count=0

# Read the env_vars array using jq
env_vars_json=$(jq -c '.env_vars // []' "$DEPLOY_JSON_FILE")

# Check if jq succeeded and env_vars_json is not empty/null
if [ -z "$env_vars_json" ] || [ "$env_vars_json" = "null" ] || [ "$env_vars_json" = "[]" ]; then
  echo "Warning: No 'env_vars' array found or array is empty in '$DEPLOY_JSON_FILE'." >&2
  exit 0 # Exit successfully as there's nothing to process
fi

# Use Process Substitution to feed the while loop, avoiding a subshell
while IFS= read -r item_json; do
  # Check if the item defines a secret
  if [[ $(echo "$item_json" | jq 'has("secret")') == "true" ]]; then
    var_name=$(echo "$item_json" | jq -r '.name // ""')
    secret_id=$(echo "$item_json" | jq -r '.secret // ""')
    secret_version=$(echo "$item_json" | jq -r '.version // "latest"')

    if [[ -z "$var_name" ]] || [[ -z "$secret_id" ]]; then
      echo "Warning: Skipping secret entry with missing name or secret ID in '$DEPLOY_JSON_FILE': $item_json" >&2
      continue
    fi

    echo "# Fetching secret for variable: $var_name (Secret ID: $secret_id, Version: $secret_version)" >&2

    # Construct full secret resource name
    secret_resource_name="projects/$PROJECT_ID/secrets/$secret_id/versions/$secret_version"

    # Fetch the secret value
    secret_value=$(gcloud secrets versions access "$secret_resource_name" --project="$PROJECT_ID" --quiet 2> /dev/null)

    # Check gcloud exit status
    if [[ $? -ne 0 ]]; then
      echo "Error: Failed to fetch secret '$secret_resource_name'. Check permissions or if the secret/version exists." >&2
      ((error_count++))
      continue # Skip this secret
    else
      # Output the export command
      # Use printf for safer handling of potentially complex secret values
      printf "export %s=%q\n" "$var_name" "$secret_value"
      ((processed_count++))
    fi
  fi
done < <(echo "$env_vars_json" | jq -c '.[]') # Feed the loop using Process Substitution

# --- Summary ---
echo >&2 # Add a newline to stderr
echo "# Secret Fetch Complete" >&2
echo "#   Variables to be exported: $processed_count" >&2
echo "#   Errors encountered: $error_count" >&2

# Exit with error code if any errors occurred
if [[ $error_count -gt 0 ]]; then
  exit 1
else
  exit 0
fi 