# Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV APP_MODULE main:app
ENV PORT 8080
ENV TTS_HOME /app/.tts
# --- NEW: Automatically agree to the Coqui-AI Terms of Service ---
ENV COQUI_TOS_AGREED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Bake the TTS model into the Docker image
RUN tts --model_name "tts_models/multilingual/multi-dataset/xtts_v2"

# Copy the rest of the application code into the container
COPY . .

# Command to run the application using Gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 $APP_MODULE