"""Typed error hierarchy for yt-to-skill pipeline.

All pipeline errors inherit from SkillError and carry a category prefix
and actionable suggestion string.

Format: "[CATEGORY] message — suggestion"
"""


class SkillError(Exception):
    """Base class for all yt-to-skill pipeline errors.

    Subclasses must define class-level `category` and `suggestion` attributes.
    """

    category: str = "UNKNOWN"
    suggestion: str = "Check logs for details."

    def __init__(self, message: str) -> None:
        formatted = f"[{self.category}] {message} — {self.suggestion}"
        super().__init__(formatted)


class NetworkError(SkillError):
    """Raised when a network-level failure occurs (download, API connectivity)."""

    category = "NETWORK"
    suggestion = "Check internet connection or retry later."


class ExtractionError(SkillError):
    """Raised when caption or transcript extraction fails."""

    category = "EXTRACTION"
    suggestion = "Video may lack captions; delete work/<video_id>/ and rerun."


class LLMError(SkillError):
    """Raised when an LLM API call fails."""

    category = "LLM"
    suggestion = "Check OPENROUTER_API_KEY and model availability on openrouter.ai."


class FormatError(SkillError):
    """Raised when a pipeline artifact has unexpected or malformed content."""

    category = "FORMAT"
    suggestion = "extracted_logic.json may be malformed; delete work/<video_id>/ and rerun."
