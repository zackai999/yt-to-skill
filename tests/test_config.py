"""Tests for PipelineConfig — Task 1 TDD."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from yt_to_skill.config import PipelineConfig


def test_pipeline_config_loads_api_key_from_env(monkeypatch):
    """PipelineConfig loads OPENROUTER_API_KEY from environment variables."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-12345")
    config = PipelineConfig()
    assert config.openrouter_api_key == "sk-or-test-12345"


def test_pipeline_config_default_work_dir(monkeypatch):
    """PipelineConfig has default value for work_dir."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-12345")
    config = PipelineConfig()
    assert config.work_dir == Path("work")


def test_pipeline_config_default_translation_model(monkeypatch):
    """PipelineConfig has default value for translation_model."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-12345")
    config = PipelineConfig()
    assert config.translation_model == "anthropic/claude-sonnet-4-20250514"


def test_pipeline_config_default_extraction_model(monkeypatch):
    """PipelineConfig has default value for extraction_model."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-12345")
    config = PipelineConfig()
    assert config.extraction_model == "anthropic/claude-sonnet-4-20250514"


def test_pipeline_config_work_dir_is_path(monkeypatch):
    """PipelineConfig.work_dir returns a Path object."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-12345")
    config = PipelineConfig()
    assert isinstance(config.work_dir, Path)


def test_pipeline_config_missing_api_key_raises_validation_error():
    """Missing OPENROUTER_API_KEY raises ValidationError."""
    # Ensure no env var is set
    env_key = "OPENROUTER_API_KEY"
    original = os.environ.pop(env_key, None)
    try:
        with pytest.raises(ValidationError):
            PipelineConfig()
    finally:
        if original is not None:
            os.environ[env_key] = original


def test_pipeline_config_work_dir_overridable(monkeypatch):
    """PipelineConfig.work_dir can be overridden."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-12345")
    config = PipelineConfig(work_dir=Path("/tmp/custom-work"))
    assert config.work_dir == Path("/tmp/custom-work")
