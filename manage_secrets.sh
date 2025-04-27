#!/bin/bash

# --- Configuration ---
# Default .env file path (can be overridden by the second argument)
DEFAULT_ENV_FILE=".env"

# --- Helper Functions ---
print_usage() {
  echo "Usage: $0 <gcp_project_id> [path_to_env_file]"
  echo "  <gcp_project_id>: Your Google Cloud Project ID."
  echo "  [path_to_env_file]: Optional path to the .env file (defaults to './.env')."
  echo
  echo "This script reads key-value pairs from the specified .env file and creates"
  echo "or updates corresponding secrets in Google Cloud Secret Manager."
  echo "Variable names are converted to lowercase and underscores replaced with hyphens"
  echo "to form the Secret ID (e.g., MY_API_KEY becomes my-api-key)."
}

# --- Argument Parsing ---
if [[ -z "$1" ]]; then
  echo "Error: Google Cloud Project ID is required."
  print_usage
  exit 1
fi

PROJECT_ID="$1"
ENV_FILE="${2:-$DEFAULT_ENV_FILE}"

# --- Pre-checks ---
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud command not found. Please install the Google Cloud SDK."
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: Environment file not found at '$ENV_FILE'"
  exit 1
fi

echo "--------------------------------------------------"
echo "Starting Secret Manager Sync"
echo "Project ID: $PROJECT_ID"
echo "Using .env file: $ENV_FILE"
echo "--------------------------------------------------"
echo

# --- Main Logic ---
processed_count=0
skipped_count=0
error_count=0

# Read the .env file line by line
# Handle lines that might not end with a newline
while IFS= read -r line || [[ -n "$line" ]]; do
  # Trim leading/trailing whitespace
  trimmed_line=$(echo "$line" | xargs)

  # Skip empty lines and comments
  if [[ -z "$trimmed_line" ]] || [[ "$trimmed_line" == \#* ]]; then
    continue
  fi

  # Ensure line contains '='
  if [[ "$trimmed_line" != *"="* ]]; then
    echo "Warning: Skipping malformed line (no '=' found): $trimmed_line"
    ((skipped_count++))
    continue
  fi

  # Split KEY and VALUE (handles values potentially containing '=')
  KEY="${trimmed_line%%=*}"
  VALUE="${trimmed_line#*=}"

  # Basic validation
  if [[ -z "$KEY" ]]; then
    echo "Warning: Skipping line with empty key: $trimmed_line"
    ((skipped_count++))
    continue
  fi
  # Allow empty values, as they might be valid secrets

  # Convert KEY to a valid Secret Manager ID format
  # Rules: lowercase letters, numbers, hyphens. Max 255 chars.
  SECRET_ID=$(echo "$KEY" | tr '[:upper:]' '[:lower:]' | tr '_.' '-' | sed 's/[^a-z0-9-]//g' | cut -c1-255)

  if [[ -z "$SECRET_ID" ]]; then
      echo "Warning: Could not generate a valid Secret ID from key '$KEY'. Skipping."
      ((skipped_count++))
      continue
  fi

  echo "Processing: Variable '$KEY' => Secret ID '$SECRET_ID'"

  # --- Check if secret exists ---
  if ! gcloud secrets describe "$SECRET_ID" --project="$PROJECT_ID" --quiet > /dev/null 2>&1; then
    # --- Create Secret ---
    echo "  Secret '$SECRET_ID' not found. Creating..."
    if gcloud secrets create "$SECRET_ID" \
        --project="$PROJECT_ID" \
        --replication-policy="automatic" \
        --labels=managed-by=env-script; then
      echo "  SUCCESS: Secret '$SECRET_ID' created."
    else
      echo "  ERROR: Failed to create secret '$SECRET_ID'. Check permissions or secret name validity. Skipping."
      ((error_count++))
      continue # Skip adding version if creation failed
    fi
  else
    echo "  Secret '$SECRET_ID' already exists. Updating labels (if needed) and adding new version."
     # Optionally update labels on existing secrets
     gcloud secrets update "$SECRET_ID" --project="$PROJECT_ID" --update-labels=managed-by=env-script --remove-labels="" > /dev/null 2>&1 || echo "  Warning: Failed to update labels for existing secret '$SECRET_ID'."
  fi

  # --- Add Secret Version ---
  echo "  Adding new version for secret '$SECRET_ID'..."
  # Use process substitution <(...) to avoid issues with complex values in echo
  if gcloud secrets versions add "$SECRET_ID" \
      --project="$PROJECT_ID" \
      --data-file=- < <(echo -n "$VALUE"); then
    echo "  SUCCESS: New version added for '$SECRET_ID'."
    ((processed_count++))
  else
    echo "  ERROR: Failed to add version for secret '$SECRET_ID'. Check permissions."
     ((error_count++))
  fi
  echo # Blank line for readability

done < "$ENV_FILE"

# --- Summary ---
echo "--------------------------------------------------"
echo "Secret Manager Sync Complete"
echo "  Processed successfully: $processed_count"
echo "  Skipped lines: $skipped_count"
echo "  Errors encountered: $error_count"
echo "--------------------------------------------------"

# Exit with error code if any errors occurred
if [[ $error_count -gt 0 ]]; then
  exit 1
else
  exit 0
fi 