"""Database models and connection management for audio anonymization platform."""

import os
from datetime import datetime
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Processing strategy
    processing_strategy = Column(String(50), nullable=True)  # 'direct' or 'fit'
    
    def __repr__(self):
        return f"<AnnotationSurrogate(job_id={self.processing_job_id}, {self.start_sec:.2f}s-{self.end_sec:.2f}s, surrogate={self.surrogate_name})>"


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


if __name__ == "__main__":
    # Initialize database when run directly
    init_db()
