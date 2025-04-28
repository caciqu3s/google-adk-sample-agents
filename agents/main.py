import os
import urllib.parse
import sqlalchemy
import tempfile
import atexit
from google.cloud import secretmanager

import uvicorn
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.sessions.database_session_service import DatabaseSessionService

# Determine environment
ENVIRONMENT = os.environ.get("ENVIRONMENT", "local").lower()

# Initialize engine globally, will be configured based on environment
db_engine: sqlalchemy.Engine | None = None

SESSION_DB_URL = None # Keep this for ADK compatibility

# List to keep track of temporary certificate files
_temp_cert_files = []

def _cleanup_temp_files():
    """Cleans up temporary certificate files."""
    global _temp_cert_files
    for file in _temp_cert_files:
        try:
            print(f"Cleaning up temporary file: {file.name}")
            file.close() # This also deletes the file due to delete=True
        except Exception as e:
            print(f"Error cleaning up temp file {getattr(file, 'name', 'unknown')}: {e}")
    _temp_cert_files = []

# Register the cleanup function to be called on program exit
atexit.register(_cleanup_temp_files)


if ENVIRONMENT == "production":
    print("Configuring for PRODUCTION environment using psycopg and SSL...")
    # --- Production Database Connection (Cloud SQL via psycopg + SSL) ---
    DB_USER = os.environ.get("DB_USER")
    DB_PASSWORD = os.environ.get("DB_PASSWORD")
    DB_HOST_PROD = os.environ.get("DB_HOST_PROD") # Private IP or DNS of Cloud SQL
    DB_PORT_PROD = os.environ.get("DB_PORT_PROD", "5432")
    DB_NAME = os.environ.get("DB_NAME")

    # Secrets for SSL certificates in Secret Manager (full resource names)
    # e.g., projects/your-project-id/secrets/db-server-ca/versions/latest
    DB_SSL_SERVER_CA_SECRET = os.environ.get("DB_SSL_SERVER_CA_SECRET")
    DB_SSL_CLIENT_CERT_SECRET = os.environ.get("DB_SSL_CLIENT_CERT_SECRET")
    DB_SSL_CLIENT_KEY_SECRET = os.environ.get("DB_SSL_CLIENT_KEY_SECRET")

    required_vars = [
        DB_USER, DB_PASSWORD, DB_HOST_PROD, DB_NAME,
        DB_SSL_SERVER_CA_SECRET, DB_SSL_CLIENT_CERT_SECRET, DB_SSL_CLIENT_KEY_SECRET
    ]

    if not all(required_vars):
        raise ValueError("Missing required environment variables for production: "
                         "DB_USER, DB_PASSWORD, DB_HOST_PROD, DB_NAME, "
                         "DB_SSL_SERVER_CA_SECRET, DB_SSL_CLIENT_CERT_SECRET, DB_SSL_CLIENT_KEY_SECRET")

    try:
        # Initialize Secret Manager client
        print("Initializing Secret Manager client...")
        secret_client = secretmanager.SecretManagerServiceClient()

        def get_secret(secret_version_name: str) -> bytes:
            """Fetches a secret version payload."""
            print(f"Fetching secret: {secret_version_name}")
            response = secret_client.access_secret_version(name=secret_version_name)
            return response.payload.data

        # Fetch secrets
        server_ca_data = get_secret(DB_SSL_SERVER_CA_SECRET)
        client_cert_data = get_secret(DB_SSL_CLIENT_CERT_SECRET)
        client_key_data = get_secret(DB_SSL_CLIENT_KEY_SECRET)

        # Create temporary files for certificates
        print("Creating temporary files for SSL certificates...")
        server_ca_file = tempfile.NamedTemporaryFile(delete=False, suffix="-server-ca.pem")
        client_cert_file = tempfile.NamedTemporaryFile(delete=False, suffix="-client-cert.pem")
        client_key_file = tempfile.NamedTemporaryFile(delete=False, suffix="-client-key.pem")

        # Store file objects for cleanup
        _temp_cert_files.extend([server_ca_file, client_cert_file, client_key_file])

        # Write secret data to temp files
        server_ca_file.write(server_ca_data)
        server_ca_file.flush()
        client_cert_file.write(client_cert_data)
        client_cert_file.flush()
        client_key_file.write(client_key_data)
        client_key_file.flush()

        print(f"Server CA path: {server_ca_file.name}")
        print(f"Client Cert path: {client_cert_file.name}")
        print(f"Client Key path: {client_key_file.name}")

        # Construct the connection string for psycopg with SSL
        encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
        SESSION_DB_URL = (
            f"postgresql+psycopg://{DB_USER}:{encoded_password}@{DB_HOST_PROD}:{DB_PORT_PROD}/{DB_NAME}"
            f"?sslmode=verify-ca"
            f"&sslrootcert={server_ca_file.name}"
            f"&sslcert={client_cert_file.name}"
            f"&sslkey={client_key_file.name}"
        )

        print(f"Using Cloud SQL DB: {DB_HOST_PROD} via psycopg with SSL")
        # Let ADK create the engine from the URL
        db_engine = None

    except Exception as e:
        print(f"Failed to initialize DB connection using psycopg+SSL: {e}")
        _cleanup_temp_files() # Attempt cleanup on failure
        raise # Reraise the exception

