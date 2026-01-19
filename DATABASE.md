# Database Setup and Migration Guide

## Overview

The platform uses PostgreSQL to track:
- **Processing Jobs**: Each audio anonymization job with timestamps, status, and metadata
- **Surrogate Voices**: Available surrogate audio files for replacement
- **Annotation Surrogates**: Individual annotations processed with surrogate names and timestamps
- **Daily Statistics**: Aggregated usage statistics

## Quick Start

### 1. Initialize Database (First Time)

```bash
# Start PostgreSQL container
docker-compose up -d postgres

# Wait for database to be ready
sleep 5

# Initialize all tables
python -m backend.database
```

### 2. Run Migrations (After Code Updates)

```bash
# Run pending migrations
python backend/migrations.py

# Or initialize all tables if starting fresh
python backend/migrations.py --init-all
```

## Database Schema

### ProcessingJob Table
Stores each audio anonymization job:
- `id`: Unique job identifier
- `created_at`: When the job was created
- `completed_at`: When the job finished
- `user_session_id`: Session identifier
- `original_filename`: Input file name
- `output_filename`: Output file name
- `status`: pending/processing/completed/failed
- `processing_method`: anonymize/surrogate_replace/both
- `surrogate_voice_used`: Name of surrogate used
- `gender_detected`: Detected gender (male/female/unknown)
- `language_detected`: Detected language
- `processing_duration_seconds`: Time taken
- Various file size and duration metrics

### AnnotationSurrogate Table (NEW)
Tracks each annotation processed with surrogate details:
- `id`: Unique annotation record ID
- `processing_job_id`: Foreign key to ProcessingJob
- `start_sec`, `end_sec`, `duration_sec`: Annotation timing
- `gender`, `label`, `language`: Annotation metadata
- `surrogate_name`: Name of the surrogate file used
- `surrogate_file_path`: Full path to surrogate file
- `surrogate_duration_ms`: Duration of surrogate used
- `created_at`: **Timestamp when annotation was processed**
- `processing_strategy`: direct/fit

### SurrogateVoice Table
Tracks available surrogate audio files:
- `name`: Unique surrogate identifier
- `gender`: male/female
- `language`: english/luganda/etc
- `file_path`: Path to audio file
- `usage_count`: How many times used
- `last_used_at`: Last usage timestamp

### DailyStatistics Table
Aggregated daily metrics for monitoring.

## Querying Surrogate Usage

### Get all surrogates used for a specific job:

```python
from backend.database import get_db_session, AnnotationSurrogate

db = get_db_session()
job_id = 123

annotations = db.query(AnnotationSurrogate).filter(
    AnnotationSurrogate.processing_job_id == job_id
).all()

for ann in annotations:
    print(f"{ann.start_sec:.2f}s-{ann.end_sec:.2f}s: {ann.surrogate_name} (created: {ann.created_at})")

db.close()
```

### Get surrogate usage statistics:

```python
from backend.database import get_db_session, AnnotationSurrogate
from sqlalchemy import func

db = get_db_session()

# Count usage per surrogate
results = db.query(
    AnnotationSurrogate.surrogate_name,
    func.count(AnnotationSurrogate.id).label('count')
).group_by(AnnotationSurrogate.surrogate_name).all()

for surrogate_name, count in results:
    print(f"{surrogate_name}: {count} uses")

db.close()
```

### Get all annotations processed today:

```python
from backend.database import get_db_session, AnnotationSurrogate
from datetime import datetime, timedelta

db = get_db_session()
today = datetime.utcnow().date()

annotations = db.query(AnnotationSurrogate).filter(
    func.date(AnnotationSurrogate.created_at) == today
).all()

print(f"Processed {len(annotations)} annotations today")
db.close()
```

## Troubleshooting

### Database Connection Issues

Check the connection string in `.env` or use default:
```
DATABASE_URL=postgresql://audio_user:audio_dev_password@localhost:5432/audio_anony
```

For Docker deployment:
```
DATABASE_URL=postgresql://audio_user:audio_dev_password@postgres:5432/audio_anony
```

### Reset Database

```bash
# Stop and remove containers
docker-compose down -v

# Start fresh
docker-compose up -d postgres
python backend/migrations.py --init-all
```

### View Database Logs

```bash
docker logs audio-anonymization-db-local
```

## Migration History

1. **Initial Schema**: ProcessingJob, SurrogateVoice, DailyStatistics
2. **2026-01-18**: Added AnnotationSurrogate table to track individual annotations with surrogate names and timestamps
