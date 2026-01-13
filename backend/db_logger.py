"""Database logging utilities for audio processing operations."""

import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager

from .database import (
    get_db_session, 
    ProcessingJob, 
    ProcessingStatus, 
    ProcessingMethod,
    Gender,
    SurrogateVoice
)

log = logging.getLogger(__name__)


class ProcessingJobLogger:
    """Context manager for logging audio processing jobs to database."""
    
    def __init__(
        self,
        original_filename: str,
        processing_method: str,
        parameters: Optional[Dict[str, Any]] = None,
        user_session_id: Optional[str] = None,
        user_ip: Optional[str] = None,
    ):
        self.db = None
        self.job = None
        self.start_time = None
        self.original_filename = original_filename
        self.processing_method = processing_method
        self.parameters = parameters or {}
        self.user_session_id = user_session_id
        self.user_ip = user_ip
    
    def __enter__(self):
        """Start logging the processing job."""
        try:
            self.db = get_db_session()
            self.start_time = time.time()
            
            # Map string method to enum
            method_map = {
                'anonymize': ProcessingMethod.ANONYMIZE,
                'surrogate_replace': ProcessingMethod.SURROGATE_REPLACE,
                'both': ProcessingMethod.BOTH,
            }
            method_enum = method_map.get(self.processing_method.lower(), ProcessingMethod.BOTH)
            
            # Create processing job record
            self.job = ProcessingJob(
                original_filename=self.original_filename,
                user_session_id=self.user_session_id,
                user_ip=self.user_ip,
                processing_method=method_enum,
                parameters_json=self.parameters,
                status=ProcessingStatus.PROCESSING,
            )
            
            self.db.add(self.job)
            self.db.commit()
            self.db.refresh(self.job)
            
            log.info(f"Created processing job {self.job.id} for {self.original_filename}")
            return self
            
        except Exception as e:
            log.error(f"Failed to create processing job in database: {e}")
            if self.db:
                self.db.rollback()
            return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Complete logging with success or failure status."""
        if not self.job or not self.db:
            return False
        
        try:
            processing_duration = time.time() - self.start_time if self.start_time else None
            
            if exc_type is None:
                # Success
                self.job.status = ProcessingStatus.COMPLETED
                self.job.completed_at = datetime.utcnow()
                self.job.processing_duration_seconds = processing_duration
                log.info(f"Processing job {self.job.id} completed successfully in {processing_duration:.2f}s")
            else:
                # Failure
                self.job.status = ProcessingStatus.FAILED
                self.job.error_message = str(exc_val) if exc_val else "Unknown error"
                self.job.completed_at = datetime.utcnow()
                self.job.processing_duration_seconds = processing_duration
                log.error(f"Processing job {self.job.id} failed: {exc_val}")
            
            self.db.commit()
            
        except Exception as e:
            log.error(f"Failed to update processing job status: {e}")
            if self.db:
                self.db.rollback()
        finally:
            if self.db:
                self.db.close()
        
        return False  # Don't suppress exceptions
    
    def update_input_metadata(self, file_size: int, duration: float, sample_rate: int, channels: int):
        """Update input file metadata."""
        if not self.job or not self.db:
            return
        
        try:
            self.job.original_file_size = file_size
            self.job.original_duration = duration
            self.job.original_sample_rate = sample_rate
            self.job.original_channels = channels
            self.db.commit()
            log.debug(f"Updated input metadata for job {self.job.id}")
        except Exception as e:
            log.error(f"Failed to update input metadata: {e}")
            self.db.rollback()
    
    def update_output_metadata(self, filename: str, file_size: int, duration: float):
        """Update output file metadata."""
        if not self.job or not self.db:
            return
        
        try:
            self.job.output_filename = filename
            self.job.output_file_size = file_size
            self.job.output_duration = duration
            self.db.commit()
            log.debug(f"Updated output metadata for job {self.job.id}")
        except Exception as e:
            log.error(f"Failed to update output metadata: {e}")
            self.db.rollback()
    
    def update_detection_metadata(
        self, 
        gender: Optional[str] = None, 
        language: Optional[str] = None,
        surrogate_voice: Optional[str] = None
    ):
        """Update detected characteristics."""
        if not self.job or not self.db:
            return
        
        try:
            if gender:
                gender_map = {
                    'male': Gender.MALE,
                    'female': Gender.FEMALE,
                }
                self.job.gender_detected = gender_map.get(gender.lower(), Gender.UNKNOWN)
            
            if language:
                self.job.language_detected = language
            
            if surrogate_voice:
                self.job.surrogate_voice_used = surrogate_voice
                # Update surrogate usage statistics
                self._update_surrogate_stats(surrogate_voice)
            
            self.db.commit()
            log.debug(f"Updated detection metadata for job {self.job.id}")
        except Exception as e:
            log.error(f"Failed to update detection metadata: {e}")
            self.db.rollback()
    
    def _update_surrogate_stats(self, surrogate_name: str):
        """Update surrogate voice usage statistics."""
        try:
            surrogate = self.db.query(SurrogateVoice).filter(
                SurrogateVoice.name == surrogate_name
            ).first()
            
            if surrogate:
                surrogate.usage_count += 1
                surrogate.last_used_at = datetime.utcnow()
                log.debug(f"Updated surrogate stats for {surrogate_name}")
            else:
                log.warning(f"Surrogate voice {surrogate_name} not found in database")
        except Exception as e:
            log.error(f"Failed to update surrogate stats: {e}")


def init_surrogate_voices(surrogates_root: str, db_session=None):
    """Initialize surrogate voices in database from file system."""
    import os
    
    should_close = False
    if db_session is None:
        db_session = get_db_session()
        should_close = True
    
    try:
        # Scan surrogate directories
        for language in ['english']:
            lang_path = os.path.join(surrogates_root, language)
            if not os.path.isdir(lang_path):
                continue
            
            for gender in ['male', 'female']:
                gender_path = os.path.join(lang_path, gender)
                if not os.path.isdir(gender_path):
                    continue
                
                for label in ['person', 'user_id', 'location']:
                    label_path = os.path.join(gender_path, label)
                    if not os.path.isdir(label_path):
                        continue
                    
                    # List audio files
                    for filename in os.listdir(label_path):
                        if filename.lower().endswith(('.wav', '.mp3', '.flac', '.ogg', '.m4a')):
                            name = f"{language}_{gender}_{label}_{os.path.splitext(filename)[0]}"
                            file_path = os.path.join(label_path, filename)
                            
                            # Check if already exists
                            existing = db_session.query(SurrogateVoice).filter(
                                SurrogateVoice.name == name
                            ).first()
                            
                            if not existing:
                                surrogate = SurrogateVoice(
                                    name=name,
                                    gender=Gender.MALE if gender == 'male' else Gender.FEMALE,
                                    language=language,
                                    file_path=file_path,
                                    usage_count=0,
                                )
                                db_session.add(surrogate)
                                log.info(f"Added surrogate voice: {name}")
        
        db_session.commit()
        log.info("✅ Surrogate voices initialized in database")
        
    except Exception as e:
        log.error(f"Failed to initialize surrogate voices: {e}")
        db_session.rollback()
    finally:
        if should_close:
            db_session.close()
