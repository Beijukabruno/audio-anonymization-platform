-- ============================================================================
-- Inter-Annotator Agreement SQL Queries
-- Audio Anonymization Platform
-- ============================================================================

-- Query 1: Get all audio files with multiple annotators
-- Use this to see which files have been annotated by 2+ users
SELECT 
    a.audio_file_hash,
    p.original_filename,
    COUNT(DISTINCT p.user_session_id) as num_annotators,
    COUNT(a.id) as total_segments,
    MIN(p.created_at) as first_annotation,
    MAX(p.created_at) as last_annotation,
    STRING_AGG(DISTINCT SUBSTRING(p.user_session_id, 1, 8), ', ' ORDER BY SUBSTRING(p.user_session_id, 1, 8)) as annotator_ids
FROM annotation_surrogates a
JOIN processing_jobs p ON a.processing_job_id = p.id
WHERE a.audio_file_hash IS NOT NULL
GROUP BY a.audio_file_hash, p.original_filename
HAVING COUNT(DISTINCT p.user_session_id) >= 2
ORDER BY COUNT(DISTINCT p.user_session_id) DESC, p.original_filename;


-- Query 2: Get detailed annotations for a specific audio file
-- Replace 'YOUR_AUDIO_HASH' with actual hash
SELECT 
    SUBSTRING(p.user_session_id, 1, 8) as user_id,
    a.start_sec,
    a.end_sec,
    a.duration_sec,
    a.gender,
    a.label,
    a.language,
    a.surrogate_name,
    a.created_at
FROM annotation_surrogates a
JOIN processing_jobs p ON a.processing_job_id = p.id
WHERE a.audio_file_hash = 'YOUR_AUDIO_HASH'
ORDER BY p.user_session_id, a.start_sec;


-- Query 3: Find timestamp deviations for same audio across users
-- This shows where users marked different start/end times for similar segments
SELECT 
    p1.original_filename,
    SUBSTRING(p1.user_session_id, 1, 8) as user1_id,
    SUBSTRING(p2.user_session_id, 1, 8) as user2_id,
    a1.start_sec as user1_start,
    a2.start_sec as user2_start,
    ABS(a1.start_sec - a2.start_sec) as start_deviation_sec,
    a1.end_sec as user1_end,
    a2.end_sec as user2_end,
    ABS(a1.end_sec - a2.end_sec) as end_deviation_sec,
    a1.gender as user1_gender,
    a2.gender as user2_gender,
    a1.label as user1_label,
    a2.label as user2_label
FROM annotation_surrogates a1
JOIN annotation_surrogates a2 ON a1.audio_file_hash = a2.audio_file_hash
JOIN processing_jobs p1 ON a1.processing_job_id = p1.id
JOIN processing_jobs p2 ON a2.processing_job_id = p2.id
WHERE p1.user_session_id < p2.user_session_id  -- Avoid duplicate pairs
    AND ABS(a1.start_sec - a2.start_sec) < 2.0  -- Within 2 seconds (likely same segment)
    AND a1.audio_file_hash IS NOT NULL
ORDER BY start_deviation_sec DESC
LIMIT 50;


-- Query 4: Get agreement statistics per audio file
SELECT 
    audio_filename,
    COUNT(*) as total_comparisons,
    SUM(CASE WHEN agreement_level = 'complete' THEN 1 ELSE 0 END) as complete_agreements,
    SUM(CASE WHEN agreement_level = 'partial' THEN 1 ELSE 0 END) as partial_agreements,
    SUM(CASE WHEN agreement_level = 'none' THEN 1 ELSE 0 END) as no_agreements,
    ROUND(AVG(time_overlap_percent), 2) as avg_overlap_percent,
    ROUND(AVG(CASE WHEN gender_match THEN 100.0 ELSE 0.0 END), 2) as gender_agreement_percent,
    ROUND(AVG(CASE WHEN label_match THEN 100.0 ELSE 0.0 END), 2) as label_agreement_percent
FROM user_annotation_agreements
GROUP BY audio_filename
ORDER BY complete_agreements DESC, audio_filename;


