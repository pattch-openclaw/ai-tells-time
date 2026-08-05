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

        Args:
            reference_system_time: The reference system time when the image was captured
            model_name: The precise model name (e.g., "gemini-1.5-flash")
            provider_family: The provider family (e.g., "gemini", "openai", "claude", "local")
            time_guess: The raw output from the model
            inference_failure: Whether inference failed (output not parseable)
            captured_image_filename: Optional path to the captured image
            parsed_time: Optional parsed time from the guess
            guessed_offset_minutes: Optional absolute difference from reference time
            is_accurate: Whether guess was within +/- 5 minutes of reference
            webcam_model: Optional webcam model identifier
            clock_model: Optional clock model identifier

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

        Args:
            hours: Number of hours to look back
            provider_family: Optional filter for provider family
            model_name: Optional filter for specific model name

        Returns:
            Accuracy rate as a float (0.0 to 1.0)
        """
        cursor = self._conn.cursor()

        query = f"""
            SELECT AVG(is_accurate) as accuracy
            FROM inference_results
            WHERE datetime(substr(reference_system_time, 1, 19)) > datetime('now', '-{hours} hours')
              AND inference_failure = 0
        """
        params = []

        if provider_family:
            query += " AND provider_family = ?"
            params.append(provider_family)

        if model_name:
            query += " AND model_name = ?"
            params.append(model_name)
        else:
            query += " AND model_name != 'reference'"

        cursor.execute(query, params)

        result = cursor.fetchone()
        return float(result["accuracy"]) if result["accuracy"] is not None else 0.0


    def get_active_models(self) -> list[str]:
        """Get a list of all model names that have inference results."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT DISTINCT model_name FROM inference_results WHERE inference_failure = 0 AND model_name != 'reference' ORDER BY model_name"
        )
        return [row["model_name"] for row in cursor.fetchall()]

    def get_total_inferences(
        self,
        provider_family: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> int:
        """Get total number of successful inferences."""
        cursor = self._conn.cursor()
        query = "SELECT COUNT(*) as total FROM inference_results WHERE inference_failure = 0"
        params = []

        if provider_family:
            query += " AND provider_family = ?"
            params.append(provider_family)

        if model_name:
            query += " AND model_name = ?"
            params.append(model_name)
        else:
            query += " AND model_name != 'reference'"

        cursor.execute(query, params)
        result = cursor.fetchone()
        return result["total"] if result["total"] is not None else 0

    def get_overall_accuracy(
        self,
        provider_family: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> float:
        """
        Calculate overall accuracy rate.

        Args:
            provider_family: Optional filter for provider family
            model_name: Optional filter for specific model name
            
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
        else:
            query += " AND model_name != 'reference'"
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        return float(result["accuracy"]) if result["accuracy"] is not None else 0.0

    def get_offset_over_time(
        self,
        hours: int = 1,
        model_name: Optional[str] = None,
    ) -> list[dict]:
        """
        Get offset data over time for a specific model (or all models).

        Args:
            hours: Number of hours to look back
            model_name: Optional filter for specific model name
            
        Returns:
            List of dicts with reference_system_time and guessed_offset_minutes
        """
        cursor = self._conn.cursor()
        
        # Normalize timestamps to comparable format for SQLite datetime comparison
        # The stored timestamps are ISO format with timezone, so we need to handle this properly
        query = f"""
            SELECT reference_system_time, model_name, guessed_offset_minutes
            FROM inference_results
            WHERE datetime(substr(reference_system_time, 1, 19)) > datetime('now', '-{hours} hours')
              AND guessed_offset_minutes IS NOT NULL
              AND inference_failure = 0
        """
        
        if model_name:
            query += " AND model_name = ?"
            cursor.execute(query, (model_name,))
        else:
            cursor.execute(query)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "timestamp": row["reference_system_time"],
                "model_name": row["model_name"],
                "offset_minutes": row["guessed_offset_minutes"]
            })
        return results

    def get_last_inference_per_provider(self) -> list[dict]:
        """Get the most recent inference result for each provider."""
        cursor = self._conn.cursor()
        
        # Get the most recent inference for each provider family
        query = """
            SELECT provider_family, MAX(reference_system_time) as max_time
            FROM inference_results
            WHERE inference_failure = 0 AND model_name != 'reference'
            GROUP BY provider_family
            ORDER BY max_time DESC
        """
        cursor.execute(query)
        
        results = []
        for row in cursor.fetchall():
            # Get the full record for this provider's latest inference
            cursor2 = self._conn.cursor()
            cursor2.execute(
                "SELECT * FROM inference_results WHERE reference_system_time = ? AND provider_family = ?",
                (row["max_time"], row["provider_family"])
            )
            record = cursor2.fetchone()
            if record:
                results.append({
                    "provider_family": record["provider_family"],
                    "accuracy": float(record["is_accurate"]),
                    "model_name": record["model_name"],
                    "reference_system_time": record["reference_system_time"]
                })
        
        return results
    
    def get_latest_timestamp(self) -> Optional[datetime]:
        """Get the most recent timestamp from inference results."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT reference_system_time FROM inference_results ORDER BY reference_system_time DESC LIMIT 1"
        )
        result = cursor.fetchone()
        if result:
            return datetime.fromisoformat(result["reference_system_time"].replace("Z", "+00:00"))
        return None


# Database instances
_DEV_DB_PATH = Path(__file__).parent.parent / "data" / "dev_inference.db"
_PROD_DB_PATH = Path(__file__).parent.parent / "data" / "prod_inference.db"

_dev_db: Optional[Database] = None
_prod_db: Optional[Database] = None


def get_dev_database() -> Database:
    """
    Get the development database instance.

    Returns:
        Database instance for development
    """
    global _dev_db
    if _dev_db is None:
        _dev_db = Database(_DEV_DB_PATH)
    return _dev_db


def get_prod_database() -> Database:
    """
    Get the production database instance.

    Returns:
        Database instance for production
    """
    global _prod_db
    if _prod_db is None:
        _prod_db = Database(_PROD_DB_PATH)
    return _prod_db


def get_database() -> Database:
    """
    Get the current database instance.

    Uses environment variable DATABASE_ENV to determine which database to use.
    If not set, defaults to prod when running on the Mac Mini (production).

    Returns:
        Database instance based on current environment
    """
    import os

    # Check explicit DATABASE_ENV setting
    env = os.getenv("DATABASE_ENV", "").lower()

    if env == "prod":
        return get_prod_database()
    elif env == "dev":
        return get_dev_database()

    # No explicit setting - default to prod on Mac Mini (production)
    # Check for Mac Mini hostname or presence of production environment indicators
    import platform
    hostname = os.getenv("HOSTNAME", "").lower()

    # Mac Mini typically has hostname containing "mini" or specific naming
    if "mini" in hostname or "macmini" in hostname:
        return get_prod_database()

    # Default to dev for local development (e.g., on laptop/workstation)
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
