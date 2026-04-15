"""Pipeline configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class PipelineConfig(BaseSettings):
    """Configuration for the yt-to-skill pipeline.

    All settings can be overridden via environment variables or .env file.
    """

    openrouter_api_key: str
    work_dir: Path = Path("work")
    skills_dir: Path = Path("skills")
    translation_model: str = "anthropic/claude-sonnet-4.6"
    extraction_model: str = "anthropic/claude-sonnet-4.6"
    filter_model: str = "mistralai/mistral-small-2603"
    hf_token: str | None = None
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    max_tokens_translation: int = 4096
    max_tokens_extraction: int = 4096
    max_keyframes: int = 20
    keyframes_enabled: bool = True

    model_config = {"env_file": ".env"}
