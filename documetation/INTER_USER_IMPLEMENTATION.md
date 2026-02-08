# Inter-User Annotation Agreement Tracking - Implementation Summary

## COMPLETED

### 1. Database Schema (`/backend/database.py`)
- **ProcessingJob** extended with:
  - `user_session_id`: Unique user identifier
  - `audio_file_hash`: Tracking same audio across users
- **AnnotationSurrogate** extended with:
  - `audio_file_hash`: Links annotations to source file
  - `created_at`: Timestamp of annotation
- **UserAnnotationAgreement** table created with:
  - Complete inter-user comparison fields
  - Agreement metrics (gender_match, label_match, surrogate_match)
  - Overall agreement level classification
  - Time overlap percentage calculation

### 2. Database Helper Functions (`/backend/database.py`)
All query and analysis functions implemented:

  - Main function generating inter-user comparisons
  - Automatically creates UserAnnotationAgreement records
  - Filters by 20%+ time overlap

- `get_agreement_summary_for_audio(db, audio_file_hash)`
  - Returns summary statistics (complete/partial/none counts and percentages)
  - Includes average overlap percentage

- `get_all_user_pairs_for_audio(db, audio_file_hash)`
  - Returns unique user pairs who annotated same file
  - Shows agreement percentage per pair

- `get_user_annotations_for_audio(db, audio_file_hash, user_session_id)`
  - Returns specific user's annotations for a file
  - Useful for side-by-side comparison

- `get_disagreement_segments_for_audio(db, audio_file_hash)`
  - Returns only non-complete agreement segments
  - For focused review of differences

### 3. Database Logging Updates (`/backend/db_logger.py`)
- **ProcessingJobLogger.__init__** extended with:
  - `audio_file_hash` parameter for tracking
  
- **log_annotation_surrogates()** enhanced:
  - Now accepts `audio_file_hash` parameter
  - Stores hash in AnnotationSurrogate records
  - Automatically triggers `compare_user_annotations()` when hash provided
  - Logs inter-user comparison results

### 4. Utility Script (`/scripts/view_inter_user_agreement.py`)
Complete command-line tool for viewing agreement metrics:

```bash
# List all audio files with annotations
python scripts/view_inter_user_agreement.py --list-files

# View summary for specific file
python scripts/view_inter_user_agreement.py --file-hash abc123

# View all annotations by a user
python scripts/view_inter_user_agreement.py --file-hash abc123 --user-session user-uuid

# View user pairs and agreement %
python scripts/view_inter_user_agreement.py --file-hash abc123 --pairs

# View only disagreement segments
python scripts/view_inter_user_agreement.py --file-hash abc123 --disagreements
```

### 5. Documentation (`/INTER_USER_TRACKING.md`)
Complete guide including:
- Database schema explanation
- Function documentation with examples
- Workflow instructions
- Integration examples
- Query patterns

---

## NEXT STEPS (for Gradio App Integration)

### Step 1: Update `gradio_app.py` - User Session Management
Generate unique user session ID on app startup:

```python
import uuid

USER_SESSION_ID = str(uuid.uuid4())  # Generate once at startup

# Or use username if authentication exists
# USER_SESSION_ID = current_user.username
```

### Step 2: Update `gradio_app.py` - Audio File Hashing
Calculate hash when processing audio:

```python
import hashlib

def process_audio(audio_file):
    # Calculate hash for inter-user tracking
    audio_data = audio_file.read()
    audio_file_hash = hashlib.sha256(audio_data).hexdigest()[:16]
    
    # ... rest of processing ...
    
    return audio_file_hash, processed_audio
```

### Step 3: Update `gradio_app.py` - Database Logging
Pass audio_file_hash and user_session_id to logger:

```python
from backend.db_logger import ProcessingJobLogger

with ProcessingJobLogger(
    original_filename=filename,
    processing_method="surrogate_replace",  # Without voice modification for now
    parameters={"method": "direct"},
    user_session_id=USER_SESSION_ID,  # Pass user ID
) as logger:
    # ... process audio ...
    
    # Log with audio hash
    logger.log_annotation_surrogates(
        surrogate_usage_list=usage_list,
        audio_file_hash=audio_file_hash,  # Pass hash
    )
```

### Step 4: Update `gradio_app.py` - Display Agreement Metrics
Show inter-user agreement in UI (if multiple users have annotated):

```python
from backend.database import (
    get_agreement_summary_for_audio,
    get_db_session,
)

# After processing
db = get_db_session()
try:
    summary = get_agreement_summary_for_audio(db, audio_file_hash)
    if summary['total_comparisons'] > 0:
        gr.Markdown(f"""
        ### Inter-User Agreement (This file annotated by {len(user_ids)} users)
        - **Complete Agreement**: {summary['complete_agreement']} segments ({summary['complete_percent']}%)
        - **Partial Agreement**: {summary['partial_agreement']} segments
        - **Disagreement**: {summary['no_agreement']} segments
        - **Average Overlap**: {summary['avg_overlap_percent']}%
        """)
finally:
    db.close()
```

