"""Database models and connection management for audio anonymization platform."""

import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Enum, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://audio_user:audio_dev_password@localhost:5432/audio_anony")

# SQLAlchemy setup
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Enums
class ProcessingStatus(enum.Enum):
    """Status of audio processing job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingMethod(enum.Enum):
    """Type of processing applied."""
    ANONYMIZE = "anonymize"
    SURROGATE_REPLACE = "surrogate_replace"
    BOTH = "both"


class Gender(enum.Enum):
    """Gender classification."""
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


# Database Models
class ProcessingJob(Base):
    """Record of each audio processing job."""
    
    __tablename__ = "processing_jobs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    
    # User/Session info
    user_session_id = Column(String(255), nullable=True, index=True)
    user_ip = Column(String(50), nullable=True)
    
    # Input file info
    original_filename = Column(String(500), nullable=False)
    original_file_size = Column(Integer, nullable=True)  # bytes
    original_duration = Column(Float, nullable=True)  # seconds
    original_sample_rate = Column(Integer, nullable=True)
    original_channels = Column(Integer, nullable=True)
    
    # Processing info
    processing_method = Column(Enum(ProcessingMethod), nullable=False)
    parameters_json = Column(JSON, nullable=True)  # Flexible storage for any params
    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    
    # Output file info
    output_filename = Column(String(500), nullable=True)
    output_file_size = Column(Integer, nullable=True)  # bytes
    output_duration = Column(Float, nullable=True)  # seconds
    
    # Performance metrics
    processing_duration_seconds = Column(Float, nullable=True)
    
    # Detected characteristics
    surrogate_voice_used = Column(String(255), nullable=True, index=True)
    gender_detected = Column(Enum(Gender), nullable=True, index=True)
    language_detected = Column(String(50), nullable=True, index=True)
    
    def __repr__(self):
        return f"<ProcessingJob(id={self.id}, filename={self.original_filename}, status={self.status})>"


class SurrogateVoice(Base):
    """Tracking and statistics for surrogate voices."""
    
    __tablename__ = "surrogate_voices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    gender = Column(Enum(Gender), nullable=False, index=True)
    language = Column(String(50), nullable=False, index=True)
    file_path = Column(String(1000), nullable=False)
    
    # Usage statistics
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    def __repr__(self):
        return f"<SurrogateVoice(name={self.name}, gender={self.gender}, language={self.language})>"


class DailyStatistics(Base):
    """Daily aggregated statistics for monitoring and analytics."""
    
    __tablename__ = "daily_statistics"
    
    date = Column(DateTime, primary_key=True)
    
    # Volume metrics
    total_files_processed = Column(Integer, default=0, nullable=False)
    total_files_failed = Column(Integer, default=0, nullable=False)
    
    # Performance metrics
    total_processing_time = Column(Float, default=0.0, nullable=False)  # seconds
    average_processing_time = Column(Float, nullable=True)  # seconds
    
    # File size metrics
    average_input_file_size = Column(Integer, nullable=True)  # bytes
    average_output_file_size = Column(Integer, nullable=True)  # bytes
    total_data_processed = Column(Integer, default=0, nullable=False)  # bytes
    
    # Success rate
    success_rate = Column(Float, nullable=True)  # percentage
    
    # Most popular
    most_used_surrogate = Column(String(255), nullable=True)
    most_used_method = Column(String(50), nullable=True)
    
    def __repr__(self):
        return f"<DailyStatistics(date={self.date}, total_files={self.total_files_processed})>"


class AnnotationSurrogate(Base):
    """Track each annotation processed with the surrogate used."""
    
    __tablename__ = "annotation_surrogates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    processing_job_id = Column(Integer, ForeignKey('processing_jobs.id'), nullable=False, index=True)
    
    # Audio file identifier
    audio_file_hash = Column(String(64), nullable=True, index=True)  # MD5 or SHA256 of original file
    
    # Annotation details
    start_sec = Column(Float, nullable=False)
    end_sec = Column(Float, nullable=False)
    duration_sec = Column(Float, nullable=False)
    gender = Column(String(20), nullable=False)
    label = Column(String(100), nullable=True)
    language = Column(String(50), nullable=False)
    
    # Surrogate information
    surrogate_name = Column(String(500), nullable=False, index=True)
    surrogate_file_path = Column(String(1000), nullable=False)
    surrogate_duration_ms = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    # Processing strategy
    processing_strategy = Column(String(50), nullable=True)  # 'direct' or 'fit'
    
    def __repr__(self):
        return f"<AnnotationSurrogate(job_id={self.processing_job_id}, {self.start_sec:.2f}s-{self.end_sec:.2f}s, surrogate={self.surrogate_name})>"


class UserAnnotationAgreement(Base):
    """Track inter-user annotation agreements/disagreements on same audio segments.
    
    This table stores comparisons between annotations from different users
    on the same audio file and time segment.
    """
    
    __tablename__ = "user_annotation_agreements"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Audio file being annotated
    audio_file_hash = Column(String(64), nullable=False, index=True)
    audio_filename = Column(String(500), nullable=False)
    
    # The time segment that was annotated
    segment_start_sec = Column(Float, nullable=False)
    segment_end_sec = Column(Float, nullable=False)
    
    # User 1 information
    user1_session_id = Column(String(255), nullable=False, index=True)
    user1_processing_job_id = Column(Integer, ForeignKey('processing_jobs.id'), nullable=False)
    user1_annotation_id = Column(Integer, ForeignKey('annotation_surrogates.id'), nullable=True)
    user1_gender = Column(String(20), nullable=True)
    user1_label = Column(String(100), nullable=True)
    user1_surrogate = Column(String(500), nullable=True)
    user1_annotation_time = Column(DateTime, nullable=True)
    
    # User 2 information
    user2_session_id = Column(String(255), nullable=False, index=True)
    user2_processing_job_id = Column(Integer, ForeignKey('processing_jobs.id'), nullable=False)
    user2_annotation_id = Column(Integer, ForeignKey('annotation_surrogates.id'), nullable=True)
    user2_gender = Column(String(20), nullable=True)
    user2_label = Column(String(100), nullable=True)
    user2_surrogate = Column(String(500), nullable=True)
    user2_annotation_time = Column(DateTime, nullable=True)
    
    # Agreement metrics
    gender_match = Column(Boolean, nullable=True)  # True if both users chose same gender
    label_match = Column(Boolean, nullable=True)   # True if both users chose same label
    surrogate_match = Column(Boolean, nullable=True)  # True if same surrogate was used
    time_overlap_percent = Column(Float, nullable=True)  # How much time ranges overlap (0-100)
    
    # Overall agreement assessment
    agreement_level = Column(String(20), nullable=True)  # 'complete', 'partial', 'none'
    notes = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    reviewed = Column(Boolean, default=False, nullable=False)
    
    def __repr__(self):
        return f"<UserAnnotationAgreement(audio={self.audio_filename}, segment={self.segment_start_sec:.1f}s-{self.segment_end_sec:.1f}s, agreement={self.agreement_level})>"


# Database helper functions
def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created successfully")


def get_db():
    """Get database session with context manager support."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session():
    """Get a database session (for non-context manager usage)."""
    return SessionLocal()


