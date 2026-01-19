# Surrogate Tracking Implementation Summary

## What Was Added

Your audio anonymization platform now fully tracks surrogate names and timestamps in the database.

## New Features

### 1. **AnnotationSurrogate Table**
A new database table that records every annotation processed:

```sql
CREATE TABLE annotation_surrogates (
    id SERIAL PRIMARY KEY,
    processing_job_id INTEGER REFERENCES processing_jobs(id),
    
    -- Annotation details
    start_sec FLOAT NOT NULL,
    end_sec FLOAT NOT NULL,
    duration_sec FLOAT NOT NULL,
    gender VARCHAR(20) NOT NULL,
    label VARCHAR(100),
    language VARCHAR(50) NOT NULL,
    
    -- Surrogate information
    surrogate_name VARCHAR(500) NOT NULL,
    surrogate_file_path VARCHAR(1000) NOT NULL,
    surrogate_duration_ms INTEGER,
    
    -- Timestamp when annotation was processed
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Processing strategy used
    processing_strategy VARCHAR(50)
);
```

### 2. **Enhanced Audio Processing**
- Functions now return both the processed audio AND surrogate usage details
- Each annotation's surrogate path is tracked during processing
- Surrogate selection is logged with full file paths

### 3. **Database Logging**
- New method `log_annotation_surrogates()` in ProcessingJobLogger
- Automatically updates surrogate usage statistics
- Links each annotation to its parent processing job

### 4. **Gradio App Integration**
- Automatically captures and stores surrogate information
- Links annotations to processing jobs
- Updates timestamps in real-time

## Files Modified

1. **backend/database.py**
   - Added `AnnotationSurrogate` model
   - Added foreign key relationship to ProcessingJob

2. **backend/audio_processing.py**
   - Modified `_load_and_fit_surrogate()` to return (audio, path)
   - Modified `_load_surrogate_direct()` to return (audio, path)
   - Modified `anonymize_with_surrogates()` to return (audio, usage_list)
   - Modified `anonymize_file()` to return (path, usage_list)
   - Modified `anonymize_to_bytes()` to return (bytes, usage_list)

3. **backend/db_logger.py**
   - Added `log_annotation_surrogates()` method
   - Imported `AnnotationSurrogate` model
   - Enhanced surrogate statistics tracking

4. **app/gradio_app.py**
   - Updated to capture surrogate usage information
   - Calls `log_annotation_surrogates()` after processing
   - Handles new return values from processing functions

## New Files Created

1. **backend/migrations.py**
   - Database migration script
   - Creates AnnotationSurrogate table
   - Can be run safely multiple times

2. **DATABASE.md**
   - Complete database documentation
   - Query examples
   - Troubleshooting guide

3. **scripts/view_surrogate_tracking.py**
   - Utility to view tracking data
   - Shows recent jobs, statistics, and today's activity
   - Examples of querying the database

## How to Use

### Step 1: Run Migration

```bash
# Start database if not running
docker-compose up -d postgres

# Run migration to create new table
python backend/migrations.py
```

### Step 2: Process Audio Files

Use the Gradio app normally - surrogate tracking is automatic:

```bash
python app/gradio_app.py
```

### Step 3: View Tracking Data

```bash
# View all tracking information
python scripts/view_surrogate_tracking.py

# Or view specific data
python scripts/view_surrogate_tracking.py --jobs      # Recent jobs
python scripts/view_surrogate_tracking.py --stats     # Statistics
python scripts/view_surrogate_tracking.py --today     # Today's activity
python scripts/view_surrogate_tracking.py --inventory # Available surrogates
```

## Example Queries

### Get all annotations for a specific job:

```python
from backend.database import get_db_session, AnnotationSurrogate

db = get_db_session()
annotations = db.query(AnnotationSurrogate).filter(
    AnnotationSurrogate.processing_job_id == 123
).all()

for ann in annotations:
    print(f"{ann.start_sec}s-{ann.end_sec}s: {ann.surrogate_name} at {ann.created_at}")
```

### Get most used surrogates:

```python
from backend.database import get_db_session, AnnotationSurrogate
from sqlalchemy import func, desc

db = get_db_session()
results = db.query(
    AnnotationSurrogate.surrogate_name,
    func.count(AnnotationSurrogate.id).label('count')
).group_by(
    AnnotationSurrogate.surrogate_name
).order_by(desc('count')).all()

for name, count in results:
    print(f"{name}: {count} uses")
```

### Get today's processed annotations:

```python
from backend.database import get_db_session, AnnotationSurrogate
from datetime import datetime
from sqlalchemy import func

db = get_db_session()
today = datetime.utcnow().date()

count = db.query(func.count(AnnotationSurrogate.id)).filter(
    func.date(AnnotationSurrogate.created_at) == today
).scalar()

print(f"Processed {count} annotations today")
```

## Data Tracked Per Annotation

For each annotation processed, the database now stores:

1. **Timing Information**
   - `start_sec`: When the annotation starts
   - `end_sec`: When the annotation ends
   - `duration_sec`: Duration of the annotation
   - `created_at`: **Timestamp when it was processed**

2. **Surrogate Information**
   - `surrogate_name`: Name of the audio file used (e.g., "PERSON.wav")
   - `surrogate_file_path`: Full path to the surrogate file
   - `surrogate_duration_ms`: Duration of the surrogate used

3. **Metadata**
   - `gender`: male/female
   - `label`: PERSON/USER_ID/LOCATION
   - `language`: english/luganda/etc
   - `processing_strategy`: direct/fit

4. **Job Linkage**
   - `processing_job_id`: Links to the parent processing job

## Benefits

- **Complete Audit Trail**: Know exactly which surrogate was used for each annotation
- **Temporal Tracking**: Know when each annotation was processed
- **Usage Analytics**: See which surrogates are used most frequently
- **Quality Assurance**: Verify surrogate selection logic
- **Performance Metrics**: Analyze processing patterns over time
- **Debugging**: Trace issues to specific surrogate files

## Backward Compatibility

- Existing functionality unchanged
- Database migration is non-destructive
- Runs safely on existing databases
- Gracefully handles missing database connections
