"""
Database handler for IOA (Inter-Operator Agreement) database
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.ioa_models import Base

DB_PATH = 'sqlite:///inter_operator_agreement.db'
engine = create_engine(DB_PATH)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

# Usage:
# from backend.ioa_database import SessionLocal, init_db
# session = SessionLocal()
# ...
