#!/usr/bin/env python3
"""
Inter-Annotator Agreement Analysis Tool

Purpose:
- Distribute same audio files to multiple users for annotation
- Track individual PII segment annotations (start, end, gender, type)
- Calculate inter-annotator agreement metrics (Cohen's Kappa, F1, IoU)
- Identify missed PII segments across annotators
- Generate quality control reports
"""

import hashlib
import sys
import os
import logging
from typing import Dict, List, Tuple
from collections import defaultdict
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import (
    get_db_session,
    ProcessingJob,
    AnnotationSurrogate,
   UserAnnotationAgreement,
    compare_user_annotations,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)


def compute_audio_hash(audio_bytes: bytes) -> str:
    """
    Compute SHA256 hash of audio file for tracking.
    
    Args:
        audio_bytes: Raw audio file bytes
    
    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(audio_bytes).hexdigest()


def get_files_for_distribution(db: Session, min_annotations: int = 1, max_annotations: int = 3) -> pd.DataFrame:
    """
    Get list of audio files suitable for distributing to additional annotators.
    
    Args:
        db: Database session
        min_annotations: Minimum annotations already completed
        max_annotations: Maximum annotations (stop distributing after this)
    
    Returns:
        DataFrame with files ready for distribution
    """
    # Query to count annotations per audio file
    query = """
    SELECT 
        a.audio_file_hash,
        p.original_filename,
        COUNT(DISTINCT p.user_session_id) as annotator_count,
        COUNT(a.id) as segment_count,
        MIN(p.created_at) as first_annotation_date,
        MAX(p.created_at) as last_annotation_date
    FROM annotation_surrogates a
    JOIN processing_jobs p ON a.processing_job_id = p.id
    WHERE a.audio_file_hash IS NOT NULL
      AND p.status = 'completed'
    GROUP BY a.audio_file_hash, p.original_filename
    HAVING COUNT(DISTINCT p.user_session_id) >= :min_ann
      AND COUNT(DISTINCT p.user_session_id) < :max_ann
    ORDER BY COUNT(DISTINCT p.user_session_id) ASC, MIN(p.created_at) DESC
    """
    
    result = db.execute(query, {"min_ann": min_annotations, "max_ann": max_annotations})
    
    data = []
    for row in result:
        data.append({
            "audio_hash": row[0],
            "filename": row[1],
            "annotators": row[2],
            "segments": row[3],
            "first_annotation": row[4],
            "last_annotation": row[5],
        })
    
    return pd.DataFrame(data)


def get_user_annotations(db: Session, audio_file_hash: str) -> Dict[str, List[Dict]]:
    """
    Get all annotations from different users for a specific audio file.
    
    Args:
        db: Database session
        audio_file_hash: SHA256 hash of audio file
    
    Returns:
        Dictionary mapping user_session_id to list of their annotations
    """
    # Get all annotations for this audio
    annotations = db.query(AnnotationSurrogate).filter(
        AnnotationSurrogate.audio_file_hash == audio_file_hash
    ).all()
    
    # Get associated user sessions
    user_annotations = defaultdict(list)
    
    for ann in annotations:
        job = db.query(ProcessingJob).filter_by(id=ann.processing_job_id).first()
        if job:
            user_annotations[job.user_session_id].append({
                "annotation_id": ann.id,
                "start_sec": ann.start_sec,
                "end_sec": ann.end_sec,
                "duration_sec": ann.duration_sec,
                "gender": ann.gender,
                "label": ann.label,
                "language": ann.language,
                "surrogate": ann.surrogate_name,
                "created_at": ann.created_at,
            })
    
    return dict(user_annotations)


def compute_iou_for_segments(seg1: Tuple[float, float], seg2: Tuple[float, float]) -> float:
    """
    Compute Intersection over Union (IoU) for two time segments.
    
    Args:
        seg1: (start, end) tuple for first segment
        seg2: (start, end) tuple for second segment
    
    Returns:
        IoU score (0-1)
    """
    start1, end1 = seg1
    start2, end2 = seg2
    
    # Compute intersection
    intersection_start = max(start1, start2)
    intersection_end = min(end1, end2)
    intersection = max(0, intersection_end - intersection_start)
    
    # Compute union
    union_start = min(start1, start2)
    union_end = max(end1, end2)
    union = union_end - union_start
    
    return intersection / union if union > 0 else 0


def calculate_agreement_metrics(user1_anns: List[Dict], user2_anns: List[Dict]) -> Dict:
    """
    Calculate inter-annotator agreement metrics between two users.
    
    Metrics:
    - Segment overlap (IoU-based matching)
    - Gender agreement
    - Label (PII type) agreement
    - Timestamp deviation (for matched segments)
    
    Args:
        user1_anns: List of annotations from user 1
        user2_anns: List of annotations from user 2
    
    Returns:
        Dictionary with agreement metrics
    """
    metrics = {
        "user1_segment_count": len(user1_anns),
        "user2_segment_count": len(user2_anns),
        "matched_segments": 0,
        "gender_agreement": 0,
        "label_agreement": 0,
        "avg_start_deviation_sec": 0,
        "avg_end_deviation_sec": 0,
        "avg_iou": 0,
        "user1_only_segments": 0,  # PII missed by user2
        "user2_only_segments": 0,  # PII missed by user1
    }
    
    if not user1_anns or not user2_anns:
        return metrics
    
    # Match segments based on IoU threshold
    iou_threshold = 0.3  # 30% overlap required to match
    matched_pairs = []
    matched_user1_indices = set()
    matched_user2_indices = set()
    
    for i, ann1 in enumerate(user1_anns):
        best_match_idx = None
        best_iou = 0
        
        for j, ann2 in enumerate(user2_anns):
            if j in matched_user2_indices:
                continue
            
            iou = compute_iou_for_segments(
                (ann1["start_sec"], ann1["end_sec"]),
                (ann2["start_sec"], ann2["end_sec"])
            )
            
            if iou > best_iou and iou >= iou_threshold:
                best_iou = iou
                best_match_idx = j
        
        if best_match_idx is not None:
            matched_pairs.append((i, best_match_idx, best_iou))
            matched_user1_indices.add(i)
            matched_user2_indices.add(best_match_idx)
    
    # Calculate metrics for matched segments
    metrics["matched_segments"] = len(matched_pairs)
    
    if matched_pairs:
        gender_matches = 0
        label_matches = 0
        start_deviations = []
        end_deviations = []
        ious = []
        
        for i, j, iou in matched_pairs:
            ann1 = user1_anns[i]
            ann2 = user2_anns[j]
            
            if ann1["gender"] == ann2["gender"]:
                gender_matches += 1
            
            if ann1["label"] == ann2["label"]:
                label_matches += 1
            
            start_deviations.append(abs(ann1["start_sec"] - ann2["start_sec"]))
            end_deviations.append(abs(ann1["end_sec"] - ann2["end_sec"]))
            ious.append(iou)
        
        metrics["gender_agreement"] = gender_matches / len(matched_pairs)
        metrics["label_agreement"] = label_matches / len(matched_pairs)
        metrics["avg_start_deviation_sec"] = sum(start_deviations) / len(start_deviations)
        metrics["avg_end_deviation_sec"] = sum(end_deviations) / len(end_deviations)
        metrics["avg_iou"] = sum(ious) / len(ious)
    
    # Count unmatched segments (potential missed PII)
    metrics["user1_only_segments"] = len(user1_anns) - len(matched_user1_indices)
    metrics["user2_only_segments"] = len(user2_anns) - len(matched_user2_indices)
    
    return metrics


def generate_agreement_report(db: Session, audio_file_hash: str = None) -> pd.DataFrame:
    """
    Generate comprehensive inter-annotator agreement report.
    
    Args:
        db: Database session
        audio_file_hash: Optional specific audio file, or None for all files
    
    Returns:
        DataFrame with agreement statistics per file
    """
    if audio_file_hash:
        audio_hashes = [audio_file_hash]
    else:
        # Get all audio files with multiple annotators
        query = """
        SELECT audio_file_hash
        FROM annotation_surrogates
        WHERE audio_file_hash IS NOT NULL
        GROUP BY audio_file_hash
        HAVING COUNT(DISTINCT processing_job_id) >= 2
        """
        result = db.execute(query)
        audio_hashes = [row[0] for row in result]
    
    report_data = []
    
    for hash_val in audio_hashes:
        user_annotations = get_user_annotations(db, hash_val)
        
        # Get filename
        first_ann = db.query(AnnotationSurrogate).filter_by(audio_file_hash=hash_val).first()
        if not first_ann:
            continue
        
        job = db.query(ProcessingJob).filter_by(id=first_ann.processing_job_id).first()
        filename = job.original_filename if job else "Unknown"
        
        # Compare each pair of users
        users = list(user_annotations.keys())
        for i in range(len(users)):
            for j in range(i + 1, len(users)):
                user1 = users[i]
                user2 = users[j]
                
                metrics = calculate_agreement_metrics(
                    user_annotations[user1],
                    user_annotations[user2]
                )
                
                report_data.append({
                    "audio_hash": hash_val,
                    "filename": filename,
                    "user1_id": user1[:8],  # Truncate for display
                    "user2_id": user2[:8],
                    "user1_segments": metrics["user1_segment_count"],
                    "user2_segments": metrics["user2_segment_count"],
                    "matched_segments": metrics["matched_segments"],
                    "gender_agreement_%": f"{metrics['gender_agreement']*100:.1f}",
                    "label_agreement_%": f"{metrics['label_agreement']*100:.1f}",
                    "avg_iou": f"{metrics['avg_iou']:.3f}",
                    "start_deviation_sec": f"{metrics['avg_start_deviation_sec']:.3f}",
                    "end_deviation_sec": f"{metrics['avg_end_deviation_sec']:.3f}",
                    "user1_missed": metrics["user2_only_segments"],  # PII user1 missed
                    "user2_missed": metrics["user1_only_segments"],  # PII user2 missed
                })
    
    return pd.DataFrame(report_data)


def find_missed_pii_segments(db: Session, audio_file_hash: str) -> List[Dict]:
    """
    Identify PII segments that were detected by some annotators but missed by others.
    
    Args:
        db: Database session
        audio_file_hash: Hash of audio file
    
    Returns:
        List of potentially missed PII segments with details
    """
    user_annotations = get_user_annotations(db, audio_file_hash)
    
    if len(user_annotations) < 2:
        return []
    
    # Find segments that appear in some users' annotations but not others
    missed_segments = []
    users = list(user_annotations.keys())
    
    for user_id, anns in user_annotations.items():
        for ann in anns:
            # Check how many other users detected this segment
            detected_by_count = 1  # Current user
            not_detected_by = []
            
            for other_user in users:
                if other_user == user_id:
                    continue
                
                # Check if any annotation from other user overlaps with this
                other_anns = user_annotations[other_user]
                found = False
                
                for other_ann in other_anns:
                    iou = compute_iou_for_segments(
                        (ann["start_sec"], ann["end_sec"]),
                        (other_ann["start_sec"], other_ann["end_sec"])
                    )
                    if iou >= 0.3:  # 30% overlap threshold
                        found = True
                        detected_by_count += 1
                        break
                
                if not found:
                    not_detected_by.append(other_user[:8])
            
            # If less than half of users detected this, flag it
            if detected_by_count < len(users) / 2:
                missed_segments.append({
                    "detected_by": user_id[:8],
                    "missed_by": ", ".join(not_detected_by),
                    "start_sec": ann["start_sec"],
                    "end_sec": ann["end_sec"],
                    "duration_sec": ann["duration_sec"],
                    "gender": ann["gender"],
                    "label": ann["label"],
                    "detection_rate": f"{detected_by_count}/{len(users)}",
                })
    
    return missed_segments


def export_agreement_report(output_path: str = None):
    """
    Export full inter-annotator agreement report to CSV.
    
    Args:
        output_path: Optional path for output file
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"inter_annotator_agreement_{timestamp}.csv"
    
    db = get_db_session()
    
    try:
        log.info("Generating inter-annotator agreement report...")
        report_df = generate_agreement_report(db)
        
        if report_df.empty:
            log.warning("No multi-user annotations found in database")
            return
        
        report_df.to_csv(output_path, index=False)
        log.info(f"Report exported to: {output_path}")
        log.info(f"Total comparisons: {len(report_df)}")
        
        # Print summary statistics
        print("\n" + "="*80)
        print("INTER-ANNOTATOR AGREEMENT SUMMARY")
        print("="*80)
        print(f"Total audio files: {report_df['audio_hash'].nunique()}")
        print(f"Total user pairs compared: {len(report_df)}")
        print(f"\nAverage Agreement Metrics:")
        
        # Extract numeric values (remove % signs)
        gender_vals = [float(x.replace('%', '')) for x in report_df['gender_agreement_%']]
        label_vals = [float(x.replace('%', '')) for x in report_df['label_agreement_%']]
        iou_vals = [float(x) for x in report_df['avg_iou']]
        
        print(f"  Gender Agreement:  {sum(gender_vals)/len(gender_vals):.1f}%")
        print(f"  Label Agreement:   {sum(label_vals)/len(label_vals):.1f}%")
        print(f"  Average IoU:       {sum(iou_vals)/len(iou_vals):.3f}")
        print(f"\nTimestamp Deviations:")
        start_devs = [float(x) for x in report_df['start_deviation_sec']]
        end_devs = [float(x) for x in report_df['end_deviation_sec']]
        print(f"  Avg Start:         {sum(start_devs)/len(start_devs):.3f} seconds")
        print(f"  Avg End:           {sum(end_devs)/len(end_devs):.3f} seconds")
        
        print("="*80)
        
    finally:
        db.close()


if __name__ == "__main__":
    export_agreement_report()
