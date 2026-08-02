"""
Inference module for AI Tells Time.

This module provides shared boilerplate for prompting AI models uniformly
across providers and parsing structured output.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import os
from pydantic import BaseModel


class BaseInferenceProvider(ABC):
    """Base class for all inference providers."""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    async def tell_time(self, image_path: Path) -> str:
        """
        Analyze a clock image and return the time as text.
        
        Args:
            image_path: Path to the clock image to analyze
            
        Returns:
            Text response from the AI model (e.g., "It's 3:15")
        """
        pass
    
    @abstractmethod
    async def parse_response(self, raw_response: str) -> Optional[str]:
        """
        Parse the raw AI response to extract the time.
        
        Args:
            raw_response: Raw text from the AI model
            
        Returns:
            Parsed time string, or None if parsing failed
        """
        pass
    
    @abstractmethod
    async def handle_error(self, error: Exception, attempt: int) -> bool:
        """
        Handle errors from API calls.
        
        Args:
            error: The exception that occurred
            attempt: Current attempt number (1-indexed)
            
        Returns:
            True if should retry, False if should give up
        """
        pass

    def get_time_string(self, time_result: str) -> str:
        """Format the time string for OBS output."""
        return f"{self.name.upper()}: {time_result}"

    def get_model_detail_string(self) -> str:
        """Format the model detail string for OBS output."""
        provider_display = self.name.title().replace("Openai", "OpenAI")
        model_str = getattr(self, "model_name", getattr(self, "model", "Unknown"))
        return f"{provider_display}: {model_str}"

    def get_placeholder_text(self) -> str:
        """Get the placeholder text to show while waiting for inference."""
        return "..."


# Shared prompt templates
PROMPT_TEMPLATES = {
    "default": "What time is shown in this image? Just tell me the time in format 'HH:MM'.",
    "detailed": (
        "Analyze this clock image and tell me the time. "
        "If the image is unclear or shows something unusual, describe what you see and make your best guess. "
        "Respond with just the time in format 'HH:MM'."
    ),
    "hallucination_friendly": (
        "This is a test of your visual perception. Look at the clock image "
        "and tell me what time it shows. Don't worry about being perfectly accurate - "
        "just tell me what you think you see. Format: 'HH:MM'."
    ),
}

# Default prompt to use
DEFAULT_PROMPT = PROMPT_TEMPLATES["default"]


def format_prompt(prompt_type: str = "default") -> str:
    """
    Get a formatted prompt for clock time inference.
    
    Args:
        prompt_type: Type of prompt to use (default, detailed, hallucination_friendly)
        
    Returns:
        Formatted prompt string
    """
    return PROMPT_TEMPLATES.get(prompt_type, DEFAULT_PROMPT)


def extract_time_from_text(text: str) -> Optional[str]:
    """
    Try to extract a time (HH:MM format) from arbitrary text.
    
    Args:
        text: Text that may contain a time
        
    Returns:
        Extracted time string in HH:MM format, or None if not found
    """
    import re
    
    # Try to find time patterns like "12:34", "3:15 PM", "09:00"
    time_patterns = [
        r'\b([01]?\d):([0-5]\d)\s*([APap][Mm])?\b',  # HH:MM with optional AM/PM
        r'\b([01]?\d)\s*([APap][Mm])\b',  # Just HH with AM/PM (added capture group for AM/PM)
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            hour = int(groups[0])
            
            # If the matched pattern has 3 groups (or 2 and the 2nd is a number), 
            # groups[1] is minutes. If groups[1] is AM/PM, minutes is 0.
            if len(groups) > 1 and groups[1] is not None:
                if groups[1].upper() in ['AM', 'PM']:
                    minute = 0
                else:
                    minute = int(groups[1])
            else:
                minute = 0
            
            # Handle AM/PM conversion
            # Find the AM/PM string in the groups
            am_pm_group = None
            for g in groups[1:]:
                if g and isinstance(g, str) and g.upper() in ['AM', 'PM']:
                    am_pm_group = g
                    break
            
            if am_pm_group:
                is_pm = am_pm_group.upper() == 'PM'
                if is_pm and hour < 12:
                    hour += 12
                elif not is_pm and hour == 12:
                    hour = 0
            
            return f"{hour:02d}:{minute:02d}"
    
    return None


def truncate_output(text: str, max_length: int = 50) -> str:
    """
    Truncate output text, showing truncation with ellipsis.
    
    Args:
        text: Text to truncate
        max_length: Maximum characters to show
        
    Returns:
        Truncated text with ... if it was cut off
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


