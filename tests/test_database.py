"""
Tests for the database module.
"""

import pytest
import os
from pathlib import Path
from datetime import datetime, timedelta
from src.database import (
    Database,
    get_dev_database,
    get_prod_database,
    get_database,
    cleanup_database,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Set up a test database and clean up after tests."""
    # Use a test-specific database path
    os.environ["DATABASE_ENV"] = "test"
    test_db_path = Path(__file__).parent / "data" / "test_inference.db"
    
    # Create and yield the test database
    db = Database(test_db_path)
    yield db
    
    # Cleanup
    db.close()
    if test_db_path.exists():
        test_db_path.unlink()
    cleanup_database()


def test_database_creation(setup_test_db):
    """Test that the database is created with the correct schema."""
    db = setup_test_db
    cursor = db._conn.cursor()
    
    # Check that the table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='inference_results'
    """)
    assert cursor.fetchone() is not None
    
    # Check that indexes exist
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND name IN (
            'idx_reference_time', 'idx_provider_family', 
            'idx_model_name', 'idx_accuracy_time', 'idx_offset_time'
        )
    """)
    indexes = cursor.fetchall()
    assert len(indexes) == 5


def test_save_inference_result(setup_test_db):
    """Test saving an inference result."""
    db = setup_test_db
    reference_time = datetime.now()
    
    result_id = db.save_inference_result(
        reference_system_time=reference_time,
        model_name="gemini-1.5-flash",
        provider_family="gemini",
        time_guess="12:34",
        inference_failure=False,
        captured_image_filename="test_image.png",
        parsed_time=reference_time,
        guessed_offset_minutes=5,
        is_accurate=True,
        webcam_model="Logitech C920",
        clock_model="Analog Wall Clock",
    )
    
    assert result_id > 0
    
    # Verify the new columns are saved
    cursor = db._conn.cursor()
    cursor.execute("SELECT webcam_model, clock_model FROM inference_results WHERE id = ?", (result_id,))
    row = cursor.fetchone()
    assert row["webcam_model"] == "Logitech C920"
    assert row["clock_model"] == "Analog Wall Clock"


def test_save_inference_failure(setup_test_db):
    """Test saving an inference failure."""
    db = setup_test_db
    reference_time = datetime.now()
    
    result_id = db.save_inference_result(
        reference_system_time=reference_time,
        model_name="gemini-1.5-flash",
        provider_family="gemini",
        time_guess="Banana",
        inference_failure=True,
    )
    
    assert result_id > 0
    
    # Verify the failure is recorded
    cursor = db._conn.cursor()
    cursor.execute("SELECT inference_failure FROM inference_results WHERE id = ?", (result_id,))
    assert cursor.fetchone()["inference_failure"] == 1


def test_get_recent_accuracy(setup_test_db):
    """Test calculating recent accuracy rate."""
    db = setup_test_db
    now = datetime.now()
    
    # Save some accurate and inaccurate results
    for i in range(10):
        is_accurate = i < 7  # 70% accuracy
        db.save_inference_result(
            reference_system_time=now - timedelta(hours=1),
            model_name="gemini-1.5-flash",
            provider_family="gemini",
            time_guess=f"{i}:00",
            inference_failure=False,
            guessed_offset_minutes=5 if not is_accurate else 0,
            is_accurate=is_accurate,
        )
    
    accuracy = db.get_recent_accuracy(hours=2)
    assert accuracy == pytest.approx(0.7, rel=0.01)


def test_get_overall_accuracy(setup_test_db):
    """Test calculating overall accuracy rate."""
    db = setup_test_db
    
    # Save results over different time periods
    now = datetime.now()
    for i in range(20):
        is_accurate = i < 12  # 60% accuracy
        db.save_inference_result(
            reference_system_time=now - timedelta(hours=i * 2),
            model_name="gemini-1.5-flash",
            provider_family="gemini",
            time_guess=f"{i}:00",
            inference_failure=False,
            guessed_offset_minutes=5 if not is_accurate else 0,
            is_accurate=is_accurate,
        )
    
    accuracy = db.get_overall_accuracy()
    assert accuracy == pytest.approx(0.6, rel=0.01)


def test_get_average_offset(setup_test_db):
    """Test calculating average absolute offset."""
    db = setup_test_db
    now = datetime.now()
    
    # Save results with known offsets
    for offset in [2, 4, 6, 8, 10]:
        db.save_inference_result(
            reference_system_time=now,
            model_name="gemini-1.5-flash",
            provider_family="gemini",
            time_guess="12:00",
            inference_failure=False,
            guessed_offset_minutes=offset,
            is_accurate=offset <= 5,
        )
    
    avg_offset = db.get_average_offset()
    assert avg_offset == pytest.approx(6.0, rel=0.01)  # (2+4+6+8+10)/5 = 6.0


def test_get_recent_results(setup_test_db):
    """Test retrieving recent results."""
    db = setup_test_db
    now = datetime.now()
    
    # Save multiple results
    for i in range(5):
        db.save_inference_result(
            reference_system_time=now - timedelta(minutes=i),
            model_name=f"model-{i}",
            provider_family="test",
            time_guess=f"{i}:00",
            inference_failure=False,
        )
    
    results = db.get_recent_results(limit=3)
    assert len(results) == 3
    assert results[0]["model_name"] == "model-0"  # Most recent first