else:
    print("Configuring for LOCAL environment...")
    # --- Local Database Connection --- 
    DB_USER_LOCAL = os.environ.get("DB_USER_LOCAL", "postgres")
    DB_PASSWORD_LOCAL = os.environ.get("DB_PASSWORD_LOCAL", "password")
    DB_HOST_LOCAL = os.environ.get("DB_HOST_LOCAL", "db") # Default to service name 'db' for compose
    DB_PORT_LOCAL = os.environ.get("DB_PORT_LOCAL", "5432")
    DB_NAME_LOCAL = os.environ.get("DB_NAME_LOCAL", "postgres")

    # Construct the PostgreSQL connection string for local/compose
    SESSION_DB_URL = f"postgresql+psycopg://{DB_USER_LOCAL}:{DB_PASSWORD_LOCAL}@{DB_HOST_LOCAL}:{DB_PORT_LOCAL}/{DB_NAME_LOCAL}"
    # For local, create engine directly from URL if needed, or let ADK handle it
    # db_engine = sqlalchemy.create_engine(SESSION_DB_URL) # ADK can handle this
    db_engine = None # Let ADK handle engine creation from URL
    print(f"Using Local DB: {DB_HOST_LOCAL}")


# --- FastAPI App Configuration ---

# Get the directory where main.py is located
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Example allowed origins for CORS
ALLOWED_ORIGINS = ["http://localhost", "http://localhost:8080", "*"]
# Set web=True if you intend to serve a web interface, False otherwise
SERVE_WEB_INTERFACE = True

# Call the function to get the FastAPI app instance
# Pass the engine if available (none needed now, ADK uses URL), otherwise let ADK use the URL
app: FastAPI = get_fast_api_app(
    agent_dir=AGENT_DIR,
    session_db_url=SESSION_DB_URL, # Use the conditionally constructed URL
    # session_db_engine=db_engine, # Remove: Let ADK create engine from URL
    allow_origins=ALLOWED_ORIGINS,
    web=SERVE_WEB_INTERFACE,
)

# --- Remove cleanup hook for the connector ---
# No longer needed as connector is removed and temp files handled by atexit

# @app.on_event("shutdown")
# async def shutdown_event():
#    pass # atexit handles temp file cleanup

# Alternative using atexit if needed, but FastAPI shutdown event is preferred
# import atexit
# atexit.register(close_db_connector)

# You can add more FastAPI routes or configurations below if needed
# Example:
# @app.get("/hello")
# async def read_root():
#     return {"Hello": "World"}

if __name__ == "__main__":
    # Use the PORT environment variable provided by Cloud Run, defaulting to 8080
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Uvicorn on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)