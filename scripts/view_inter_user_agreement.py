#!/usr/bin/env python3
"""
Utility script to view inter-user annotation agreement metrics.

This script demonstrates how to use the new inter-user tracking database functions
to view agreement statistics between different users who have annotated the same audio file.
"""

import sys
import argparse
import hashlib
from pathlib import Path
from tabulate import tabulate

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import (
    get_db_session,
    compare_user_annotations,
    get_agreement_summary_for_audio,
    get_all_user_pairs_for_audio,
    get_user_annotations_for_audio,
    get_disagreement_segments_for_audio,
    AnnotationSurrogate,
)


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()[:16]


def view_file_summary(audio_file_hash: str):
    """View agreement summary for a specific audio file hash."""
    db = get_db_session()
    try:
        summary = get_agreement_summary_for_audio(db, audio_file_hash)
        
        print("\n" + "="*60)
        print("INTER-USER AGREEMENT SUMMARY")
        print("="*60)
        print(f"Audio File Hash: {audio_file_hash}")
        print(f"Total Comparisons: {summary['total_comparisons']}")
        print(f"Complete Agreement: {summary['complete_agreement']} ({summary['complete_percent']}%)")
        print(f"Partial Agreement: {summary['partial_agreement']}")
        print(f"No Agreement: {summary['no_agreement']}")
        print(f"Average Time Overlap: {summary['avg_overlap_percent']}%")
        print("="*60 + "\n")
        
    finally:
        db.close()


def view_user_annotations(audio_file_hash: str, user_session_id: str):
    """View all annotations from a specific user."""
    db = get_db_session()
    try:
        annotations = get_user_annotations_for_audio(db, audio_file_hash, user_session_id)
        
        print(f"\nAnnotations by User {user_session_id[:8]}...: {len(annotations)} segments")
        print("-" * 80)
        
        if annotations:
            table_data = []
            for ann in annotations:
                table_data.append([
                    f"{ann.start_sec:.2f}s",
                    f"{ann.end_sec:.2f}s",
                    ann.duration_sec,
                    ann.gender,
                    ann.label or "-",
                    ann.surrogate_name.split("_")[-1][:10],  # Shortened name
                    ann.created_at.strftime("%H:%M:%S") if ann.created_at else "-",
                ])
            
            headers = ["Start", "End", "Duration", "Gender", "Label", "Surrogate", "Time"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
    finally:
        db.close()


def view_user_pairs(audio_file_hash: str):
    """View all user pairs who annotated the same file."""
    db = get_db_session()
    try:
        pairs = get_all_user_pairs_for_audio(db, audio_file_hash)
        
        print(f"\nUser Pairs for Audio File {audio_file_hash}")
        print("-" * 80)
        
        if pairs:
            table_data = []
            for pair in pairs:
                table_data.append([
                    pair['user1'][:8] + "...",
                    pair['user2'][:8] + "...",
                    pair['total_comparisons'],
                    pair['complete_agreement'],
                    f"{pair['agreement_percent']}%",
                ])
            
            headers = ["User 1", "User 2", "Comparisons", "Complete", "Agreement %"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            print("No multi-user annotations found for this file.")
        
    finally:
        db.close()


def view_disagreements(audio_file_hash: str):
    """View all disagreement segments."""
    db = get_db_session()
    try:
        disagreements = get_disagreement_segments_for_audio(db, audio_file_hash)
        
        print(f"\nDisagreement Segments for Audio File {audio_file_hash}")
        print("-" * 100)
        
        if disagreements:
            table_data = []
            for dis in disagreements:
                level_icon = "⚠️" if dis.agreement_level == "partial" else "✗"
                table_data.append([
                    level_icon,
                    f"{dis.segment_start_sec:.2f}s",
                    f"{dis.segment_end_sec:.2f}s",
                    dis.user1_gender,
                    dis.user1_label or "-",
                    dis.user2_gender,
                    dis.user2_label or "-",
                    f"{dis.time_overlap_percent:.1f}%",
                ])
            
            headers = ["", "Start", "End", "User1 Gender", "User1 Label", "User2 Gender", "User2 Label", "Overlap"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            print("No disagreement segments found!")
        
    finally:
        db.close()


def list_audio_files():
    """List all audio files that have been annotated."""
    db = get_db_session()
    try:
        annotations = db.query(AnnotationSurrogate).distinct(AnnotationSurrogate.audio_file_hash).all()
        unique_hashes = list(set(ann.audio_file_hash for ann in annotations if ann.audio_file_hash))
        
        print(f"\nAudio Files with Annotations: {len(unique_hashes)}")
        print("-" * 60)
        
        if unique_hashes:
            table_data = []
            for file_hash in unique_hashes:
                summary = get_agreement_summary_for_audio(db, file_hash)
                file_annotations = db.query(AnnotationSurrogate).filter_by(audio_file_hash=file_hash).all()
                unique_users = len(set(
                    db.query(AnnotationSurrogate.processing_job_id)
                    .filter_by(audio_file_hash=file_hash)
                    .distinct()
                    .all()
                ))
                
                table_data.append([
                    file_hash,
                    len(file_annotations),
                    unique_users,
                    summary['total_comparisons'],
                    f"{summary['complete_percent']}%",
                ])
            
            headers = ["File Hash", "Annotations", "Users", "Comparisons", "Agreement"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        else:
            print("No annotated audio files found in database.")
        
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="View inter-user annotation agreement metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all audio files with annotations
  python view_inter_user_agreement.py --list-files
  
  # View summary for a specific audio file
  python view_inter_user_agreement.py --file-hash abc123def456
  
  # View annotations by a specific user
  python view_inter_user_agreement.py --file-hash abc123def456 --user-session user-uuid-here
  
  # View user pairs for an audio file
  python view_inter_user_agreement.py --file-hash abc123def456 --pairs
  
  # View disagreement segments
  python view_inter_user_agreement.py --file-hash abc123def456 --disagreements
        """
    )
    
    parser.add_argument("--list-files", action="store_true", help="List all audio files with annotations")
    parser.add_argument("--file-hash", type=str, help="Audio file hash to analyze")
    parser.add_argument("--user-session", type=str, help="User session ID to view annotations for")
    parser.add_argument("--pairs", action="store_true", help="View all user pairs for a file")
    parser.add_argument("--disagreements", action="store_true", help="View disagreement segments")
    
    args = parser.parse_args()
    
    # List files
    if args.list_files:
        list_audio_files()
        return
    
    # File hash is required for other operations
    if not args.file_hash:
        if not args.list_files:
            parser.print_help()
            sys.exit(1)
        return
    
    # View summary
    view_file_summary(args.file_hash)
    
    # View user annotations
    if args.user_session:
        view_user_annotations(args.file_hash, args.user_session)
    
    # View user pairs
    if args.pairs:
        view_user_pairs(args.file_hash)
    
    # View disagreements
    if args.disagreements:
        view_disagreements(args.file_hash)


if __name__ == "__main__":
    main()