def compare_user_annotations(db, audio_file_hash: str, audio_filename: str):
    """
    Compare annotations from different users on the same audio file.
    
    Args:
        db: Database session
        audio_file_hash: Hash of audio file (for identification)
        audio_filename: Original filename
    
    Returns:
        List of UserAnnotationAgreement records
    """
    # Find all annotations for this audio file
    annotations = db.query(AnnotationSurrogate).filter_by(
        audio_file_hash=audio_file_hash
    ).all()
    
    agreements = []
    
    # Compare each pair of annotations from different users
    for i, ann1 in enumerate(annotations):
        job1 = db.query(ProcessingJob).filter_by(id=ann1.processing_job_id).first()
        
        for ann2 in annotations[i+1:]:
            job2 = db.query(ProcessingJob).filter_by(id=ann2.processing_job_id).first()
            
            # Different users?
            if job1.user_session_id == job2.user_session_id:
                continue
            
            # Same or overlapping time segment?
            time_overlap = max(0, min(ann1.end_sec, ann2.end_sec) - max(ann1.start_sec, ann2.start_sec))
            total_time = max(ann1.end_sec, ann2.end_sec) - min(ann1.start_sec, ann2.start_sec)
            overlap_percent = (time_overlap / total_time * 100) if total_time > 0 else 0
            
            if overlap_percent < 20:  # Less than 20% overlap, skip
                continue
            
            # Check agreement
            gender_match = ann1.gender == ann2.gender
            label_match = ann1.label == ann2.label
            surrogate_match = ann1.surrogate_name == ann2.surrogate_name
            
            # Determine overall agreement level
            if gender_match and label_match and surrogate_match:
                agreement_level = "complete"
            elif gender_match and label_match:
                agreement_level = "partial"
            else:
                agreement_level = "none"
            
            # Create agreement record
            agreement = UserAnnotationAgreement(
                audio_file_hash=audio_file_hash,
                audio_filename=audio_filename,
                segment_start_sec=min(ann1.start_sec, ann2.start_sec),
                segment_end_sec=max(ann1.end_sec, ann2.end_sec),
                
                user1_session_id=job1.user_session_id,
                user1_processing_job_id=job1.id,
                user1_annotation_id=ann1.id,
                user1_gender=ann1.gender,
                user1_label=ann1.label,
                user1_surrogate=ann1.surrogate_name,
                user1_annotation_time=ann1.created_at,
                
                user2_session_id=job2.user_session_id,
                user2_processing_job_id=job2.id,
                user2_annotation_id=ann2.id,
                user2_gender=ann2.gender,
                user2_label=ann2.label,
                user2_surrogate=ann2.surrogate_name,
                user2_annotation_time=ann2.created_at,
                
                gender_match=gender_match,
                label_match=label_match,
                surrogate_match=surrogate_match,
                time_overlap_percent=overlap_percent,
                agreement_level=agreement_level,
            )
            
            agreements.append(agreement)
    
    return agreements


