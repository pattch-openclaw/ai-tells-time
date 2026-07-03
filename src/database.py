"""
Database module for AI Tells Time.

This module provides SQLite-based storage for inference results.
"""

import sqlite3
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone


class Database:
    """
    SQLite database manager for inference results.
    """

    def __init__(self, db_path: Path):
        """
        Initialize the database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        cursor = self._conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inference_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference_system_time TIMESTAMP NOT NULL,
                model_name TEXT NOT NULL,
                provider_family TEXT NOT NULL,
                time_guess TEXT NOT NULL,
                inference_failure BOOLEAN NOT NULL DEFAULT 0,
                captured_image_filename TEXT,
                parsed_time TIMESTAMP,
                guessed_offset_minutes INTEGER,
                is_accurate BOOLEAN NOT NULL DEFAULT 0,
                webcam_model TEXT,
                clock_model TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Index for recent accuracy queries (last X hours)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reference_time 
            ON inference_results(reference_system_time)
        """)
        
        # Composite index for accurate/inaccurate filtering with time range
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accuracy_time 
            ON inference_results(is_accurate, reference_system_time)
        """)
        
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()

    def save_inference_result(
        self,
        reference_system_time: datetime,
        model_name: str,
        provider_family: str,
        time_guess: str,
        inference_failure: bool,
        captured_image_filename: Optional[str] = None,
        parsed_time: Optional[datetime] = None,
        guessed_offset_minutes: Optional[int] = None,
        is_accurate: bool = False,
        webcam_model: Optional[str] = None,
        clock_model: Optional[str] = None,
    ) -> int:
        """
        Save an inference result to the database.
        
        Returns:
            The ID of the inserted row
        """
        cursor = self._conn.cursor()
        
        cursor.execute("""
            INSERT INTO inference_results (
                reference_system_time,
                model_name,
                provider_family,
                time_guess,
                inference_failure,
                captured_image_filename,
                parsed_time,
                guessed_offset_minutes,
                is_accurate,
                webcam_model,
                clock_model
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            reference_system_time.astimezone(timezone.utc).isoformat(),
            model_name,
            provider_family,
            time_guess,
            1 if inference_failure else 0,
            captured_image_filename,
            parsed_time.astimezone(timezone.utc).isoformat() if parsed_time else None,
            guessed_offset_minutes,
            1 if is_accurate else 0,
            webcam_model,
            clock_model,
        ))
        
        self._conn.commit()
        return cursor.lastrowid

    def get_recent_accuracy(
        self,
        hours: int = 1,
        provider_family: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> float:
        """
        Calculate accuracy rate over the last X hours.
        
        Returns:
            Accuracy rate as a float (0.0 to 1.0)
        """
        cursor = self._conn.cursor()
        
        cursor.execute(f"""
            SELECT AVG(is_accurate) as accuracy
            FROM inference_results
            WHERE reference_system_time > datetime('now', '-{hours} hours')
              AND inference_failure = 0
        """)
        
        result = cursor.fetchone()
        return float(result["accuracy"]) if result["accuracy"] is not None else 0.0

    def get_overall_accuracy(
        self,
        provider_family: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> float:
        """
        Calculate overall accuracy rate.
        
        Returns:
            Accuracy rate as a float (0.0 to 1.0)
        """
        cursor = self._conn.cursor()
        
        query = """
            SELECT AVG(is_accurate) as accuracy
            FROM inference_results
            WHERE inference_failure = 0
        """
        params = []
        
        if provider_family:
            query += " AND provider_family = ?"
            params.append(provider_family)
        
        if model_name:
            query += " AND model_name = ?"
            params.append(model_name)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        return float(result["accuracy"]) if result["accuracy"] is not None else 0.0


# Database instances
_DEV_DB_PATH = Path(__file__).parent.parent.parent / "data" / "dev_inference.db"
_PROD_DB_PATH = Path(__file__).parent.parent.parent / "data" / "prod_inference.db"

_dev_db: Optional[Database] = None
_prod_db: Optional[Database] = None


def get_dev_database() -> Database:
    """Get the development database instance."""
    global _dev_db
    if _dev_db is None:
        _dev_db = Database(_DEV_DB_PATH)
    return _dev_db


def get_prod_database() -> Database:
    """Get the production database instance."""
    global _prod_db
    if _prod_db is None:
        _prod_db = Database(_PROD_DB_PATH)
    return _prod_db


def get_database() -> Database:
    """
    Get the current database instance.
    
    Uses environment variable DATABASE_ENV to determine which database to use.
    Defaults to development database if not set.
    """
    import os
    env = os.getenv("DATABASE_ENV", "dev").lower()
    
    if env == "prod":
        return get_prod_database()
    else:
        return get_dev_database()


def cleanup_database() -> None:
    """Clean up all database connections."""
    global _dev_db, _prod_db
    if _dev_db:
        _dev_db.close()
        _dev_db = None
    if _prod_db:
        _prod_db.close()
        _prod_db = None
