# Inter-Annotator Agreement System

## Overview

This system enables you to:
1. **Distribute same audio files to multiple users** for annotation
2. **Track individual PII segments** (start/end timestamps, gender, type) per user
3. **Calculate inter-annotator agreement** to measure annotation consistency
4. **Identify missed PII** segments across annotators
5. **Quality control** - flag low-agreement segments for review

## Database Architecture

### Core Tables

#### 1. `processing_jobs`
Tracks each processing session by a user:
- `id`: Unique job identifier
- `user_session_id`: UUID identifying the user/session
- `original_filename`: Input audio filename
- `created_at`: Timestamp of annotation
- `status`: completed/failed/processing
- Other metadata (file size, duration, etc.)

#### 2. `annotation_surrogates`
**Critical table** - stores individual PII segments:
```sql
- id: Primary key
- processing_job_id: Links to processing_jobs
- audio_file_hash: SHA256 hash of audio (enables inter-user matching)
- start_sec: PII start timestamp
- end_sec: PII end timestamp
- duration_sec: Segment duration
- gender: 'male' | 'female'
- label: 'PERSON' | 'LOCATION' | 'USER_ID'
- language: 'english' | others
- surrogate_name: Which surrogate was used
- created_at: Annotation timestamp
```

**Key Feature**: `audio_file_hash` allows comparing annotations from different users on the **same audio file**.

#### 3. `user_annotation_agreements`
Stores pairwise comparisons between users:
- Automatically populated when 2+ users annotate same audio
- Tracks gender_match, label_match, time_overlap_percent
- Agreement levels: 'complete', 'partial', 'none'

## How It Works

### Step 1: Audio File Hashing
When a user uploads audio, the system computes a SHA256 hash:
```python
import hashlib
audio_hash = hashlib.sha256(audio_bytes).hexdigest()
```

This hash uniquely identifies the audio content (not filename), so:
- Same audio uploaded by different users → Same hash
- Enables matching across users/sessions

### Step 2: Recording Annotations
Each user's annotations are stored in `annotation_surrogates`:

**User A annotates file:**
```
audio_hash: abc123...
user_session_id: user-a-uuid
Segments:
  - start: 2.5s, end: 4.3s, gender: male, label: PERSON
  - start: 8.1s, end: 10.2s, gender: female, label: LOCATION
```

**User B annotates same file:**
```
audio_hash: abc123...  (same hash!)
user_session_id: user-b-uuid
Segments:
  - start: 2.4s, end: 4.4s, gender: male, label: PERSON
  - start: 8.0s, end: 10.3s, gender: female, label: LOCATION
  - start: 15.2s, end: 16.5s, gender: male, label: PERSON  (extra segment!)
```

### Step 3: Computing Agreement
The system automatically compares annotations:

```python
from backend.database import compare_user_annotations, get_db_session

db = get_db_session()
agreements = compare_user_annotations(db, audio_hash, filename)
```

**Agreement Metrics:**
- **IoU (Intersection over Union)**: How much time segments overlap
- **Gender Agreement**: % of matched segments with same gender
- **Label Agreement**: % of matched segments with same PII type
- **Timestamp Deviation**: Average difference in start/end times
- **Missed PII**: Segments detected by one user but not others

## Usage Guide

### 1. Distribute Files to Users

**Get files ready for additional annotations:**
```python
from scripts.inter_annotator_agreement import get_files_for_distribution

# Find files with 1-2 annotations (need more users)
files_df = get_files_for_distribution(
    db,
    min_annotations=1,
    max_annotations=3
)

print(files_df)
# Output:
#   audio_hash    filename         annotators  segments  
#   abc123...     call_001.wav     1          5
#   def456...     call_002.wav     2          8
```

**Action**: Send these files to additional annotators.

### 2. Run Agreement Analysis

**Generate full inter-annotator report:**
```bash
cd /home/beijuka/Bruno/MARCONI_LAB/MHDP/audio-anonymization-platform
python3 scripts/inter_annotator_agreement.py
```

**Output:** `inter_annotator_agreement_YYYYMMDD_HHMMSS.csv`

