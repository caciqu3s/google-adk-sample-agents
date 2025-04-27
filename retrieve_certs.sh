#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define Secret IDs and output directory
CA_CERT_SECRET_ID="sql-server-ca-cert"
CLIENT_CERT_SECRET_ID="sql-client-cert-agent-user"
CLIENT_KEY_SECRET_ID="sql-client-key-agent-user"
OUTPUT_DIR="./certs"

# Create the output directory if it doesn't exist
echo "Creating directory $OUTPUT_DIR if it doesn't exist..."
mkdir -p "$OUTPUT_DIR"

# Retrieve the CA Certificate
echo "Retrieving CA certificate ($CA_CERT_SECRET_ID)..."
gcloud secrets versions access latest --secret="$CA_CERT_SECRET_ID" --format='get(payload.data)' | base64 --decode > "$OUTPUT_DIR/server-ca.pem"

# Retrieve the Client Certificate
echo "Retrieving client certificate ($CLIENT_CERT_SECRET_ID)..."
gcloud secrets versions access latest --secret="$CLIENT_CERT_SECRET_ID" --format='get(payload.data)' | base64 --decode > "$OUTPUT_DIR/client-cert.pem"

# Retrieve the Client Private Key
echo "Retrieving client private key ($CLIENT_KEY_SECRET_ID)..."
gcloud secrets versions access latest --secret="$CLIENT_KEY_SECRET_ID" --format='get(payload.data)' | base64 --decode > "$OUTPUT_DIR/client-key.pem"

# Ensure the private key file has restricted permissions
chmod 600 "$OUTPUT_DIR/client-key.pem"

echo "Successfully retrieved and saved certificates to $OUTPUT_DIR"