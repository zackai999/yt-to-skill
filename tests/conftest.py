"""Shared pytest fixtures for yt-to-skill tests."""

import tempfile
from pathlib import Path

import pytest

from yt_to_skill.config import PipelineConfig


@pytest.fixture
def tmp_work_dir():
    """Create a temporary work directory, yield it, clean up after test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_video_id() -> str:
    """Return a consistent test video ID."""
    return "dQw4w9WgXcQ"


@pytest.fixture
def sample_transcript_segments() -> list[dict]:
    """Return a list of 5 sample transcript segments."""
    return [
        {"start": 0.0, "end": 3.5, "text": "当MACD金叉出现时"},
        {"start": 3.5, "end": 7.2, "text": "我们就可以考虑入场做多"},
        {"start": 7.2, "end": 11.0, "text": "止损设在上一个低点下方"},
        {"start": 11.0, "end": 15.3, "text": "目标位看前高附近"},
        {"start": 15.3, "end": 19.8, "text": "风险收益比至少要达到1比2"},
    ]


@pytest.fixture
def mock_config() -> PipelineConfig:
    """Return a PipelineConfig with test values."""
    return PipelineConfig(
        openrouter_api_key="test-api-key-for-testing",
        work_dir=Path("test-work"),
        translation_model="anthropic/claude-sonnet-4-20250514",
        extraction_model="anthropic/claude-sonnet-4-20250514",
        filter_model="mistralai/mistral-7b-instruct",
    )
