#!/bin/bash
set -e

echo "Starting Audio Anonymizer..."

# Create necessary directories if they don't exist
echo "Ensuring directories exist..."
mkdir -p /app/output
mkdir -p /app/uploads
mkdir -p /app/data/surrogates/luganda/{male,female}/{person,user_id,location}
mkdir -p /app/data/surrogates/english/{male,female}/{person,user_id,location}

# Check if surrogates directory has any files
SURROGATE_COUNT=$(find /app/data/surrogates -type f \( -name "*.wav" -o -name "*.mp3" -o -name "*.flac" -o -name "*.ogg" -o -name "*.m4a" \) 2>/dev/null | wc -l)

if [ "$SURROGATE_COUNT" -eq 0 ]; then
    echo "WARNING: No surrogate audio files found in /app/data/surrogates/"
    echo "   The app will use placeholder tones for anonymization."
    echo "   Please add surrogate files to the appropriate directories."
else
    echo "Found $SURROGATE_COUNT surrogate audio file(s)"
fi

# Set default environment variables if not provided
export GRADIO_SERVER_NAME="${GRADIO_SERVER_NAME:-0.0.0.0}"
export GRADIO_SERVER_PORT="${GRADIO_SERVER_PORT:-7860}"

echo "Server will bind to: ${GRADIO_SERVER_NAME}:${GRADIO_SERVER_PORT}"

# Start the Gradio app
echo "Launching Gradio application..."
exec python3 app/gradio_app.py