### Step 5: Optional - Add Query UI
Create interface to view agreement metrics:

```python
import gradio as gr

# Add new tab in Gradio app
with gr.Tab("Inter-User Analysis"):
    file_hash_input = gr.Textbox(label="Audio File Hash", lines=1)
    query_button = gr.Button("View Agreement")
    
    agreement_output = gr.Markdown()
    disagreement_output = gr.Dataframe()
    
    query_button.click(
        fn=show_agreement_metrics,
        inputs=[file_hash_input],
        outputs=[agreement_output, disagreement_output]
    )
```

---

## Configuration Notes

### User Session ID Options
Choose one based on your setup:

1. **Per-Session (Current Default)**
   ```python
   import uuid
   USER_SESSION_ID = str(uuid.uuid4())  # New UUID each session
   ```
   - Pro: Privacy-preserving, easy to reset
   - Con: Can't track same user across sessions

2. **Username-Based**
   ```python
   USER_SESSION_ID = current_user.username  # Requires authentication
   ```
   - Pro: Track same user across sessions
   - Con: Requires login system

3. **Browser Fingerprinting**
   ```python
   import hashlib
   browser_id = hashlib.md5(f"{user_agent}{ip_address}".encode()).hexdigest()
   ```
   - Pro: Persistent across sessions
   - Con: May fail with VPNs, cookie blocking

### Database Initialization
When first running with new schema:

```python
from backend.database import init_db

# Create all tables
init_db()
```

Tables created automatically in `ProcessingJobLogger.__enter__()` if using context manager.

---

## Data Flow

```
User Uploads Audio
        ↓
[Calculate audio_file_hash]
        ↓
[Generate user_session_id]
        ↓
ProcessingJobLogger created with:
  - user_session_id
  - original_filename
  - audio_file_hash (NEW)
        ↓
Log annotations with:
  - audio_file_hash (NEW)
        ↓
In log_annotation_surrogates():
  - Stores hash in AnnotationSurrogate
  - Calls compare_user_annotations() (NEW)
        ↓
UserAnnotationAgreement records created
        ↓
Query functions available:
  - get_agreement_summary_for_audio()
  - get_disagreement_segments_for_audio()
  - get_all_user_pairs_for_audio()
        ↓
Display in UI / Export via utility script
```

---

##  Testing

### 1. Test Database Setup
```bash
# Initialize database (creates new tables)
python -c "from backend.database import init_db; init_db()"
```

### 2. Test Manual Recording
```python
from backend.database import get_db_session, ProcessingJobLogger
import uuid

db = get_db_session()
user_id = str(uuid.uuid4())
audio_hash = "test123abc456"

with ProcessingJobLogger(
    original_filename="test.wav",
    processing_method="surrogate_replace",
    user_session_id=user_id,
    audio_file_hash=audio_hash,
) as logger:
    logger.log_annotation_surrogates([
        {
            'start_sec': 0.0, 'end_sec': 2.5, 'duration_sec': 2.5,
            'gender': 'male', 'label': 'person',
            'surrogate_name': 'english_male_person_voice1',
            'surrogate_path': '/path/to/surrogate.wav',
            'language': 'english'
        }
    ], audio_file_hash=audio_hash)
```

### 3. Test Queries
```bash
# View all audio files (after processing)
python scripts/view_inter_user_agreement.py --list-files

# View summary for specific file
python scripts/view_inter_user_agreement.py --file-hash abc123def456

# View disagreements
python scripts/view_inter_user_agreement.py --file-hash abc123def456 --disagreements
```

---

##  Deployment Checklist

- [ ] Database migrations/initialization scripts added
- [ ] `gradio_app.py` updated with user_session_id generation
- [ ] Audio file hashing implemented in audio processing
- [ ] ProcessingJobLogger calls updated with audio_file_hash
- [ ] Inter-user agreement display added to UI
- [ ] Utility script (view_inter_user_agreement.py) deployed
- [ ] Database backups configured
- [ ] Schema documentation added to README

---

##  Summary

**What's Ready**: Complete database infrastructure for inter-user annotation tracking with:
- Table schema for storing comparisons
- Query functions for analysis
- Automatic comparison generation
- Utility script for viewing metrics
- Full documentation

**What's Pending**: Integration with Gradio app UI to:
- Generate and pass user_session_id
- Calculate and pass audio_file_hash
- Display agreement metrics in interface
- Optionally provide query UI for analysis

**Estimated Implementation Time**: 30-60 minutes for full integration
