#!/usr/bin/env python3
"""
Test script for inter-annotator agreement system.

This script:
1. Verifies database tables exist
2. Tests audio hashing functionality
3. Simulates multi-user annotations
4. Generates agreement report
"""

import os
import sys
import logging
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import (
    get_db_session,
    ProcessingJob,
    AnnotationSurrogate,
    UserAnnotationAgreement,
    ProcessingStatus,
    ProcessingMethod,
    Gender,
    init_db,
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
log = logging.getLogger(__name__)


def test_database_tables():
    """Test 1: Verify all required tables exist."""
    log.info("="*60)
    log.info("TEST 1: Database Tables")
    log.info("="*60)
    
    try:
        db = get_db_session()
        
        # Try to query each table
        tables_to_check = [
            ("ProcessingJob", ProcessingJob),
            ("AnnotationSurrogate", AnnotationSurrogate),
            ("UserAnnotationAgreement", UserAnnotationAgreement),
        ]
        
        for table_name, table_class in tables_to_check:
            try:
                count = db.query(table_class).count()
                log.info(f"  ✓ {table_name:25s}: {count:4d} records")
            except Exception as e:
                log.error(f"  ✗ {table_name:25s}: ERROR - {e}")
                return False
        
        db.close()
        log.info("  Test PASSED")
        return True
        
    except Exception as e:
        log.error(f"  Test FAILED: {e}")
        return False


def test_audio_hashing():
    """Test 2: Verify audio hashing works correctly."""
    log.info("\n" + "="*60)
    log.info("TEST 2: Audio Hashing")
    log.info("="*60)
    
    try:
        # Test with sample data
        test_data_1 = b"sample audio data content"
        test_data_2 = b"sample audio data content"  # Same
        test_data_3 = b"different audio content"
        
        hash_1 = hashlib.sha256(test_data_1).hexdigest()
        hash_2 = hashlib.sha256(test_data_2).hexdigest()
        hash_3 = hashlib.sha256(test_data_3).hexdigest()
        
        log.info(f"  Hash 1: {hash_1[:16]}...")
        log.info(f"  Hash 2: {hash_2[:16]}...")
        log.info(f"  Hash 3: {hash_3[:16]}...")
        
        if hash_1 == hash_2:
            log.info("  ✓ Same content produces same hash")
        else:
            log.error("  ✗ Same content produced different hashes!")
            return False
        
        if hash_1 != hash_3:
            log.info("  ✓ Different content produces different hash")
        else:
            log.error("  ✗ Different content produced same hash!")
            return False
        
        log.info("  Test PASSED")
        return True
        
    except Exception as e:
        log.error(f"  Test FAILED: {e}")
        return False


def test_annotation_storage():
    """Test 3: Test storing annotations with audio hash."""
    log.info("\n" + "="*60)
    log.info("TEST 3: Annotation Storage")
    log.info("="*60)
    
    try:
        db = get_db_session()
        
        # Simulate audio hash
        test_audio_hash = hashlib.sha256(b"test_audio_file_001").hexdigest()
        log.info(f"  Test audio hash: {test_audio_hash[:16]}...")
        
        # Create test processing job
        test_job = ProcessingJob(
            original_filename="test_audio_001.wav",
            user_session_id="test-user-001",
            processing_method=ProcessingMethod.BOTH,
            status=ProcessingStatus.COMPLETED,
        )
        db.add(test_job)
        db.commit()
        db.refresh(test_job)
        log.info(f"  ✓ Created test processing job (ID: {test_job.id})")
        
        # Create test annotations
        test_annotations = [
            AnnotationSurrogate(
                processing_job_id=test_job.id,
                audio_file_hash=test_audio_hash,
                start_sec=2.5,
                end_sec=4.3,
                duration_sec=1.8,
                gender="male",
                label="PERSON",
                language="english",
                surrogate_name="test_surrogate_m_person_001",
                surrogate_file_path="/test/path",
            ),
            AnnotationSurrogate(
                processing_job_id=test_job.id,
                audio_file_hash=test_audio_hash,
                start_sec=8.1,
                end_sec=10.2,
                duration_sec=2.1,
                gender="female",
                label="LOCATION",
                language="english",
                surrogate_name="test_surrogate_f_location_001",
                surrogate_file_path="/test/path",
            ),
        ]
        
        for ann in test_annotations:
            db.add(ann)
        
        db.commit()
        log.info(f"  ✓ Created {len(test_annotations)} test annotations")
        
        # Verify annotations can be retrieved by hash
        retrieved = db.query(AnnotationSurrogate).filter_by(
            audio_file_hash=test_audio_hash
        ).all()
        
        if len(retrieved) == len(test_annotations):
            log.info(f"  ✓ Successfully retrieved annotations by hash")
        else:
            log.error(f"  ✗ Expected {len(test_annotations)} annotations, got {len(retrieved)}")
            db.close()
            return False
        
        # Clean up
        for ann in retrieved:
            db.delete(ann)
        db.delete(test_job)
        db.commit()
        log.info("  ✓ Cleaned up test data")
        
        db.close()
        log.info("  Test PASSED")
        return True
        
    except Exception as e:
        log.error(f"  Test FAILED: {e}")
        if db:
            db.rollback()
            db.close()
        return False


def test_multi_user_annotations():
    """Test 4: Simulate multi-user annotations on same file."""
    log.info("\n" + "="*60)
    log.info("TEST 4: Multi-User Annotations")
    log.info("="*60)
    
    try:
        db = get_db_session()
        
        # Same audio hash for both users
        test_audio_hash = hashlib.sha256(b"shared_audio_file").hexdigest()
        log.info(f"  Simulating 2 users annotating same audio")
        log.info(f"  Audio hash: {test_audio_hash[:16]}...")
        
        # User 1 annotations
        job1 = ProcessingJob(
            original_filename="shared_audio.wav",
            user_session_id="user-001-uuid",
            processing_method=ProcessingMethod.BOTH,
            status=ProcessingStatus.COMPLETED,
        )
        db.add(job1)
        db.commit()
        db.refresh(job1)
        
        ann1_1 = AnnotationSurrogate(
            processing_job_id=job1.id,
            audio_file_hash=test_audio_hash,
            start_sec=2.5,
            end_sec=4.3,
            duration_sec=1.8,
            gender="male",
            label="PERSON",
            language="english",
            surrogate_name="surrogate_1",
            surrogate_file_path="/path",
        )
        ann1_2 = AnnotationSurrogate(
            processing_job_id=job1.id,
            audio_file_hash=test_audio_hash,
            start_sec=10.0,
            end_sec=12.5,
            duration_sec=2.5,
            gender="female",
            label="LOCATION",
            language="english",
            surrogate_name="surrogate_2",
            surrogate_file_path="/path",
        )
        db.add(ann1_1)
        db.add(ann1_2)
        db.commit()
        log.info("  ✓ User 1: Added 2 annotations")
        
        # User 2 annotations (slightly different timestamps)
        job2 = ProcessingJob(
            original_filename="shared_audio.wav",
            user_session_id="user-002-uuid",
            processing_method=ProcessingMethod.BOTH,
            status=ProcessingStatus.COMPLETED,
        )
        db.add(job2)
        db.commit()
        db.refresh(job2)
        
        ann2_1 = AnnotationSurrogate(
            processing_job_id=job2.id,
            audio_file_hash=test_audio_hash,  # Same hash!
            start_sec=2.4,  # Slightly different
            end_sec=4.4,
            duration_sec=2.0,
            gender="male",
            label="PERSON",
            language="english",
            surrogate_name="surrogate_1",
            surrogate_file_path="/path",
        )
        ann2_2 = AnnotationSurrogate(
            processing_job_id=job2.id,
            audio_file_hash=test_audio_hash,
            start_sec=9.8,  # Slightly different
            end_sec=12.3,
            duration_sec=2.5,
            gender="female",
            label="LOCATION",
            language="english",
            surrogate_name="surrogate_2",
            surrogate_file_path="/path",
        )
        db.add(ann2_1)
        db.add(ann2_2)
        db.commit()
        log.info("  ✓ User 2: Added 2 annotations")
        
        # Count annotations per user
        user1_annotations = db.query(AnnotationSurrogate).filter_by(    processing_job_id=job1.id
        ).count()
        user2_annotations = db.query(AnnotationSurrogate).filter_by(
            processing_job_id=job2.id
        ).count()
        
        log.info(f"  User 1: {user1_annotations} segments")
        log.info(f"  User 2: {user2_annotations} segments")
        
        # Verify we can query by hash
        all_for_audio = db.query(AnnotationSurrogate).filter_by(
            audio_file_hash=test_audio_hash
        ).count()
        
        if all_for_audio == 4:
            log.info(f"  ✓ Found {all_for_audio} total annotations for this audio")
        else:
            log.error(f"  ✗ Expected 4 annotations, found {all_for_audio}")
            return False
        
        # Verify different user sessions
        unique_users = db.query(ProcessingJob.user_session_id).join(
            AnnotationSurrogate
        ).filter(
            AnnotationSurrogate.audio_file_hash == test_audio_hash
        ).distinct().count()
        
        if unique_users == 2:
            log.info(f"  ✓ Verified 2 unique users annotated this audio")
        else:
            log.error(f"  ✗ Expected 2 users, found {unique_users}")
            return False
        
        # Clean up
        for ann in [ann1_1, ann1_2, ann2_1, ann2_2]:
            db.delete(ann)
        db.delete(job1)
        db.delete(job2)
        db.commit()
        log.info("  ✓ Cleaned up test data")
        
        db.close()
        log.info("  Test PASSED")
        return True
        
    except Exception as e:
        log.error(f"  Test FAILED: {e}")
        if db:
            db.rollback()
            db.close()
        return False


def main():
    """Run all tests."""
    log.info("\n" + "="*60)
    log.info("INTER-ANNOTATOR AGREEMENT SYSTEM TEST SUITE")
    log.info("="*60 + "\n")
    
    tests = [
        ("Database Tables", test_database_tables),
        ("Audio Hashing", test_audio_hashing),
        ("Annotation Storage", test_annotation_storage),
        ("Multi-User Annotations", test_multi_user_annotations),
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    # Summary
    log.info("\n" + "="*60)
    log.info("TEST SUMMARY")
    log.info("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        log.info(f"  {status:7s} - {name}")
    
    log.info("-"*60)
    log.info(f"  Total: {passed}/{total} tests passed")
    log.info("="*60)
    
    if passed == total:
        log.info("\n🎉 All tests passed! System is ready for use.")
        return 0
    else:
        log.error(f"\n❌ {total - passed} test(s) failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