Example report:
```csv
audio_hash,filename,user1_id,user2_id,matched_segments,gender_agreement_%,label_agreement_%,avg_iou,user1_missed,user2_missed
abc123...,call_001.wav,a1b2c3d4,e5f6g7h8,5,100.0,100.0,0.875,0,1
def456...,call_002.wav,a1b2c3d4,i9j0k1l2,8,87.5,87.5,0.823,2,1
```

**Key Columns:**
- `matched_segments`: How many PII segments both users found
- `gender_agreement_%`: % agreement on gender classification
- `label_agreement_%`: % agreement on PII type
- `avg_iou`: Average overlap quality (1.0 = perfect alignment)
- `user1_missed`: PII detected by user2 but not user1
- `user2_missed`: PII detected by user1 but not user2

### 3. Identify Missed PII

```python
from scripts.inter_annotator_agreement import find_missed_pii_segments

missed = find_missed_pii_segments(db, audio_hash)

for seg in missed:
    print(f"⚠️  PII at {seg['start_sec']:.1f}s-{seg['end_sec']:.1f}s")
    print(f"    Detected by: {seg['detected_by']}")
    print(f"    Missed by: {seg['missed_by']}")
    print(f"    Type: {seg['label']}, Gender: {seg['gender']}")
```

### 4. SQL Queries for Analysis

**Get all users who annotated a specific audio:**
```sql
SELECT 
    p.user_session_id,
    p.original_filename,
    COUNT(a.id) as segment_count,
    p.created_at
FROM processing_jobs p
JOIN annotation_surrogates a ON p.id = a.processing_job_id
WHERE a.audio_file_hash = 'YOUR_AUDIO_HASH_HERE'
GROUP BY p.user_session_id, p.original_filename, p.created_at;
```

**Find files with low agreement:**
```sql
SELECT 
    audio_filename,
    audio_file_hash,
    COUNT(*) as comparison_count,
    AVG(CASE WHEN agreement_level = 'complete' THEN 1.0 ELSE 0.0 END) as complete_rate,
    AVG(time_overlap_percent) as avg_overlap
FROM user_annotation_agreements
GROUP BY audio_filename, audio_file_hash
HAVING AVG(CASE WHEN agreement_level = 'complete' THEN 1.0 ELSE 0.0 END) < 0.5
ORDER BY complete_rate ASC;
```

**Get timestamp deviation statistics:**
```sql
SELECT 
    a1.audio_file_hash,
    p1.original_filename,
    ABS(a1.start_sec - a2.start_sec) as start_diff,
    ABS(a1.end_sec - a2.end_sec) as end_diff
FROM annotation_surrogates a1
JOIN annotation_surrogates a2 ON a1.audio_file_hash = a2.audio_file_hash
    AND a1.id < a2.id  -- Avoid duplicate pairs
JOIN processing_jobs p1 ON a1.processing_job_id = p1.id
JOIN processing_jobs p2 ON a2.processing_job_id = p2.id
WHERE p1.user_session_id != p2.user_session_id
    AND ABS(a1.start_sec - a2.start_sec) < 1.0  -- Within 1 second
ORDER BY start_diff DESC;
```

## Workflow Example

### Multi-User Annotation Workflow

**Phase 1: Initial Annotation**
1. User A uploads `sensitive_call.wav`
2. System computes hash: `a7f8...`
3. User A annotates 3 PII segments
4. Data stored in `annotation_surrogates` with hash

**Phase 2: Second Annotator**
1. Admin distributes same `sensitive_call.wav` to User B
2. User B uploads (system recognizes same hash!)
3. User B annotates independently
4. System auto-computes agreement in `user_annotation_agreements`

**Phase 3: Quality Review**
1. Run agreement analysis script
2. Review segments with <80% agreement
3. Identify missed PII (detected by only 1 user)
4. Assign to User C for tie-breaker annotation

**Phase 4: Final Consensus**
1. Keep segments where 2+ users agree
2. Flag disagreements for expert review
3. Update "ground truth" annotations

## Best Practices

### 1. User Session Management
- Each annotator gets unique `user_session_id` (UUID)
- Never reuse session IDs across users
- Track user identities separately for privacy

### 2. File Distribution
- Distribute same audio to 2-3 users minimum
- More users = better reliability metrics
- Use `get_files_for_distribution()` to automate

