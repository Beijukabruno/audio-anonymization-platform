# Inter-User Annotation Agreement Tracking

## Overview

The audio anonymization platform now supports tracking how different users annotate the same audio file. This enables measurement of inter-user agreement, identification of disagreement segments, and support for collaborative annotation workflows.

## Database Schema

### New Tables

#### `UserAnnotationAgreement` Table
Stores comparisons between annotations from different users on the same audio segment.

**Key Fields:**
- `audio_file_hash`: Hash of the audio file being annotated (enables tracking same file)
- `segment_start_sec`, `segment_end_sec`: Time range being annotated
- `user1_session_id`, `user2_session_id`: Unique identifiers for users
- `user1_gender`, `user1_label`, `user1_surrogate`: User 1's choices
- `user2_gender`, `user2_label`, `user2_surrogate`: User 2's choices
- `gender_match`, `label_match`, `surrogate_match`: Boolean fields showing agreement on each attribute
- `agreement_level`: Overall agreement ('complete', 'partial', 'none')
- `time_overlap_percent`: How much the time ranges overlap (0-100%)

### Extended Tables

#### `ProcessingJob` Extended Fields
- `user_session_id`: Unique user identifier (required for inter-user tracking)
- `audio_file_hash`: Hash of original file (enables linking annotations across users)

