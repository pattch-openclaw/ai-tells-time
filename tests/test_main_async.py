import pytest
import asyncio
from unittest.mock import MagicMock
from main import update_obs_text, obs_lock

@pytest.mark.asyncio
async def test_update_obs_text_background_thread():
    mock_client = MagicMock()
    # Test that it successfully calls set_input_settings without blocking
    await update_obs_text(mock_client, "test_source", "test text")
    
    # Verify the mock was called
    mock_client.set_input_settings.assert_called_once_with("test_source", {"text": "test text"}, True)

@pytest.mark.asyncio
async def test_update_obs_text_handles_errors_gracefully():
    mock_client = MagicMock()
    mock_client.set_input_settings.side_effect = Exception("Connection error")
    
    # Should not raise exception
    await update_obs_text(mock_client, "test_source", "test text")
