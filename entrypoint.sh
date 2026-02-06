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

# Wait for PostgreSQL to be ready (if DATABASE_URL is set)
if [ -n "${DATABASE_URL:-}" ]; then
    echo "Database configured, waiting for PostgreSQL to be ready..."
    MAX_RETRIES=30
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if python3 -c "from backend.database import engine; engine.connect()" 2>/dev/null; then
            echo "Database connection successful"
            
            # Initialize database tables
            echo "Initializing database tables..."
            python3 -c "from backend.database import init_db; init_db()" || echo "WARNING: Database init failed, continuing anyway"

            # Run migrations (idempotent)
            echo "Running database migrations..."
            python3 backend/migrations.py || echo "WARNING: Database migrations failed, continuing anyway"
            
            break
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))
            echo "Waiting for database... ($RETRY_COUNT/$MAX_RETRIES)"
            sleep 2
        fi
    done
    
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo "WARNING: Could not connect to database after $MAX_RETRIES attempts"
        echo "   Application will start without database logging"
    fi
else
    echo "No DATABASE_URL configured, skipping database initialization"
fi

# Start the Gradio app
echo "Launching Gradio application..."
exec python3 app/gradio_app.py --server-name "$GRADIO_SERVER_NAME" --server-port "$GRADIO_SERVER_PORT"