#### `AnnotationSurrogate` Extended Fields  
- `audio_file_hash`: Hash of audio file (links to other users' annotations of same file)

## Helper Functions

### `compare_user_annotations(db, audio_file_hash, audio_filename)`
Main function to generate inter-user agreement comparisons.

**Returns:** List of `UserAnnotationAgreement` records

```python
from backend.database import compare_user_annotations

agreements = compare_user_annotations(db, audio_hash, "speech.wav")
for agreement in agreements:
    print(f"Segment {agreement.segment_start_sec:.1f}s-{agreement.segment_end_sec:.1f}s: {agreement.agreement_level}")
    print(f"  User1 chose: {agreement.user1_gender} + {agreement.user1_label} + {agreement.user1_surrogate}")
    print(f"  User2 chose: {agreement.user2_gender} + {agreement.user2_label} + {agreement.user2_surrogate}")
```

### `get_agreement_summary_for_audio(db, audio_file_hash)`
Get summary statistics for an audio file.

**Returns:** Dictionary with:
- `total_comparisons`: How many segment pairs were compared
- `complete_agreement`: Segments where users matched all 3 attributes
- `partial_agreement`: Segments where users matched some attributes
- `no_agreement`: Segments where users matched no attributes
- `complete_percent`: Percentage of complete agreements
- `avg_overlap_percent`: Average time overlap percentage

```python
from backend.database import get_agreement_summary_for_audio

summary = get_agreement_summary_for_audio(db, audio_hash)
print(f"Complete agreement: {summary['complete_percent']}%")
```

### `get_all_user_pairs_for_audio(db, audio_file_hash)`
Get all unique user pairs who annotated the same file.

**Returns:** List of dictionaries with:
- `user1`, `user2`: Session IDs
- `total_comparisons`: Number of compared segments
- `complete_agreement`: Count of complete agreements
- `agreement_percent`: Percentage of complete agreements

### `get_user_annotations_for_audio(db, audio_file_hash, user_session_id)`
Get all annotations from a specific user for a file.

**Returns:** List of `AnnotationSurrogate` records

### `get_disagreement_segments_for_audio(db, audio_file_hash)`
Get all segments where users disagreed.

**Returns:** List of `UserAnnotationAgreement` records filtered to non-complete agreements

## Workflow

### Step 1: Capture User Identifier
When a user uploads audio, capture a unique session ID:

```python
import uuid
from datetime import datetime

# In gradio_app.py
user_session_id = str(uuid.uuid4())  # Or use username/email if available
audio_filename = "speech.wav"

# Calculate hash of uploaded file
import hashlib
with open(audio_path, 'rb') as f:
    audio_file_hash = hashlib.sha256(f.read()).hexdigest()[:16]
```

### Step 2: Store Annotations with User ID
When logging annotations to database:

```python
from backend.db_logger import ProcessingJobLogger

with ProcessingJobLogger(
    user_session_id=user_session_id,
    original_filename=audio_filename,
    # ... other fields
) as logger:
    # Process audio and create annotations
    logger.log_annotation_surrogates(
        annotations=[...],  # List of Annotation objects
        processing_job_id=job.id,
        audio_file_hash=audio_file_hash,  # Important for tracking
    )
```

### Step 3: Compare Annotations
After multiple users have annotated the same file:

```python
from backend.database import compare_user_annotations

agreements = compare_user_annotations(db, audio_file_hash, audio_filename)

# Display results
for agreement in agreements:
    status = " " if agreement.agreement_level == "complete" else " "
    print(f"{status} {agreement.segment_start_sec:.1f}s-{agreement.segment_end_sec:.1f}s: {agreement.agreement_level}")
```

### Step 4: View Summary
Get overview of agreement on a file:

```python
from backend.database import get_agreement_summary_for_audio

summary = get_agreement_summary_for_audio(db, audio_file_hash)
print(f"Total segments compared: {summary['total_comparisons']}")
print(f"Complete agreement: {summary['complete_agreement']} ({summary['complete_percent']}%)")
print(f"Partial agreement: {summary['partial_agreement']}")
print(f"No agreement: {summary['no_agreement']}")
```

## Implementation Notes

### Agreement Levels
1. **Complete**: Both users chose same gender, label, AND surrogate
2. **Partial**: Both users chose same gender and label, but different surrogates
3. **None**: Users differed on gender or label

### Time Overlap
- Only segments with 20%+ time overlap are compared
- Overlap percentage is calculated as: `(time_intersection / total_time_span) × 100`
- This prevents comparing completely disjoint time ranges

### User Session ID
- Each user should have a unique `user_session_id`
- Options:
  - Generate UUID for each session
  - Use username if logged in
  - Use email
  - Use combination of username + timestamp
- **IMPORTANT**: Same user in multiple sessions = different user_session_id (can track individual session agreement)

### Audio File Hash
- Use SHA256 or MD5 hash of original audio file
- Enables tracking same file across users
- Example:
  ```python
  import hashlib
  with open(audio_file_path, 'rb') as f:
      audio_file_hash = hashlib.sha256(f.read()).hexdigest()[:16]
  ```

## Integration with Gradio App

### Required Changes to `gradio_app.py`

1. **Import new functions:**
   ```python
   from backend.database import (
       compare_user_annotations,
       get_agreement_summary_for_audio,
       get_user_annotations_for_audio,
   )
   ```

2. **Generate user session ID on startup:**
   ```python
   import uuid
   USER_SESSION_ID = str(uuid.uuid4())
   ```

3. **Calculate audio file hash when uploading:**
   ```python
   import hashlib
   
   def process_audio(audio_file):
       # ... existing code ...
       
       # Calculate hash for inter-user tracking
       audio_hash = hashlib.sha256(audio_file.read()).hexdigest()[:16]
       
       # ... rest of processing ...
   ```

4. **Pass audio_file_hash to database logger:**
   ```python
   with ProcessingJobLogger(
       user_session_id=USER_SESSION_ID,
       original_filename=filename,
       # ... other fields ...
   ) as logger:
       # ... processing ...
       logger.log_annotation_surrogates(
           annotations=annotations,
           processing_job_id=job.id,
           audio_file_hash=audio_hash,  # NEW
       )
   ```

5. **Display inter-user agreement in UI:**
   ```python
   # After processing
   summary = get_agreement_summary_for_audio(db, audio_hash)
   
   gr.Markdown(f"""
   ### Inter-User Agreement (if multiple users processed this file)
   - Complete Agreement: {summary['complete_agreement']} segments
   - Partial Agreement: {summary['partial_agreement']} segments
   - Disagreement: {summary['no_agreement']} segments
   - Overall: {summary['complete_percent']}% agreement
   """)
   ```

## Example Queries

### Find all audio files with >2 annotators
```python
from backend.database import SessionLocal
from sqlalchemy import func

db = SessionLocal()
files_with_multiple_users = db.query(
    AnnotationSurrogate.audio_file_hash,
    func.count(func.distinct(ProcessingJob.user_session_id)).label('user_count')
).join(
    ProcessingJob, AnnotationSurrogate.processing_job_id == ProcessingJob.id
).group_by(
    AnnotationSurrogate.audio_file_hash
).filter(
    func.count(func.distinct(ProcessingJob.user_session_id)) >= 2
).all()
```

### Get all high-agreement files (>80% agreement)
```python
from backend.database import get_agreement_summary_for_audio

for file_hash in file_hashes:
    summary = get_agreement_summary_for_audio(db, file_hash)
    if summary['complete_percent'] >= 80:
        print(f"High agreement file: {file_hash}")
```

### Get disagreement segments for manual review
```python
from backend.database import get_disagreement_segments_for_audio

disagreements = get_disagreement_segments_for_audio(db, audio_hash)
for disagreement in disagreements:
    print(f"Segment {disagreement.segment_start_sec:.1f}s-{disagreement.segment_end_sec:.1f}s:")
    print(f"  User1: {disagreement.user1_label} ({disagreement.user1_gender})")
    print(f"  User2: {disagreement.user2_label} ({disagreement.user2_gender})")
    print(f"  Overlap: {disagreement.time_overlap_percent:.1f}%")
```

## Status

 Database schema created
 Helper functions implemented
⏳ Integration with gradio_app.py (pending)
⏳ UI display features (pending)

## Next Steps

1. Update `gradio_app.py` to generate and use user_session_id
2. Update `db_logger.py` to accept and store audio_file_hash
3. Add inter-user agreement summary display in Gradio UI
4. Create query UI for viewing agreement metrics
5. Add export function for agreement reports