-- Query 5: Find files with LOW agreement (need review)
SELECT 
    audio_filename,
    audio_file_hash,
    COUNT(*) as comparisons,
    ROUND(AVG(CASE WHEN agreement_level = 'complete' THEN 1.0 ELSE 0.0 END) * 100, 1) as complete_rate,
    ROUND(AVG(time_overlap_percent), 2) as avg_overlap,
    STRING_AGG(DISTINCT user1_session_id || '<->' || user2_session_id, ', ') as user_pairs
FROM user_annotation_agreements
GROUP BY audio_filename, audio_file_hash
HAVING AVG(CASE WHEN agreement_level = 'complete' THEN 1.0 ELSE 0.0 END) < 0.7
ORDER BY complete_rate ASC
LIMIT 20;


-- Query 6: Get per-user annotation statistics
SELECT 
    SUBSTRING(p.user_session_id, 1, 8) as user_id,
    COUNT(DISTINCT p.id) as sessions,
    COUNT(DISTINCT a.audio_file_hash) as unique_files_annotated,
    COUNT(a.id) as total_segments_marked,
    ROUND(AVG(a.duration_sec), 2) as avg_segment_duration,
    MIN(p.created_at) as first_annotation_date,
    MAX(p.created_at) as last_annotation_date
FROM processing_jobs p
JOIN annotation_surrogates a ON p.id = a.processing_job_id
WHERE a.audio_file_hash IS NOT NULL
GROUP BY p.user_session_id
ORDER BY COUNT(a.id) DESC;


-- Query 7: Find potential MISSED PII segments
-- Shows segments detected by one user but not others on same audio
WITH user_segments AS (
    SELECT 
        a.audio_file_hash,
        p.user_session_id,
        a.start_sec,
        a.end_sec,
        a.gender,
        a.label
    FROM annotation_surrogates a
    JOIN processing_jobs p ON a.processing_job_id = p.id
    WHERE a.audio_file_hash IN (
        -- Only for files with multiple annotators
        SELECT audio_file_hash
        FROM annotation_surrogates
        WHERE audio_file_hash IS NOT NULL
        GROUP BY audio_file_hash
        HAVING COUNT(DISTINCT processing_job_id) >= 2
    )
)
SELECT 
    u1.audio_file_hash,
    SUBSTRING(u1.user_session_id, 1, 8) as detected_by_user,
    u1.start_sec,
    u1.end_sec,
    u1.gender,
    u1.label,
    COUNT(DISTINCT u2.user_session_id) + 1 as total_annotators,
    COUNT(DISTINCT CASE 
        WHEN ABS(u2.start_sec - u1.start_sec) < 1.0 
        THEN u2.user_session_id 
    END) as users_who_found_it
FROM user_segments u1
LEFT JOIN user_segments u2 ON u1.audio_file_hash = u2.audio_file_hash
    AND u1.user_session_id != u2.user_session_id
GROUP BY u1.audio_file_hash, u1.user_session_id, u1.start_sec, u1.end_sec, u1.gender, u1.label
HAVING COUNT(DISTINCT CASE 
    WHEN ABS(u2.start_sec - u1.start_sec) < 1.0 
    THEN u2.user_session_id 
END) = 0  -- Found by only this user
ORDER BY u1.audio_file_hash, u1.start_sec
LIMIT 50;


-- Query 8: Gender classification disagreements
-- Find segments where users disagreed on gender
SELECT 
    p1.original_filename,
    SUBSTRING(p1.user_session_id, 1, 8) as user1,
    SUBSTRING(p2.user_session_id, 1, 8) as user2,
    ROUND(AVG((a1.start_sec + a2.start_sec) / 2.0), 2) as avg_start_time,
    a1.gender as user1_gender,
    a2.gender as user2_gender,
    a1.label as type
FROM annotation_surrogates a1
JOIN annotation_surrogates a2 ON a1.audio_file_hash = a2.audio_file_hash
JOIN processing_jobs p1 ON a1.processing_job_id = p1.id
JOIN processing_jobs p2 ON a2.processing_job_id = p2.id
WHERE p1.user_session_id < p2.user_session_id
    AND ABS(a1.start_sec - a2.start_sec) < 1.0  -- Same segment
    AND a1.gender != a2.gender  -- Different gender classification
