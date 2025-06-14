# Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# Let Gunicorn know where to find the app
ENV APP_MODULE main:app
# Port that Cloud Run will listen on
ENV PORT 8080

# Install system dependencies that might be needed by Python libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install dependencies
# This is done in a separate step to leverage Docker's layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Command to run the application using Gunicorn
# Gunicorn is a production-ready web server for Python.
# --timeout 0 disables the timeout, which is useful for long-running TTS jobs.
# --workers 1 is recommended for Cloud Run v2 (CPU always allocated).
# The $PORT variable is automatically set by Cloud Run.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 $APP_MODULE
