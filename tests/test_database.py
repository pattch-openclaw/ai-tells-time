"""
Tests for the database module.
"""

import pytest
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from src.database import Database, cleanup_database


@pytest.fixture(autouse=True)
def setup_test_db():
    """Set up a test database and clean up after tests."""
    # Use a test-specific database path
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
        WHERE type='index' AND name IN ('idx_reference_time', 'idx_accuracy_time')
    """)
    indexes = cursor.fetchall()
    assert len(indexes) == 2


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
    
    # Verify the result was saved
    cursor = db._conn.cursor()
    cursor.execute("SELECT * FROM inference_results WHERE id = ?", (result_id,))
    row = cursor.fetchone()
    assert row["model_name"] == "gemini-1.5-flash"
    assert row["provider_family"] == "gemini"
    assert row["is_accurate"] == 1


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


def test_provider_filter(setup_test_db):
    """Test filtering by provider family."""
    db = setup_test_db
    now = datetime.now()
    
    # Save results for different providers
    for provider in ["gemini", "openai"]:
        for i in range(5):
            is_accurate = i < 3  # 60% accuracy for each
            db.save_inference_result(
                reference_system_time=now,
                model_name=f"{provider}-model",
                provider_family=provider,
                time_guess=f"{i}:00",
                inference_failure=False,
                guessed_offset_minutes=5 if not is_accurate else 0,
                is_accurate=is_accurate,
            )
    
    # Verify filtering works
    gemini_accuracy = db.get_overall_accuracy(provider_family="gemini")
    assert gemini_accuracy == pytest.approx(0.6, rel=0.01)


def test_model_filter(setup_test_db):
    """Test filtering by model name."""
    db = setup_test_db
    now = datetime.now()
    
    # Save results for different models
    for model in ["gemini-1.5-flash", "gemini-2.0-flash"]:
        is_accurate = True
        db.save_inference_result(
            reference_system_time=now,
            model_name=model,
            provider_family="gemini",
            time_guess="12:00",
            inference_failure=False,
            guessed_offset_minutes=0,
            is_accurate=is_accurate,
        )
    
    # Verify filtering by specific model works
    flash_accuracy = db.get_overall_accuracy(model_name="gemini-1.5-flash")
    assert flash_accuracy == 1.0


def test_time_based_filtering_with_iso_timestamps(setup_test_db):
    """Test that time-based filtering works correctly with ISO-format timestamps."""
    db = setup_test_db
    now = datetime.now(timezone.utc)
    
    # Save a record from 30 minutes ago (should be within 1 hour)
    db.save_inference_result(
        reference_system_time=now - timedelta(minutes=30),
        model_name="test-model",
        provider_family="test",
        time_guess="12:00",
        inference_failure=False,
        guessed_offset_minutes=5,
        is_accurate=True,
    )
    
    # Save a record from 2 hours ago (should NOT be within 1 hour)
    db.save_inference_result(
        reference_system_time=now - timedelta(hours=2),
        model_name="test-model",
        provider_family="test",
        time_guess="12:00",
        inference_failure=False,
        guessed_offset_minutes=5,
        is_accurate=True,
    )
    
    # Verify 1-hour filtering works (should only return 30-min record)
    accuracy_1h = db.get_recent_accuracy(hours=1)
    assert accuracy_1h == pytest.approx(1.0)  # Only the recent record is counted
    
    offsets_1h = db.get_offset_over_time(hours=1)
    assert len(offsets_1h) == 1  # Only 1 record within 1 hour
    
    # Verify 3-hour filtering works (should return both records)
    accuracy_3h = db.get_recent_accuracy(hours=3)
    assert accuracy_3h == pytest.approx(1.0)  # Both records are accurate
    
    offsets_3h = db.get_offset_over_time(hours=3)
    assert len(offsets_3h) == 2  # Both records within 3 hours


def test_time_based_filtering_excludes_reference_model(setup_test_db):
    """Test that reference model is excluded from accuracy calculations."""
    db = setup_test_db
    now = datetime.now()
    
    # Save a regular model result
    db.save_inference_result(
        reference_system_time=now,
        model_name="gemini-1.5-flash",
        provider_family="gemini",
        time_guess="12:00",
        inference_failure=False,
        guessed_offset_minutes=0,
        is_accurate=True,
    )
    
    # Save a reference model result
    db.save_inference_result(
        reference_system_time=now,
        model_name="reference",
        provider_family="reference",
        time_guess="12:00",
        inference_failure=False,
        guessed_offset_minutes=0,
        is_accurate=True,
    )
    
    # Verify reference model is excluded from overall accuracy
    accuracy = db.get_overall_accuracy()
    assert accuracy == 1.0  # Only the gemini result is counted
    assert db.get_total_inferences() == 1  # Only 1 non-reference inference