# Shared output schema
class TimeResponse(BaseModel):
    """Structured output schema for the AI to conform to."""
    time_hh_mm: str


class OpenAIProvider(BaseInferenceProvider):
    """OpenAI GPT-4o-mini provider for time inference."""
    
    def __init__(self, model_name: str = "gpt-4o-mini"):
        super().__init__("openai")
        self.model_name = model_name
        self._client = None
        
    @property
    def client(self):
        if self._client is None:
            import openai
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            self._client = openai.AsyncClient(api_key=api_key)
        return self._client
    
    async def tell_time(self, image_path: Path) -> str:
        import base64
        
        # Encode image to base64
        image_bytes = image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        
        prompt = format_prompt("default")
        
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=300,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "time_response",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "time_hh_mm": {
                                "type": "string"
                            }
                        },
                        "required": ["time_hh_mm"],
                        "additionalProperties": False
                    }
                }
            }
        )
        return response.choices[0].message.content or ""
    
    async def parse_response(self, raw_response: str) -> Optional[str]:
        import json
        try:
            data = json.loads(raw_response)
            if "time_hh_mm" in data:
                return data["time_hh_mm"]
        except Exception:
            pass
        return extract_time_from_text(raw_response)
    
    async def handle_error(self, error: Exception, attempt: int) -> bool:
        print(f"OpenAI API Error (Attempt {attempt}): {error}")
        return attempt < 3


class GeminiProvider(BaseInferenceProvider):
    """Google Gemini provider for time inference using Structured Outputs."""
    
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        super().__init__("gemini")
        self.model_name = model_name
        self._client = None
        
    @property
    def client(self):
        if self._client is None:
            from google import genai
            api_key = os.getenv("GEMINI_API_KEY")
            self._client = genai.Client(api_key=api_key)
        return self._client
    
    async def tell_time(self, image_path: Path) -> str:
        from google.genai import types
        
        image_bytes = image_path.read_bytes()
        prompt = format_prompt("default")
        
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TimeResponse,
                temperature=0.7,
            )
        )
        return response.text
    
    async def parse_response(self, raw_response: str) -> Optional[str]:
        import json
        try:
            # We expect strict JSON from the structured output
            data = json.loads(raw_response)
            if "time_hh_mm" in data:
                return data["time_hh_mm"]
        except Exception:
            pass
            
        # Fallback to the default regex extraction if JSON fails somehow
        return extract_time_from_text(raw_response)
    
    async def handle_error(self, error: Exception, attempt: int) -> bool:
        print(f"Gemini API Error (Attempt {attempt}): {error}")
        return attempt < 3


