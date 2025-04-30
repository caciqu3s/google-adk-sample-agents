import os
import urllib.parse
import sqlalchemy # Keep for potential type hints

import uvicorn
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

# --- Environment Configuration ---
ENVIRONMENT = os.environ.get("ENVIRONMENT", "local").lower()
print(f"Configuring for {ENVIRONMENT.upper()} environment...")

# --- Database URL Configuration ---
SESSION_DB_URL_FOR_SERVICE: str
DB_USER = os.environ.get("DB_USER") # Used by production and production-local
DB_PASSWORD = os.environ.get("DB_PASSWORD") # Used by production and production-local
DB_NAME = os.environ.get("DB_NAME") # Used by production and production-local

# Common check for production credentials
if ENVIRONMENT.startswith("production"):
    required_vars_prod = [DB_USER, DB_PASSWORD, DB_NAME]
    if not all(required_vars_prod):
        missing = [name for name, var in zip(
            ["DB_USER", "DB_PASSWORD", "DB_NAME"], required_vars_prod
            ) if not var]
        raise ValueError(f"Missing required environment variables for {ENVIRONMENT} DB: {', '.join(missing)}")

if ENVIRONMENT == "production":
    # Production (Cloud Run): Connect via Cloud SQL Unix Socket
    # Assumes Cloud Run service is configured with a Cloud SQL connection
    # pointing the instance connection name to /cloudsql/
    print("Using Cloud Run configuration: Connecting via Unix Socket")
    INSTANCE_CONNECTION_NAME = os.environ.get("DB_INSTANCE_CONNECTION_NAME")
    if not INSTANCE_CONNECTION_NAME:
         raise ValueError("Missing required environment variable for production: DB_INSTANCE_CONNECTION_NAME")

    # Socket path format: /cloudsql/<INSTANCE_CONNECTION_NAME>/.s.PGSQL.5432
    socket_path = f"/cloudsql/{INSTANCE_CONNECTION_NAME}/.s.PGSQL.5432"

    # URL Encode user/password
    encoded_user = urllib.parse.quote_plus(DB_USER)
    encoded_pass = urllib.parse.quote_plus(DB_PASSWORD)

    # Use pg8000 driver with unix_sock query parameter
    SESSION_DB_URL_FOR_SERVICE = (
        f"postgresql+pg8000://{encoded_user}:{encoded_pass}@/{DB_NAME}"
        f"?unix_sock={socket_path}"
    )
    print(f"Using DB URL for ADK Session Service (Cloud Run Unix Socket): postgresql+pg8000://<user>:***@/<db_name>?unix_sock=...")

elif ENVIRONMENT == "production-local":
    # Production-Local (Docker Compose): Connect via Cloud SQL Auth Proxy service
    print("Using Docker configuration: Connecting via Cloud SQL Auth Proxy")
    proxy_host = "cloud-sql-proxy" # Docker service name
    proxy_port = "5432"

    # URL Encode user/password
    encoded_user = urllib.parse.quote_plus(DB_USER)
    encoded_pass = urllib.parse.quote_plus(DB_PASSWORD)

    # Use pg8000 driver for proxy connection URL
    SESSION_DB_URL_FOR_SERVICE = (
        f"postgresql+pg8000://{encoded_user}:{encoded_pass}"
        f"@{proxy_host}:{proxy_port}/{DB_NAME}"
    )
    print(f"Using DB URL for ADK Session Service (via Proxy): postgresql+pg8000://<user>:***@{proxy_host}:{proxy_port}/{DB_NAME}")

else: # local
    # Local: Connect directly to a local DB service (e.g., another Docker container)
    print("Using Local configuration: Connecting directly to local DB")
    DB_USER_LOCAL = os.environ.get("DB_USER_LOCAL", "postgres")
    DB_PASSWORD_LOCAL = os.environ.get("DB_PASSWORD_LOCAL", "password")
    DB_HOST_LOCAL = os.environ.get("DB_HOST_LOCAL", "db") # Default Docker Compose service name
    DB_PORT_LOCAL = os.environ.get("DB_PORT_LOCAL", "5432")
    DB_NAME_LOCAL = os.environ.get("DB_NAME_LOCAL", "postgres")

    # URL Encode user/password
    encoded_user = urllib.parse.quote_plus(DB_USER_LOCAL)
    encoded_pass = urllib.parse.quote_plus(DB_PASSWORD_LOCAL)

    # Use psycopg driver for direct local connection URL (or pg8000 if preferred/installed)
    SESSION_DB_URL_FOR_SERVICE = (
        f"postgresql+psycopg://{encoded_user}:{encoded_pass}"
        f"@{DB_HOST_LOCAL}:{DB_PORT_LOCAL}/{DB_NAME_LOCAL}"
    )
    print(f"Using DB URL for ADK Session Service (Local): postgresql+psycopg://<user>:***@{DB_HOST_LOCAL}:{DB_PORT_LOCAL}/{DB_NAME_LOCAL}")

# --- FastAPI App Configuration ---

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.join(_APP_DIR, "agents")
print(f"ADK Agent Directory set to: {AGENT_DIR}")

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*,http://localhost,http://localhost:8080").split(',')
SERVE_WEB_INTERFACE = os.environ.get("SERVE_WEB_INTERFACE", "True").lower() == "true"

print(f"Allowed Origins: {ALLOWED_ORIGINS}")
print(f"Serve Web Interface: {SERVE_WEB_INTERFACE}")

try:
    print("Initializing FastAPI app with ADK...")
    app: FastAPI = get_fast_api_app(
        agent_dir=AGENT_DIR,
        session_db_url=SESSION_DB_URL_FOR_SERVICE, # ADK uses this to create DatabaseSessionService
        allow_origins=ALLOWED_ORIGINS,
        web=SERVE_WEB_INTERFACE,
    )
    print("FastAPI app initialized successfully.")
except Exception as e:
    print(f"Failed to initialize FastAPI app: {e}")
    raise

# --- Application Entry Point ---
if __name__ == "__main__":
    # Use the PORT environment variable provided by Cloud Run/Compose, defaulting to 8080
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0") # Listen on all interfaces by default
    print(f"Starting Uvicorn server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)