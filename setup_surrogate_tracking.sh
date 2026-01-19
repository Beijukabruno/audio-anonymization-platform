#!/bin/bash

# Setup script for surrogate tracking feature
# Run this after pulling the latest code changes

set -e  # Exit on error

echo "=================================================="
echo "Setting Up Surrogate Tracking Feature"
echo "=================================================="
echo ""

# Check if PostgreSQL is running
echo "1. Checking database connection..."
if docker ps | grep -q "audio-anonymization-db"; then
    echo "   [OK] Database container is running"
else
    echo "   [WARNING] Database container not running"
    echo "   Starting database..."
    docker-compose up -d postgres
    echo "   Waiting for database to be ready..."
    sleep 10
fi

# Run migration
echo ""
echo "2. Running database migration..."
python3 backend/migrations.py

# Initialize surrogate voices
echo ""
echo "3. Initializing surrogate voices in database..."
python3 -c "
from backend.db_logger import init_surrogate_voices
from backend.database import get_db_session

db = get_db_session()
init_surrogate_voices('data/surrogates', db)
db.close()
print('[OK] Surrogate voices initialized')
"

# Verify setup
echo ""
echo "4. Verifying setup..."
python3 scripts/view_surrogate_tracking.py --inventory

echo ""
echo "=================================================="
echo "[SUCCESS] Setup Complete!"
echo "================================================="="
echo ""
echo "Next steps:"
echo "  1. Start the application: python app/gradio_app.py"
echo "  2. Process some audio files"
echo "  3. View tracking data: python scripts/view_surrogate_tracking.py"
echo ""
echo "Documentation:"
echo "  - SURROGATE_TRACKING.md - Feature overview and usage"
echo "  - DATABASE.md - Database schema and queries"
echo ""
