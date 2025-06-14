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
# --- NEW: Set the TTS home directory inside the container ---
# This ensures the model is stored within our app's directory.
ENV TTS_HOME /app/.tts

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
# This is done first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# --- NEW: Bake the TTS model into the Docker image ---
# This command downloads the model during the build process, so it's
# available instantly at runtime without needing a live download.
RUN tts --model_name "tts_models/multilingual/multi-dataset/xtts_v2"

# Copy the rest of the application code into the container
COPY . .

# Command to run the application using Gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 $APP_MODULE