### 3. Agreement Thresholds
- **IoU ≥ 0.8**: High agreement (excellent)
- **IoU 0.5-0.8**: Moderate agreement (acceptable)
- **IoU < 0.5**: Low agreement (needs review)
- **Gender/Label agreement < 70%**: Flag for review

### 4. Timestamp Tolerance
- Start/End deviation < 0.5s: Excellent
- Deviation 0.5-1.0s: Acceptable
- Deviation > 1.0s: Investigate (different segments?)

### 5. Missed PII Handling
- If 1 user finds PII others missed:
  - Could be false positive (user A wrong)
  - Could be missed PII (others wrong)
  - → Require 3rd annotator to resolve

## Metrics & Interpretation

### Cohen's Kappa (Future)
Planned extension for chance-corrected agreement:
```
κ = (p_observed - p_expected) / (1 - p_expected)
```
- κ > 0.8: Excellent agreement
- κ 0.6-0.8: Good agreement
- κ < 0.6: Poor agreement

### F1 Score Per Annotator
Measure annotation quality against consensus:
```
Precision = TP / (TP + FP)  # Correct PII / All detected PII
Recall = TP / (TP + FN)     # Correct PII / All actual PII
F1 = 2 * (Precision * Recall) / (Precision + Recall)
```

## Troubleshooting

### Issue: "No audio_file_hash in database"
**Cause**: Old annotations before hash feature was added
**Fix**: Update `annotation_surrogates` to add hashes for existing jobs:
```sql
UPDATE annotation_surrogates a
SET audio_file_hash = 'manually_computed_hash'
WHERE audio_file_hash IS NULL
  AND processing_job_id IN (
    SELECT id FROM processing_jobs 
    WHERE original_filename = 'specific_file.wav'
  );
```

### Issue: "Same file, different hashes"
**Cause**: File was modified/converted between annotations
**Fix**: Use canonical audio format (e.g., always convert to WAV before hashing)

### Issue: "No agreement comparisons generated"
**Cause**: `audio_file_hash` not set when logging annotations
**Fix**: Verify Gradio app calls `compute_audio_hash()` and passes to logger

## Python API Examples

### Example 1: Get User's Annotation Quality
```python
from scripts.inter_annotator_agreement import get_user_annotations, calculate_agreement_metrics

# Get annotations from two users
user1_anns = get_user_annotations(db, audio_hash)['user-uuid-1']
user2_anns = get_user_annotations(db, audio_hash)['user-uuid-2']

# Calculate metrics
metrics = calculate_agreement_metrics(user1_anns, user2_anns)

print(f"Gender Agreement: {metrics['gender_agreement']*100:.1f}%")
print(f"User1 Missed: {metrics['user2_only_segments']} segments")
print(f"User2 Missed: {metrics['user1_only_segments']} segments")
```

### Example 2: Export Report for Specific Files
```python
from scripts.inter_annotator_agreement import generate_agreement_report

# Generate report for specific audio
report_df = generate_agreement_report(db, audio_file_hash='abc123...')
report_df.to_csv('specific_file_agreement.csv', index=False)
```

### Example 3: Batch Analysis
```python
# Get all files needing review (low agreement)
query = """
SELECT DISTINCT audio_file_hash, audio_filename
FROM user_annotation_agreements
WHERE agreement_level = 'none'
   OR time_overlap_percent < 50
"""
results = db.execute(query).fetchall()

for hash_val, filename in results:
    print(f"❌ {filename} needs review")
    missed = find_missed_pii_segments(db, hash_val)
    print(f"   Potential missed PII: {len(missed)} segments")
```

## Next Steps

1. **Run database migrations**: `python backend/migrations.py`
2. **Test with sample audio**: Upload same file twice with different user_session_ids
3. **Generate first report**: `python scripts/inter_annotator_agreement.py`
4. **Review results**: Check for missed PII and low agreement
5. **Distribute files**: Use dashboard to assign files to multiple annotators

## References

- Database schema: `backend/database.py`
- Logging implementation: `backend/db_logger.py`
- Analysis tools: `scripts/inter_annotator_agreement.py`
- Gradio app integration: `app/gradio_app.py`
