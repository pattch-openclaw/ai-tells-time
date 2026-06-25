import pytest
from pathlib import Path
from src.inference import get_provider, ReferenceProvider, OpenAIProvider, ClaudeProvider, extract_time_from_text

def test_extract_time_from_text():
    assert extract_time_from_text("The time is 12:34") == "12:34"
    assert extract_time_from_text("I think it's 3:15 PM") == "15:15"
    assert extract_time_from_text("09:00 AM") == "09:00"
    assert extract_time_from_text("Just 8 AM") == "08:00"
    assert extract_time_from_text("Maybe 8 PM or so") == "20:00"

@pytest.mark.asyncio
async def test_reference_provider_format():
    provider = ReferenceProvider()
    assert provider.name == "reference"
    
    # tell_time should return format HH:MM (PST) in 12h format
    time_str = await provider.tell_time(Path("dummy.png"))
    assert "(PST)" in time_str
    
    # Should not have 24h format if > 12
    # Though difficult to mock datetime easily without freezegun, 
    # we can just ensure parse_response passes it through
    assert await provider.parse_response(time_str) == time_str

@pytest.mark.asyncio
async def test_structured_output_parsing():
    openai = OpenAIProvider()
    claude = ClaudeProvider()
    
    # Test valid JSON parsing
    json_response = '{"time_hh_mm": "07:30"}'
    assert await openai.parse_response(json_response) == "07:30"
    assert await claude.parse_response(json_response) == "07:30"
    
    # Test fallback parsing
    text_response = "The JSON broke but it is 08:45 AM"
    assert await openai.parse_response(text_response) == "08:45"
    assert await claude.parse_response(text_response) == "08:45"

from unittest.mock import patch
import datetime
import zoneinfo

@pytest.mark.asyncio
async def test_reference_provider_12h_format():
    provider = ReferenceProvider()
    
    import datetime
    import zoneinfo
    
    mock_now = datetime.datetime(2026, 6, 24, 19, 50, tzinfo=zoneinfo.ZoneInfo("America/Los_Angeles"))
    
    with patch("src.inference.__init__.datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_now
        time_str = await provider.tell_time(Path("dummy.png"))
        assert time_str == "07:50 (PST)", f"Expected 07:50 (PST), got {time_str}"
