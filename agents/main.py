import os
import urllib.parse
import sqlalchemy
from google.cloud.sql.connector import Connector, IPTypes

import uvicorn
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.sessions.database_session_service import DatabaseSessionService

# Determine environment
ENVIRONMENT = os.environ.get("ENVIRONMENT", "local").lower()

# Initialize connector and engine globally, but configure based on environment
db_connector: Connector | None = None
db_engine: sqlalchemy.Engine | None = None

SESSION_DB_URL = None # Keep this for ADK compatibility for now, but engine is primary

if ENVIRONMENT == "production":
    print("Configuring for PRODUCTION environment...")
    # --- Production Database Connection (Cloud SQL via Connector) ---
    DB_USER = os.environ.get("DB_USER") # e.g., agent_user (must be set in prod)
    DB_PASSWORD = os.environ.get("DB_PASSWORD") # Must be set in prod
    DB_INSTANCE_CONNECTION_NAME = os.environ.get("DB_INSTANCE_CONNECTION_NAME") # e.g. project:region:instance
    DB_NAME = os.environ.get("DB_NAME")         # e.g., main_db (must be set in prod)

    if not all([DB_USER, DB_PASSWORD, DB_INSTANCE_CONNECTION_NAME, DB_NAME]):
        raise ValueError("Missing required environment variables for production: "
                         "DB_USER, DB_PASSWORD, DB_INSTANCE_CONNECTION_NAME, DB_NAME")

    try:
        # Initialize Cloud SQL Python Connector
        # Uses Application Default Credentials (ADC) implicitly
        # refresh_strategy="lazy" is recommended for Cloud Run/Functions
        print("Initializing Cloud SQL Python Connector...")
        db_connector = Connector(refresh_strategy="lazy")

        def getconn():
            conn = db_connector.connect(
                DB_INSTANCE_CONNECTION_NAME,
                "pg8000", # Specify the driver
                user=DB_USER,
                password=DB_PASSWORD,
                db=DB_NAME,
                ip_type=IPTypes.PUBLIC # Or IPTypes.PRIVATE if using private IP
            )
            return conn

        # Create the SQLAlchemy engine using the connector
        print(f"Creating SQLAlchemy engine for {DB_INSTANCE_CONNECTION_NAME}...")
        # Note: The URL dialect needs to match the driver specified in getconn
        db_engine = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            pool_size=5, # Example pool configuration
            max_overflow=2,
            pool_timeout=30,
            pool_recycle=1800,
        )

        # Test connection (optional but recommended)
        try:
            with db_engine.connect() as connection:
                print("Successfully connected to the database via connector.")
        except Exception as e:
             print(f"Database connection test failed: {e}")
             if db_connector:
                 db_connector.close() # Ensure cleanup on failure
             raise

        # ADK expects a URL, even if we use the engine directly later.
        # Construct a dummy URL for compatibility; it won't be used for the actual connection.
        encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
        SESSION_DB_URL = f"postgresql+pg8000://{DB_USER}:{encoded_password}@/{DB_NAME}?host={DB_INSTANCE_CONNECTION_NAME}"
        print(f"Using Cloud SQL DB: {DB_INSTANCE_CONNECTION_NAME} via Connector")

    except Exception as e:
        print(f"Failed to initialize DB connection using Cloud SQL Connector: {e}")
        if db_connector:
             db_connector.close() # Ensure cleanup on failure
        raise # Reraise the exception to prevent starting the app with bad config

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
    # For local, create engine directly from URL
    db_engine = sqlalchemy.create_engine(SESSION_DB_URL)
    print(f"Using Local DB: {DB_HOST_LOCAL}")


# --- FastAPI App Configuration ---

# Get the directory where main.py is located
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Example allowed origins for CORS
ALLOWED_ORIGINS = ["http://localhost", "http://localhost:8080", "*"]
# Set web=True if you intend to serve a web interface, False otherwise
SERVE_WEB_INTERFACE = True

# Call the function to get the FastAPI app instance
# Pass the engine if available (for production via connector), otherwise let ADK use the URL (for local)
app: FastAPI = get_fast_api_app(
    agent_dir=AGENT_DIR,
    session_db_url=SESSION_DB_URL, # Use the conditionally constructed URL
    session_db_engine=db_engine, # Pass the engine created via connector or local URL
    allow_origins=ALLOWED_ORIGINS,
    web=SERVE_WEB_INTERFACE,
)

# --- Add cleanup hook for the connector ---
def close_db_connector():
    if db_connector:
        print("Closing Cloud SQL Python Connector.")
        db_connector.close()

@app.on_event("shutdown")
async def shutdown_event():
    close_db_connector()

if __name__ == "__main__":
    # Use the PORT environment variable provided by Cloud Run, defaulting to 8080
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Uvicorn on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)