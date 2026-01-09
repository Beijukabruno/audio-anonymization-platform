#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1

echo "Starting Audio Anonymizer..."

# Create necessary directories if they don't exist
echo "Ensuring directories exist..."
mkdir -p /app/output
mkdir -p /app/uploads
mkdir -p /app/data/surrogates/luganda/male/person
mkdir -p /app/data/surrogates/luganda/male/user_id
mkdir -p /app/data/surrogates/luganda/male/location
mkdir -p /app/data/surrogates/luganda/female/person
mkdir -p /app/data/surrogates/luganda/female/user_id
mkdir -p /app/data/surrogates/luganda/female/location
mkdir -p /app/data/surrogates/english/male/person
mkdir -p /app/data/surrogates/english/male/user_id
mkdir -p /app/data/surrogates/english/male/location
mkdir -p /app/data/surrogates/english/female/person
mkdir -p /app/data/surrogates/english/female/user_id
mkdir -p /app/data/surrogates/english/female/location

# Check if surrogates directory has any files
SURROGATE_COUNT=$(find /app/data/surrogates -type f -name "*.wav" -o -name "*.mp3" -o -name "*.flac" -o -name "*.ogg" -o -name "*.m4a" 2>/dev/null | wc -l)

if [ "$SURROGATE_COUNT" -eq 0 ]; then
    echo "WARNING: No surrogate audio files found in /app/data/surrogates/"
    echo "   The app will use placeholder tones for anonymization."
    echo "   Please add surrogate files to the appropriate directories."
else
    echo "Found $SURROGATE_COUNT surrogate audio file(s)"
fi

# Set default environment variables if not provided
GRADIO_SERVER_NAME="${GRADIO_SERVER_NAME:-0.0.0.0}"
GRADIO_SERVER_PORT="${GRADIO_SERVER_PORT:-7860}"

echo "Server will bind to: $GRADIO_SERVER_NAME:$GRADIO_SERVER_PORT"

# Start the Gradio app
echo "Launching Gradio application..."
exec python3 app/gradio_app.py --server-name "$GRADIO_SERVER_NAME" --server-port "$GRADIO_SERVER_PORT"
