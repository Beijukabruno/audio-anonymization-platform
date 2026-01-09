# Use Python 3.12 slim image
FROM python:3.12-slim

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY backend/ ./backend/
COPY data/ ./data/
COPY entrypoint.sh .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Create output directory
RUN mkdir -p /app/output

# Expose Gradio default port
EXPOSE 7860

# Set environment variables
ENV GRADIO_SERVER_NAME=0.0.0.0
ENV GRADIO_SERVER_PORT=7860

# Run the application
ENTRYPOINT ["./entrypoint.sh"]
