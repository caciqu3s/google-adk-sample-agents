# Use an official Python runtime based on Debian Slim, matching the project's Python version
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir reduces image size
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create a non-root user and switch to it for security
# RUN adduser --disabled-password --gecos "" myuser && \
#     chown -R myuser:myuser /app
# Skipping user creation for now to avoid potential permission issues with Cloud SQL Auth Proxy sidecar if used later.
# Running as root is common in simple Cloud Run setups where the container is isolated.

# Copy the rest of the application code (main.py and the agents directory)
COPY main.py .
COPY agents/ ./agents/

# Cloud Run expects the application to listen on the port defined by the PORT env var.
# Default to 8080 if not set. Uvicorn in main.py handles this.
# ENV PORT=8080 # No need to set here if main.py reads it
# Inform Docker the container listens on this port (Uvicorn default)
EXPOSE 8080

# Command to run the application using uvicorn
# main:app refers to the 'app' FastAPI instance in the 'main.py' file
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"] 