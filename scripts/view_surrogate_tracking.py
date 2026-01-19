#!/usr/bin/env python3
"""
Example script showing how surrogate tracking works in the database.

This demonstrates:
1. How surrogate names are captured during processing
2. How timestamps are recorded for each annotation
3. How to query the data from the database

Run after processing some audio files through the platform.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_db_session, ProcessingJob, AnnotationSurrogate, SurrogateVoice
from sqlalchemy import func, desc


def show_recent_jobs(limit=5):
    """Show recent processing jobs with their surrogate usage."""
    print("\n" + "=" * 80)
    print(f"RECENT PROCESSING JOBS (Last {limit})")
    print("=" * 80)
    
    db = get_db_session()
    try:
        jobs = db.query(ProcessingJob).order_by(
            desc(ProcessingJob.created_at)
        ).limit(limit).all()
        
        if not jobs:
            print("No jobs found. Process some audio files first!")
            return
        
        for job in jobs:
            print(f"\nJob ID: {job.id}")
            print(f"  File: {job.original_filename}")
            print(f"  Status: {job.status.value}")
            print(f"  Created: {job.created_at}")
            print(f"  Completed: {job.completed_at or 'N/A'}")
            print(f"  Duration: {job.processing_duration_seconds:.2f}s" if job.processing_duration_seconds else "  Duration: N/A")
            print(f"  Primary Surrogate: {job.surrogate_voice_used or 'N/A'}")
            
            # Get annotations for this job
            annotations = db.query(AnnotationSurrogate).filter(
                AnnotationSurrogate.processing_job_id == job.id
            ).all()
            
            if annotations:
                print(f"  Annotations Processed: {len(annotations)}")
                for i, ann in enumerate(annotations, 1):
                    print(f"    {i}. {ann.start_sec:.2f}s-{ann.end_sec:.2f}s | "
                          f"{ann.gender} | {ann.label or 'N/A'} | "
                          f"Surrogate: {ann.surrogate_name} | "
                          f"Processed at: {ann.created_at}")
            else:
                print("  No annotation details recorded")
    
    finally:
        db.close()


def show_surrogate_statistics():
    """Show usage statistics for each surrogate."""
    print("\n" + "=" * 80)
    print("SURROGATE USAGE STATISTICS")
    print("=" * 80)
    
    db = get_db_session()
    try:
        # From AnnotationSurrogate table (detailed tracking)
        results = db.query(
            AnnotationSurrogate.surrogate_name,
            AnnotationSurrogate.gender,
            AnnotationSurrogate.label,
            func.count(AnnotationSurrogate.id).label('usage_count'),
            func.max(AnnotationSurrogate.created_at).label('last_used')
        ).group_by(
            AnnotationSurrogate.surrogate_name,
            AnnotationSurrogate.gender,
            AnnotationSurrogate.label
        ).order_by(desc('usage_count')).all()
        
        if not results:
            print("No surrogate usage data yet. Process some audio files first!")
            return
        
        print(f"\n{'Surrogate Name':<30} {'Gender':<10} {'Label':<15} {'Uses':<10} {'Last Used'}")
        print("-" * 95)
        
        for surrogate_name, gender, label, count, last_used in results:
            last_used_str = last_used.strftime("%Y-%m-%d %H:%M") if last_used else "Never"
            print(f"{surrogate_name:<30} {gender:<10} {label or 'N/A':<15} {count:<10} {last_used_str}")
        
        # Summary
        total_uses = sum(row.usage_count for row in results)
        print("-" * 95)
        print(f"Total surrogate replacements: {total_uses}")
        
    finally:
        db.close()


def show_todays_activity():
    """Show all annotations processed today."""
    print("\n" + "=" * 80)
    print("TODAY'S ACTIVITY")
    print("=" * 80)
    
    db = get_db_session()
    try:
        today = datetime.now(timezone.utc).date()
        tomorrow = today + timedelta(days=1)
        
        annotations = db.query(AnnotationSurrogate).filter(
            AnnotationSurrogate.created_at >= today,
            AnnotationSurrogate.created_at < tomorrow
        ).order_by(desc(AnnotationSurrogate.created_at)).all()
        
        if not annotations:
            print(f"\nNo annotations processed today ({today})")
            return
        
        print(f"\nProcessed {len(annotations)} annotations today ({today})")
        print(f"\n{'Time':<20} {'Duration':<12} {'Gender':<10} {'Label':<15} {'Surrogate'}")
        print("-" * 90)
        
        for ann in annotations:
            time_str = ann.created_at.strftime("%H:%M:%S")
            duration_str = f"{ann.duration_sec:.2f}s"
            print(f"{time_str:<20} {duration_str:<12} {ann.gender:<10} {ann.label or 'N/A':<15} {ann.surrogate_name}")
        
    finally:
        db.close()


def show_surrogate_inventory():
    """Show registered surrogate voices."""
    print("\n" + "=" * 80)
    print("SURROGATE VOICE INVENTORY")
    print("=" * 80)
    
    db = get_db_session()
    try:
        surrogates = db.query(SurrogateVoice).order_by(
            SurrogateVoice.language,
            SurrogateVoice.gender,
            SurrogateVoice.name
        ).all()
        
        if not surrogates:
            print("\nNo surrogate voices registered in database.")
            print("Run: python -c 'from backend.db_logger import init_surrogate_voices; init_surrogate_voices(\"data/surrogates\")'")
            return
        
        current_lang = None
        for surrogate in surrogates:
            if current_lang != surrogate.language:
                current_lang = surrogate.language
                print(f"\n{current_lang.upper()}:")
            
            print(f"  {surrogate.name:<50} | {surrogate.gender.value:<8} | "
                  f"Used: {surrogate.usage_count} times | "
                  f"Last: {surrogate.last_used_at.strftime('%Y-%m-%d') if surrogate.last_used_at else 'Never'}")
        
        print(f"\nTotal surrogate voices registered: {len(surrogates)}")
        
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="View surrogate tracking data")
    parser.add_argument("--jobs", action="store_true", help="Show recent jobs")
    parser.add_argument("--stats", action="store_true", help="Show surrogate statistics")
    parser.add_argument("--today", action="store_true", help="Show today's activity")
    parser.add_argument("--inventory", action="store_true", help="Show surrogate inventory")
    parser.add_argument("--all", action="store_true", help="Show all information")
    
    args = parser.parse_args()
    
    if args.all or not any([args.jobs, args.stats, args.today, args.inventory]):
        # Show everything if no specific option or --all
        show_surrogate_inventory()
        show_recent_jobs()
        show_surrogate_statistics()
        show_todays_activity()
    else:
        if args.inventory:
            show_surrogate_inventory()
        if args.jobs:
            show_recent_jobs()
        if args.stats:
            show_surrogate_statistics()
        if args.today:
            show_todays_activity()
    
    print("\n" + "=" * 80)
