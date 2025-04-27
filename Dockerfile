# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PORT=8080
# ENV PATH="/home/myuser/.local/bin:$PATH" # Not needed if installing system-wide

# Set the working directory in the container
WORKDIR /app

# Install system dependencies including Node.js/npm/npx
# Need sudo, curl, gnupg for nodesource setup; install nodejs after
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gnupg sudo ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    # Clean up apt lists to reduce image size
    rm -rf /var/lib/apt/lists/*

# Verify Node/npm/npx installation (optional)
RUN node --version
RUN npm --version
RUN npx --version

# Copy the requirements file from the project root (build context) into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt (system-wide)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt # Removed --user

# Create a non-root user and group
# Add user to sudo group temporarily if needed for global npm installs later, but avoid if possible.
# We install node system-wide as root, so myuser should have access to node/npm/npx in PATH
RUN adduser --disabled-password --gecos "" myuser

# Copy the main application file and the agents directory into the container
COPY main.py .
COPY agents/ /app/agents/

# Set ownership for the app directory
RUN chown -R myuser:myuser /app

# Switch to the non-root user
USER myuser

# Make port 8080 available to the world outside this container
EXPOSE $PORT

# Define the command to run the application
# Assumes your FastAPI app instance is named 'app' in 'main.py'
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"] 