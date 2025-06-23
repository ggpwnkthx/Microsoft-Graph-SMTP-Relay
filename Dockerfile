# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Set environment variables
# Python won’t try to write .pyc files on the import of source modules
ENV PYTHONDONTWRITEBYTECODE 1
# Python buffers stdout and stderr by default, this option ensures that it doesn’t
ENV PYTHONUNBUFFERED 1

# Install system dependencies
# This layer is cached, so these packages won't be re-downloaded each build unless they change
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the files needed to /usr/src/app
COPY app/ .
# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Define environment variables for your application
ENV SMTP_RELAY_HOSTNAME=0.0.0.0
ENV SMTP_RELAY_PORT=25

# Run the Python application
# Use ENTRYPOINT to ensure the script runs
ENTRYPOINT ["python"]

# Use CMD to provide default arguments to ENTRYPOINT
CMD ["server_threaded.py"]
