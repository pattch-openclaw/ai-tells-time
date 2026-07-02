"""
Database module for AI Tells Time.

This module provides SQLite-based storage for inference results with support
for both development and production environments.
"""

import sqlite3
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
import os


class Database:
    """
    SQLite database manager for inference results.
    
    Supports dev and prod instances to allow safe local testing
    without affecting production data.
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
        
        # Detect database dialect
        self._dialect = "sqlite"
        self._is_postgresql = False
    
    def _detect_dialect(self) -> str:
        """Detect the database dialect (sqlite or postgresql)."""
        cursor = self._conn.cursor()
        try:
            cursor.execute("SELECT version()")
            cursor.fetchone()
            return "postgresql"
        except:
            return "sqlite"
    
    def time_range_filter(self, hours: int) -> str:
        """
        Generate a time range filter expression for the current database dialect.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            SQL expression string (dialect-specific)
        """
        if self._is_postgresql or self._dialect == "postgresql":
            return f"reference_system_time > NOW() - INTERVAL '{hours} hours'"
        else:
            # SQLite
            return f"reference_system_time > datetime('now', '-{hours} hours')"
    
    def boolean_literal(self, value: bool) -> str:
        """
        Generate a boolean literal for the current database dialect.
        
        Args:
            value: Boolean value
            
        Returns:
            SQL boolean literal string
        """
        if self._is_postgresql or self._dialect == "postgresql":
            return "TRUE" if value else "FALSE"
        else:
            return "1" if value else "0"
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        cursor = self._conn.cursor()
        
        # Enable PostgreSQL compatibility pragmas
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inference_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference_system_time TIMESTAMP NOT NULL,
                model_name TEXT NOT NULL,
                provider_family TEXT NOT NULL,
                time_guess TEXT NOT NULL,
                inference_failure BOOLEAN NOT NULL DEFAULT FALSE,
                captured_image_filename TEXT,
                parsed_time TIMESTAMP,
                guessed_offset_minutes INTEGER,
                is_accurate BOOLEAN NOT NULL DEFAULT FALSE,
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
        
        # Index for provider/model filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_provider_family 
            ON inference_results(provider_family)
        """)
        
        # Index for model-specific queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_name 
            ON inference_results(model_name)
        """)
        
        # Composite index for accurate/inaccurate filtering with time range
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accuracy_time 
            ON inference_results(is_accurate, reference_system_time)
        """)
        
        # Index for sum of guessed_offset_minutes over time range
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_offset_time 
            ON inference_results(guessed_offset_minutes, reference_system_time)
        """)
        
        # Index for webcam model filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_webcam_model 
            ON inference_results(webcam_model)
        """)
        
        # Index for clock model filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clock_model 
            ON inference_results(clock_model)
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
            reference_system_time: The reference system time when image was captured
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
            inference_failure,  # PostgreSQL-compatible: bool → int coercion
            captured_image_filename,
            parsed_time.astimezone(timezone.utc).isoformat() if parsed_time else None,
            guessed_offset_minutes,
            is_accurate,  # PostgreSQL-compatible: bool → int coercion
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
        
        # Build the base query with dynamic hours
        time_filter = self.time_range_filter(hours)
        query = f"""
            SELECT AVG(is_accurate) as accuracy
            FROM inference_results
            WHERE {time_filter}
              AND inference_failure = FALSE
        """
        params = []
        
        # Add filters if provided
        if provider_family:
            query += " AND provider_family = ?"
            params.append(provider_family)
        
        if model_name:
            query += " AND model_name = ?"
            params.append(model_name)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        return float(result["accuracy"]) if result["accuracy"] is not None else 0.0
    
    def get_overall_accuracy(
        self,
        provider_family: Optional[str] = None,
        model_name: Optional[str] = None,
        include_local: bool = True,
        include_external: bool = False,
        external_db_path: Optional[Path] = None,
    ) -> float:
        """
        Calculate overall accuracy rate.
        
        Args:
            provider_family: Optional filter for provider family
            model_name: Optional filter for specific model name
            include_local: Whether to include local SQLite data
            include_external: Whether to include external database data (Supabase/PostgreSQL)
            external_db_path: Path to external database (if not using connection string)
            
        Returns:
            Accuracy rate as a float (0.0 to 1.0)
        """
        results = []
        
        if include_local:
            local_results = self._query_accuracy("local", provider_family, model_name)
            results.extend(local_results)
        
        if include_external and external_db_path:
            # Query external database
            external_conn = sqlite3.connect(external_db_path)
            external_conn.row_factory = sqlite3.Row
            try:
                external_results = self._query_accuracy("external", provider_family, model_name, conn=external_conn)
                results.extend(external_results)
            finally:
                external_conn.close()
        
        if not results:
            return 0.0
        
        # Calculate weighted average
        total_accurate = sum(1 for r in results if r["is_accurate"])
        return float(total_accurate / len(results))
    
    def _query_accuracy(
        self,
        db_type: str,
        provider_family: Optional[str],
        model_name: Optional[str],
        conn: Optional[sqlite3.Connection] = None,
    ) -> list:
        """
        Query accuracy data from a database.
        
        Args:
            db_type: "local" or "external" (affects how we build the query)
            provider_family: Optional filter
            model_name: Optional filter
            conn: Database connection (uses self._conn if None)
            
        Returns:
            List of row dictionaries with is_accurate field
        """
        if conn is None:
            conn = self._conn
        
        cursor = conn.cursor()
        
        # Build the base query
        query = """
            SELECT is_accurate
            FROM inference_results
            WHERE inference_failure = FALSE
        """
        params = []
        
        # Add filters if provided
        if provider_family:
            query += " AND provider_family = ?"
            params.append(provider_family)
        
        if model_name:
            query += " AND model_name = ?"
            params.append(model_name)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_average_offset(
        self,
        hours: int = None,
        provider_family: Optional[str] = None,
        model_name: Optional[str] = None,
        include_local: bool = True,
        include_external: bool = False,
        external_db_path: Optional[Path] = None,
    ) -> float:
        """
        Calculate average absolute offset in minutes.
        
        Args:
            hours: Optional number of hours to look back (None for all time)
            provider_family: Optional filter for provider family
            model_name: Optional filter for specific model name
            include_local: Whether to include local SQLite data
            include_external: Whether to include external database data (Supabase/PostgreSQL)
            external_db_path: Path to external database (if not using connection string)
            
        Returns:
            Average absolute offset as a float
        """
        offsets = []
        
        if include_local:
            local_offsets = self._query_offsets("local", hours, provider_family, model_name)
            offsets.extend(local_offsets)
        
        if include_external and external_db_path:
            external_conn = sqlite3.connect(external_db_path)
            try:
                external_offsets = self._query_offsets("external", hours, provider_family, model_name, conn=external_conn)
                offsets.extend(external_offsets)
            finally:
                external_conn.close()
        
        if not offsets:
            return 0.0
        
        return float(sum(offsets) / len(offsets))
    
    def _query_offsets(
        self,
        db_type: str,
        hours: int,
        provider_family: Optional[str],
        model_name: Optional[str],
        conn: Optional[sqlite3.Connection] = None,
    ) -> list:
        """
        Query offset data from a database.
        
        Args:
            db_type: "local" or "external"
            hours: Optional time filter
            provider_family: Optional filter
            model_name: Optional filter
            conn: Database connection (uses self._conn if None)
            
        Returns:
            List of offset values
        """
        if conn is None:
            conn = self._conn
        
        cursor = conn.cursor()
        
        # Build the base query
        query = """
            SELECT guessed_offset_minutes
            FROM inference_results
            WHERE guessed_offset_minutes IS NOT NULL
              AND inference_failure = FALSE
        """
        params = []
        
        # Add time filter if provided
        if hours is not None:
            time_filter = self.time_range_filter(hours)
            query += f" AND {time_filter}"
        
        # Add filters if provided
        if provider_family:
            query += " AND provider_family = ?"
            params.append(provider_family)
        
        if model_name:
            query += " AND model_name = ?"
            params.append(model_name)
        
        cursor.execute(query, params)
        return [row["guessed_offset_minutes"] for row in cursor.fetchall()]
    
    def get_recent_results(
        self,
        limit: int = 10,
        provider_family: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> list:
        """
        Get recent inference results.
        
        Args:
            limit: Maximum number of results to return
            provider_family: Optional filter for provider family
            model_name: Optional filter for specific model name
            
        Returns:
            List of result dictionaries
        """
        cursor = self._conn.cursor()
        
        query = """
            SELECT * FROM inference_results
            WHERE 1=1
        """
        params = []
        
        if provider_family:
            query += " AND provider_family = ?"
            params.append(provider_family)
        
        if model_name:
            query += " AND model_name = ?"
            params.append(model_name)
        
        query += " ORDER BY reference_system_time DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        return [dict(row) for row in results]


# Database instances
_DEV_DB_PATH = Path(__file__).parent.parent.parent / "data" / "dev_inference.db"
_PROD_DB_PATH = Path(__file__).parent.parent.parent / "data" / "prod_inference.db"

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
    Defaults to development database if not set.
    
    Returns:
        Database instance based on current environment
    """
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