class ClaudeProvider(BaseInferenceProvider):
    """Anthropic Claude provider for time inference."""
    
    def __init__(self, model_name: str = "claude-haiku-4-5"):
        super().__init__("claude")
        self.model_name = model_name
        self._client = None
        
    @property
    def client(self):
        if self._client is None:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            self._client = anthropic.AsyncClient(api_key=api_key)
        return self._client
    
    async def tell_time(self, image_path: Path) -> str:
        import base64
        
        # Encode image to base64
        image_bytes = image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        
        prompt = format_prompt("default")
        
        response = await self.client.messages.create(
            model=self.model_name,
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_b64,
                            },
                        },
                    ],
                }
            ],
            tools=[
                {
                    "name": "record_time",
                    "description": "Record the time shown on the clock",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "time_hh_mm": {
                                "type": "string",
                                "description": "The time in HH:MM format"
                            }
                        },
                        "required": ["time_hh_mm"]
                    }
                }
            ],
            tool_choice={"type": "tool", "name": "record_time"}
        )
        
        import json
        for block in response.content:
            if getattr(block, "type", "") == "tool_use" and getattr(block, "name", "") == "record_time":
                return json.dumps(block.input)
                
        return ""
    
    async def parse_response(self, raw_response: str) -> Optional[str]:
        import json
        try:
            data = json.loads(raw_response)
            if "time_hh_mm" in data:
                return data["time_hh_mm"]
        except Exception:
            pass
        return extract_time_from_text(raw_response)
    
    async def handle_error(self, error: Exception, attempt: int) -> bool:
        print(f"Claude API Error (Attempt {attempt}): {error}")
        return attempt < 3


class LocalProvider(BaseInferenceProvider):
    """Local provider for time inference (via Ollama)."""
    
    def __init__(self, model: str = "qwen2.5vl:7b"):
        super().__init__("local")
        self.model = model
        self.base_url = "http://localhost:11434"

    def get_time_string(self, time_result: str) -> str:
        # Note: We use two spaces after the colon to align the 5-character "LOCAL" 
        # label with the 6-character provider names (GEMINI, OPENAI, CLAUDE) in monospace fonts.
        return f"{self.name.upper()}:  {time_result}"

    def get_model_detail_string(self) -> str:
        provider_display = self.name.title()
        model_str = getattr(self, "model_name", getattr(self, "model", "Unknown"))
        # Note: We use two spaces after the colon to align the 5-character "Local" 
        # label with the 6-character provider names (Gemini, OpenAI, Claude) in monospace fonts.
        return f"{provider_display}:  {model_str}"
    
    async def tell_time(self, image_path: Path) -> str:
        import base64
        import aiohttp
        
        # Encode image to base64
        image_bytes = image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        
        prompt = format_prompt("default")
        
        # Build request payload for Ollama API
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error: {response.status} - {error_text}")
                
                result = await response.json()
                return result.get("response", "")
    
    async def parse_response(self, raw_response: str) -> Optional[str]:
        return extract_time_from_text(raw_response)
    
    async def handle_error(self, error: Exception, attempt: int) -> bool:
        print(f"Ollama API Error (Attempt {attempt}): {error}")
        return attempt < 3


import datetime
import zoneinfo

class ReferenceProvider(BaseInferenceProvider):
    """Reference provider that just returns the current system time."""
    
    def __init__(self):
        super().__init__("reference")
        
    def get_time_string(self, time_result: str) -> str:
        # User wants "ACTUAL: HH:MM (PST)" output style
        return f"ACTUAL: {time_result}"
        
    def get_model_detail_string(self) -> str:
        return "Reference: System Clock"
        
    def get_placeholder_text(self) -> str:
        import datetime
        import zoneinfo
        now = datetime.datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
        return now.strftime("%I:%M (PST)")
        
    async def tell_time(self, image_path: Path) -> str:
        # Use PST (America/Los_Angeles)
        now = datetime.datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
        return now.strftime("%I:%M (PST)")
        
    async def parse_response(self, raw_response: str) -> Optional[str]:
        # Return as-is since we generated it perfectly
        return raw_response
        
    async def handle_error(self, error: Exception, attempt: int) -> bool:
        return False


def get_provider(provider_name: str, **kwargs) -> BaseInferenceProvider:
    """
    Factory function to get an inference provider by name.
    
    Args:
        provider_name: Name of the provider (openai, gemini, claude, local, reference)
        **kwargs: Additional arguments to pass to the provider constructor
        
    Returns:
        Configured provider instance
        
    Raises:
        ValueError: If provider name is unknown
    """
    providers = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "local": LocalProvider,
        "reference": ReferenceProvider,
    }
    
    provider_class = providers.get(provider_name.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(providers.keys())}")
    
    return provider_class(**kwargs)
