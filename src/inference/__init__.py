"""
Inference module for AI Tells Time.

This module provides shared boilerplate for prompting AI models uniformly
across providers and parsing structured output.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path


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
        r'\b([01]?\d)\s*(?:AM|PM|am|pm)\b',  # Just HH with AM/PM
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            hour = int(groups[0])
            minute = int(groups[1])
            
            # Handle AM/PM conversion
            if len(groups) > 2 and groups[2]:
                is_pm = groups[2].upper() == 'PM'
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


# Placeholder provider implementations (to be filled in later)

class OpenAIProvider(BaseInferenceProvider):
    """OpenAI GPT-4o-mini provider for time inference."""
    
    def __init__(self):
        super().__init__("openai")
        # TODO: Implement API key loading and client setup
    
    async def tell_time(self, image_path: Path) -> str:
        # TODO: Implement OpenAI API call
        return "OpenAI provider not yet implemented"
    
    async def parse_response(self, raw_response: str) -> Optional[str]:
        # TODO: Implement response parsing
        return extract_time_from_text(raw_response)
    
    async def handle_error(self, error: Exception, attempt: int) -> bool:
        # TODO: Implement error handling
        return attempt < 3


from pydantic import BaseModel

class TimeResponse(BaseModel):
    """Structured output schema for the AI to conform to."""
    time_hh_mm: str

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
            # Automatically picks up GEMINI_API_KEY from environment
            self._client = genai.Client()
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
    
    def __init__(self):
        super().__init__("claude")
        # TODO: Implement API key loading and client setup
    
    async def tell_time(self, image_path: Path) -> str:
        # TODO: Implement Claude API call
        return "Claude provider not yet implemented"
    
    async def parse_response(self, raw_response: str) -> Optional[str]:
        # TODO: Implement response parsing
        return extract_time_from_text(raw_response)
    
    async def handle_error(self, error: Exception, attempt: int) -> bool:
        # TODO: Implement error handling
        return attempt < 3


class OllamaProvider(BaseInferenceProvider):
    """Local Ollama provider for time inference."""
    
    def __init__(self, model: str = "llava:7b"):
        super().__init__("ollama")
        self.model = model
        # TODO: Implement localhost connection and model selection
    
    async def tell_time(self, image_path: Path) -> str:
        # TODO: Implement Ollama API call
        return "Ollama provider not yet implemented"
    
    async def parse_response(self, raw_response: str) -> Optional[str]:
        # TODO: Implement response parsing
        return extract_time_from_text(raw_response)
    
    async def handle_error(self, error: Exception, attempt: int) -> bool:
        # TODO: Implement error handling
        return attempt < 3


def get_provider(provider_name: str) -> BaseInferenceProvider:
    """
    Factory function to get an inference provider by name.
    
    Args:
        provider_name: Name of the provider (openai, gemini, claude, ollama)
        
    Returns:
        Configured provider instance
        
    Raises:
        ValueError: If provider name is unknown
    """
    providers = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "ollama": OllamaProvider,
    }
    
    provider_class = providers.get(provider_name.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(providers.keys())}")
    
    return provider_class()
