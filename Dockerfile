# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by yt-dlp for merging formats
# ffmpeg is crucial for combining high-quality video and audio
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- IMPORTANT FIX ---
# Always upgrade yt-dlp to the absolute latest version to keep up with site changes
RUN pip install --no-cache-dir --upgrade yt-dlp

# Copy the rest of the application's code to the working directory
# This includes index.py and the templates directory
COPY . .

# Create the downloads directory within the container
RUN mkdir -p /app/downloads

# Expose the port the app runs on
EXPOSE 5123

# Run the app using gunicorn, a production-ready WSGI server
# This is more robust than Flask's built-in development server
CMD ["gunicorn", "--bind", "0.0.0.0:5123", "--workers", "4", "index:app"]

