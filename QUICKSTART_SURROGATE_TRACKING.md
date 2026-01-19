# Surrogate Tracking - Quick Reference

## Quick Setup

```bash
# One-command setup
./setup_surrogate_tracking.sh

# Or manually:
docker-compose up -d postgres
python backend/migrations.py
```

## 📊 View Tracking Data

```bash
# View everything
python scripts/view_surrogate_tracking.py

# View specific data
python scripts/view_surrogate_tracking.py --jobs      # Recent processing jobs
python scripts/view_surrogate_tracking.py --stats     # Surrogate usage stats
python scripts/view_surrogate_tracking.py --today     # Today's activity
python scripts/view_surrogate_tracking.py --inventory # Available surrogates
```

## What's Stored in Database

### For Each Processing Job:
- Job ID and timestamps (created, completed)
- Input/output filenames and sizes
- Processing status and duration
- Primary surrogate used
- Gender and language detected

### For Each Annotation (NEW):
- **Surrogate name** (e.g., "PERSON.wav")
- **Timestamp** when processed
- Time range (start, end, duration)
- Gender, label, language
- Full surrogate file path
- Processing strategy used

## 🔍 Common Queries

### Python API:

```python
from backend.database import get_db_session, AnnotationSurrogate

# Get all annotations for a job
db = get_db_session()
annotations = db.query(AnnotationSurrogate).filter_by(processing_job_id=123).all()

for ann in annotations:
    print(f"{ann.created_at}: {ann.surrogate_name}")
```

### SQL

```sql
-- Recent annotations with surrogate info
SELECT 
    created_at,
    start_sec,
    end_sec,
    gender,
    label,
    surrogate_name
FROM annotation_surrogates
ORDER BY created_at DESC
LIMIT 10;

-- Surrogate usage count
SELECT 
    surrogate_name,
    COUNT(*) as usage_count
FROM annotation_surrogates
GROUP BY surrogate_name
ORDER BY usage_count DESC;

-- Today's activity
SELECT COUNT(*) 
FROM annotation_surrogates 
WHERE DATE(created_at) = CURRENT_DATE;
```

## Files Changed

- `backend/database.py` - Added AnnotationSurrogate table
- `backend/audio_processing.py` - Returns surrogate usage info
- `backend/db_logger.py` - Logs annotation details
- `app/gradio_app.py` - Captures and stores surrogate data

## New Files

- `backend/migrations.py` - Database migration script
- `scripts/view_surrogate_tracking.py` - View tracking data
- `DATABASE.md` - Complete database documentation
- `SURROGATE_TRACKING.md` - Feature documentation
- `setup_surrogate_tracking.sh` - Setup automation

## Key Benefits

1. **Audit Trail**: Know exactly which surrogate was used
2. **Timestamps**: Track when each annotation was processed
3. **Analytics**: See usage patterns and statistics
4. **Quality Control**: Verify surrogate selection
5. **Debugging**: Trace issues to specific files

## ⚙️ How It Works

1. User uploads audio and adds annotations in Gradio UI
2. `anonymize_to_bytes()` processes each annotation
3. For each annotation:
   - Selects appropriate surrogate file
   - Records surrogate name and path
   - Captures timestamp
4. `ProcessingJobLogger` saves all details to database
5. Data queryable via Python API or SQL

## Troubleshooting

### Database connection error?
```bash
docker-compose up -d postgres
sleep 5
python backend/migrations.py
```

### No data showing?
Process some audio files through the Gradio app first!

### View database logs:
```bash
docker logs audio-anonymization-db-local
```

## Documentation

- Full details: `SURROGATE_TRACKING.md`
- Database guide: `DATABASE.md`
- Deployment: `DEPLOYMENT.md`