ORDER BY p1.original_filename, avg_start_time;


-- Query 9: PII type (label) disagreements
SELECT 
    p1.original_filename,
    SUBSTRING(p1.user_session_id, 1, 8) as user1,
    SUBSTRING(p2.user_session_id, 1, 8) as user2,
    ROUND(AVG((a1.start_sec + a2.start_sec) / 2.0), 2) as avg_start_time,
    a1.label as user1_label,
    a2.label as user2_label,
    a1.gender
FROM annotation_surrogates a1
JOIN annotation_surrogates a2 ON a1.audio_file_hash = a2.audio_file_hash
JOIN processing_jobs p1 ON a1.processing_job_id = p1.id
JOIN processing_jobs p2 ON a2.processing_job_id = p2.id
WHERE p1.user_session_id < p2.user_session_id
    AND ABS(a1.start_sec - a2.start_sec) < 1.0
    AND a1.label != a2.label
ORDER BY p1.original_filename, avg_start_time;


-- Query 10: Files ready for more annotators
-- Shows files that have been annotated but need additional users
SELECT 
    a.audio_file_hash,
    p.original_filename,
    COUNT(DISTINCT p.user_session_id) as current_annotators,
    COUNT(a.id) as total_segments,
    MAX(p.created_at) as last_annotation_date,
    ROUND(AVG(a.duration_sec), 2) as avg_segment_duration
FROM annotation_surrogates a
JOIN processing_jobs p ON a.processing_job_id = p.id
WHERE a.audio_file_hash IS NOT NULL
    AND p.status = 'completed'
GROUP BY a.audio_file_hash, p.original_filename
HAVING COUNT(DISTINCT p.user_session_id) >= 1
    AND COUNT(DISTINCT p.user_session_id) < 3  -- Want at least 3 annotators
ORDER BY COUNT(DISTINCT p.user_session_id) ASC, MAX(p.created_at) DESC
LIMIT 20;


-- Query 11: User pair agreement matrix
-- Shows agreement rates between each pair of users
SELECT 
    SUBSTRING(user1_session_id, 1, 8) as user1,
    SUBSTRING(user2_session_id, 1, 8) as user2,
    COUNT(*) as total_comparisons,
    ROUND(AVG(CASE WHEN agreement_level = 'complete' THEN 1.0 ELSE 0.0 END) * 100, 1) as complete_percent,
    ROUND(AVG(CASE WHEN gender_match THEN 1.0 ELSE 0.0 END) * 100, 1) as gender_agreement_percent,
    ROUND(AVG(CASE WHEN label_match THEN 1.0 ELSE 0.0 END) * 100, 1) as label_agreement_percent,
    ROUND(AVG(time_overlap_percent), 2) as avg_overlap
FROM user_annotation_agreements
GROUP BY user1_session_id, user2_session_id
ORDER BY complete_percent DESC;


-- Query 12: Timeline of annotations per audio file
SELECT 
    p.original_filename,
    a.audio_file_hash,
    SUBSTRING(p.user_session_id, 1, 8) as user_id,
    p.created_at as annotation_timestamp,
    COUNT(a.id) as segments_marked,
    STRING_AGG(DISTINCT a.label, ', ' ORDER BY a.label) as pii_types_found
FROM processing_jobs p
JOIN annotation_surrogates a ON p.id = a.processing_job_id
WHERE a.audio_file_hash IS NOT NULL
GROUP BY p.original_filename, a.audio_file_hash, p.user_session_id, p.created_at
ORDER BY a.audio_file_hash, p.created_at;


-- ============================================================================
-- EXAMPLE USAGE
-- ============================================================================

-- To run a specific query, copy it into your PostgreSQL client or use psql:
--   psql -U audio_user -d audio_anony -f inter_annotator_queries.sql

-- To save results to CSV:
--   \copy (SELECT ...) TO '/path/to/output.csv' WITH CSV HEADER;

-- To connect via Python:
--   from backend.database import get_db_session
--   db = get_db_session()
--   result = db.execute("YOUR SQL HERE")
--   for row in result:
--       print(row)
