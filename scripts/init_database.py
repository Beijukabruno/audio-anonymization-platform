#!/usr/bin/env python3
"""
Initialize audio anonymization database with complete schema.

This script:
1. Creates all tables (ProcessingJob, SurrogateVoice, etc.)
2. Initializes surrogate voices from filesystem
3. Verifies database connectivity
4. Reports schema status

Run this once when setting up the platform or after database reset.
"""

import sys
import logging
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import (
    init_db,
    get_db_session,
    ProcessingJob,
    SurrogateVoice,
    AnnotationSurrogate,
    UserAnnotationAgreement,
    DailyStatistics,
)
from backend.db_logger import init_surrogate_voices

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)


def verify_database_connection():
    """Test database connectivity."""
    try:
        db = get_db_session()
        # Try a simple query
        result = db.query(ProcessingJob).first()
        db.close()
        return True
    except Exception as e:
        log.error(f"Database connection failed: {e}")
        return False


def verify_schema():
    """Verify all tables exist."""
    db = get_db_session()
    try:
        tables = {
            'ProcessingJob': ProcessingJob,
            'SurrogateVoice': SurrogateVoice,
            'AnnotationSurrogate': AnnotationSurrogate,
            'UserAnnotationAgreement': UserAnnotationAgreement,
            'DailyStatistics': DailyStatistics,
        }
        
        log.info("Checking schema...")
        all_exist = True
        
        for table_name, table_class in tables.items():
            try:
                # Try to query the table
                db.query(table_class).first()
                log.info(f"  ✓ {table_name} table exists")
            except Exception as e:
                log.error(f"  ✗ {table_name} table missing: {e}")
                all_exist = False
        
        return all_exist
    finally:
        db.close()


def count_records():
    """Count records in main tables."""
    db = get_db_session()
    try:
        job_count = db.query(ProcessingJob).count()
        surrogate_count = db.query(SurrogateVoice).count()
        annotation_count = db.query(AnnotationSurrogate).count()
        agreement_count = db.query(UserAnnotationAgreement).count()
        
        log.info("Current database state:")
        log.info(f"  ProcessingJob records: {job_count}")
        log.info(f"  SurrogateVoice records: {surrogate_count}")
        log.info(f"  AnnotationSurrogate records: {annotation_count}")
        log.info(f"  UserAnnotationAgreement records: {agreement_count}")
        
        return True
    except Exception as e:
        log.error(f"Error counting records: {e}")
        return False
    finally:
        db.close()


def main():
    """Main initialization routine."""
    print("\n" + "="*70)
    print("AUDIO ANONYMIZATION PLATFORM - DATABASE INITIALIZATION")
    print("="*70 + "\n")
    
    # Step 1: Test connectivity
    log.info("Step 1: Testing database connectivity...")
    if not verify_database_connection():
        log.error("Cannot connect to database. Check DATABASE_URL and PostgreSQL service.")
        return False
    log.info("  ✓ Database connection successful\n")
    
    # Step 2: Initialize schema
    log.info("Step 2: Initializing database schema...")
    try:
        init_db()
        log.info("  ✓ Database schema initialized\n")
    except Exception as e:
        log.error(f"Failed to initialize schema: {e}")
        return False
    
    # Step 3: Verify schema
    log.info("Step 3: Verifying schema...")
    if not verify_schema():
        log.error("Schema verification failed")
        return False
    log.info("  ✓ All tables verified\n")
    
    # Step 4: Initialize surrogates (if needed)
    log.info("Step 4: Initializing surrogate voices from filesystem...")
    surrogates_path = Path(__file__).parent.parent / "data" / "surrogates"
    if surrogates_path.exists():
        try:
            init_surrogate_voices(str(surrogates_path))
            log.info("  ✓ Surrogate voices initialized\n")
        except Exception as e:
            log.error(f"Failed to initialize surrogates: {e}")
            # Not fatal, continue
    else:
        log.warning(f"  ⚠ Surrogate voices directory not found: {surrogates_path}")
        log.warning("  Surrogates can be added later\n")
    
    # Step 5: Show current state
    log.info("Step 5: Current database state...")
    count_records()
    
    print("\n" + "="*70)
    log.info("✓ DATABASE INITIALIZATION COMPLETE")
    print("="*70 + "\n")
    
    print("Next steps:")
    print("  1. Update gradio_app.py with user_session_id and audio_file_hash")
    print("  2. Start the Gradio application")
    print("  3. Have multiple users annotate the same audio file")
    print("  4. Use scripts/view_inter_user_agreement.py to view metrics")
    print()
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
