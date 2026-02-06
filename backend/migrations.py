"""
Database migration script to add AnnotationSurrogate table.
Run this script to update the database schema.
"""

import os
import sys
import logging
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine, Base, AnnotationSurrogate

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def migrate_add_annotation_surrogate_table():
    """Add the AnnotationSurrogate table to track individual annotation processing."""
    
    log.info("Starting migration: Adding AnnotationSurrogate table")
    
    try:
        # Check if table already exists
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'annotation_surrogates'
                );
            """))
            exists = result.scalar()
            
            if exists:
                log.info("AnnotationSurrogate table already exists, skipping creation")
                return True
        
        # Create the table
        log.info("Creating AnnotationSurrogate table...")
        AnnotationSurrogate.__table__.create(engine, checkfirst=True)
        log.info("AnnotationSurrogate table created successfully")
        
        # Verify table was created
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'annotation_surrogates'
                ORDER BY ordinal_position;
            """))
            columns = result.fetchall()
            log.info(f"Table columns ({len(columns)}):")
            for col_name, col_type in columns:
                log.info(f"  - {col_name}: {col_type}")
        
        return True
        
    except Exception as e:
        log.error(f"Migration failed: {e}")
        return False


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(text(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
        );
        """
    ), {"table_name": table_name, "column_name": column_name})
    return bool(result.scalar())


def _add_column_if_missing(conn, table_name: str, column_name: str, column_sql: str) -> None:
    if _column_exists(conn, table_name, column_name):
        log.info(f"{table_name}.{column_name} already exists, skipping")
        return
    log.info(f"Adding {table_name}.{column_name}")
    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))


def migrate_add_audio_file_hash_columns():
    """Add audio_file_hash columns for inter-user tracking."""
    log.info("Starting migration: Adding audio_file_hash columns")

    try:
        with engine.begin() as conn:
            _add_column_if_missing(
                conn,
                "annotation_surrogates",
                "audio_file_hash",
                "audio_file_hash VARCHAR(64) NULL"
            )
            _add_column_if_missing(
                conn,
                "processing_jobs",
                "audio_file_hash",
                "audio_file_hash VARCHAR(64) NULL"
            )
        log.info("audio_file_hash column migration completed")
        return True
    except Exception as e:
        log.error(f"audio_file_hash migration failed: {e}")
        return False


def migrate_all():
    """Run all pending migrations."""
    log.info("=" * 60)
    log.info("Running all database migrations")
    log.info("=" * 60)
    
    success = migrate_add_annotation_surrogate_table()
    if success:
        success = migrate_add_audio_file_hash_columns()
    
    if success:
        log.info("=" * 60)
        log.info("All migrations completed successfully")
        log.info("=" * 60)
    else:
        log.error("=" * 60)
        log.error("Some migrations failed")
        log.error("=" * 60)
    
    return success


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument(
        "--init-all",
        action="store_true",
        help="Initialize all tables (including existing ones)"
    )
    args = parser.parse_args()
    
    if args.init_all:
        log.info("Initializing all database tables...")
        Base.metadata.create_all(bind=engine)
        log.info("All tables initialized")
    else:
        migrate_all()
