"""
Tests for the record_inference.py script.
"""

import pytest
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta
from src.database import Database, cleanup_database


def cleanup_test_db(db_path):
    """Clean up test database files."""
    if db_path.exists():
        db_path.unlink()
    cleanup_database()


@pytest.fixture(autouse=True)
def setup_and_cleanup(tmp_path):
    """Set up test environment and clean up after tests."""
    test_db = tmp_path / "test_inference.db"
    yield
    cleanup_test_db(test_db)


def test_record_inference_accurate(tmp_path):
    """Test recording an accurate inference result."""
    # Use a test-specific database
    test_db = tmp_path / "test_inference.db"
    
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent.parent / "scripts" / "record_inference.py"),
            "--model", "gemini-1.5-flash",
            "--guess", "12:34",
            "--actual", "12:32",
            "--is-accurate"
        ],
        capture_output=True,
        text=True,
        env={**dict(**subprocess.os.environ), "DATABASE_ENV": "dev"}
    )
    
    assert result.returncode == 0
    assert "✅ Saved inference result" in result.stdout
    assert "Accurate: True" in result.stdout


def test_record_inference_inaccurate(tmp_path):
    """Test recording an inaccurate inference result."""
    test_db = tmp_path / "test_inference.db"
    
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent.parent / "scripts" / "record_inference.py"),
            "--model", "local",
            "--guess", "3:15",
            "--actual", "3:45",
            "--not-accurate"
        ],
        capture_output=True,
        text=True,
        env={**dict(**subprocess.os.environ), "DATABASE_ENV": "dev"}
    )
    
    assert result.returncode == 0
    assert "✅ Saved inference result" in result.stdout
    assert "Accurate: False" in result.stdout


def test_auto_accuracy_calculation(tmp_path):
    """Test that accuracy is auto-calculated based on offset."""
    test_db = tmp_path / "test_inference.db"
    
    # Within 5 minutes - should be accurate
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent.parent / "scripts" / "record_inference.py"),
            "--model", "gemini-1.5-flash",
            "--guess", "12:30",
            "--actual", "12:28"
        ],
        capture_output=True,
        text=True,
        env={**dict(**subprocess.os.environ), "DATABASE_ENV": "dev"}
    )
    
    assert result.returncode == 0
    assert "Accurate: True" in result.stdout