def get_agreement_summary_for_audio(db, audio_file_hash: str) -> dict:
    """
    Get summary statistics for inter-user agreement on an audio file.
    
    Args:
        db: Database session
        audio_file_hash: Hash of audio file
    
    Returns:
        Dictionary with agreement metrics
    """
    agreements = db.query(UserAnnotationAgreement).filter_by(
        audio_file_hash=audio_file_hash
    ).all()
    
    if not agreements:
        return {
            "total_comparisons": 0,
            "complete_agreement": 0,
            "partial_agreement": 0,
            "no_agreement": 0,
            "complete_percent": 0,
            "avg_overlap_percent": 0,
        }
    
    complete = sum(1 for a in agreements if a.agreement_level == "complete")
    partial = sum(1 for a in agreements if a.agreement_level == "partial")
    none = sum(1 for a in agreements if a.agreement_level == "none")
    avg_overlap = sum(a.time_overlap_percent for a in agreements) / len(agreements)
    
    return {
        "total_comparisons": len(agreements),
        "complete_agreement": complete,
        "partial_agreement": partial,
        "no_agreement": none,
        "complete_percent": round(complete / len(agreements) * 100, 2),
        "avg_overlap_percent": round(avg_overlap, 2),
    }


def get_all_user_pairs_for_audio(db, audio_file_hash: str) -> list:
    """
    Get all unique user pairs who annotated the same audio file.
    
    Args:
        db: Database session
        audio_file_hash: Hash of audio file
    
    Returns:
        List of (user1_session_id, user2_session_id, agreement_count, complete_count)
    """
    agreements = db.query(UserAnnotationAgreement).filter_by(
        audio_file_hash=audio_file_hash
    ).all()
    
    # Group by user pairs
    user_pairs = {}
    for agreement in agreements:
        # Sort user IDs to avoid duplicate pairs (u1:u2 vs u2:u1)
        users = tuple(sorted([agreement.user1_session_id, agreement.user2_session_id]))
        
        if users not in user_pairs:
            user_pairs[users] = {"total": 0, "complete": 0}
        
        user_pairs[users]["total"] += 1
        if agreement.agreement_level == "complete":
            user_pairs[users]["complete"] += 1
    
    # Return as list of tuples with agreement metrics
    result = []
    for (user1, user2), counts in user_pairs.items():
        result.append({
            "user1": user1,
            "user2": user2,
            "total_comparisons": counts["total"],
            "complete_agreement": counts["complete"],
            "agreement_percent": round(counts["complete"] / counts["total"] * 100, 2),
        })
    
    return result


def get_user_annotations_for_audio(db, audio_file_hash: str, user_session_id: str) -> list:
    """
    Get all annotations from a specific user for an audio file.
    
    Args:
        db: Database session
        audio_file_hash: Hash of audio file
        user_session_id: User session identifier
    
    Returns:
        List of AnnotationSurrogate records
    """
    # Find all ProcessingJob records for this user
    user_jobs = db.query(ProcessingJob).filter_by(
        user_session_id=user_session_id
    ).all()
    
    job_ids = [job.id for job in user_jobs]
    
    # Find all annotations by this user for this audio file
    annotations = db.query(AnnotationSurrogate).filter(
        AnnotationSurrogate.processing_job_id.in_(job_ids),
        AnnotationSurrogate.audio_file_hash == audio_file_hash,
    ).all()
    
    return annotations


def get_disagreement_segments_for_audio(db, audio_file_hash: str) -> list:
    """
    Get all segments where users disagreed on annotations.
    
    Args:
        db: Database session
        audio_file_hash: Hash of audio file
    
    Returns:
        List of disagreement records with segment details
    """
    disagreements = db.query(UserAnnotationAgreement).filter(
        UserAnnotationAgreement.audio_file_hash == audio_file_hash,
        UserAnnotationAgreement.agreement_level != "complete",
    ).all()
    
    return disagreements


if __name__ == "__main__":
    # Initialize database when run directly
    init_db()
