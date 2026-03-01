"""
Database handler for IOA (Inter-Operator Agreement) database
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.ioa_models import Base
import os

# Use DATABASE_URL from environment or default to local PostgreSQL
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://audio_user:audio_dev_password@postgres:5432/audio_anony"
)
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
