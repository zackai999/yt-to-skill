"""Tests for the ingest stage: yt-dlp metadata fetch and lazy audio download."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_to_skill.config import PipelineConfig
from yt_to_skill.stages.ingest import download_audio, run_ingest


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

FAKE_INFO_DICT = {
    "id": "dQw4w9WgXcQ",
    "title": "Test Video Title",
    "description": "A test description about trading strategy.",
    "duration": 360.0,
    "channel": "Test Channel",
    "uploader": "Test Uploader",
    "upload_date": "20240101",
    "tags": ["trading", "strategy", "BTC"],
}


def _make_config(tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(
        openrouter_api_key="test-key",
        work_dir=tmp_path,
    )


# ---------------------------------------------------------------------------
# run_ingest tests
# ---------------------------------------------------------------------------


def test_run_ingest_creates_video_directory(tmp_path: Path) -> None:
    """run_ingest should create work_dir/<video_id>/ directory."""
    config = _make_config(tmp_path)
    video_id = "dQw4w9WgXcQ"

    with patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = FAKE_INFO_DICT
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

        run_ingest(video_id, tmp_path, config)

    assert (tmp_path / video_id).is_dir()


def test_run_ingest_writes_metadata_json(tmp_path: Path) -> None:
    """run_ingest should write metadata.json with all VideoMetadata fields."""
    config = _make_config(tmp_path)
    video_id = "dQw4w9WgXcQ"

    with patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = FAKE_INFO_DICT
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = run_ingest(video_id, tmp_path, config)

    metadata_path = tmp_path / video_id / "metadata.json"
    assert metadata_path.exists()
    data = json.loads(metadata_path.read_text())
    assert data["title"] == "Test Video Title"
    assert data["description"] == "A test description about trading strategy."
    assert data["duration_seconds"] == 360.0
    assert data["channel"] == "Test Channel"
    assert data["tags"] == ["trading", "strategy", "BTC"]
    assert data["upload_date"] == "20240101"
    assert data["video_id"] == video_id
    assert result.artifact_path == metadata_path


def test_run_ingest_skips_when_metadata_json_exists(tmp_path: Path) -> None:
    """run_ingest should skip and return skipped=True when metadata.json already exists."""
    config = _make_config(tmp_path)
    video_id = "dQw4w9WgXcQ"

    # Pre-create metadata.json
    video_dir = tmp_path / video_id
    video_dir.mkdir(parents=True)
    metadata_path = video_dir / "metadata.json"
    metadata_path.write_text(json.dumps({"video_id": video_id, "title": "cached"}))

    with patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL") as mock_ydl_cls:
        result = run_ingest(video_id, tmp_path, config)
        mock_ydl_cls.assert_not_called()

    assert result.skipped is True
    assert result.artifact_path == metadata_path


def test_run_ingest_does_not_download_video(tmp_path: Path) -> None:
    """run_ingest should use skip_download=True — no video/audio downloaded."""
    config = _make_config(tmp_path)
    video_id = "dQw4w9WgXcQ"
    captured_opts: list[dict] = []

    original_ydl = __import__("yt_dlp").YoutubeDL

    def capturing_ydl(opts: dict):
        captured_opts.append(opts)
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = FAKE_INFO_DICT
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        return mock_ydl

    with patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL", side_effect=capturing_ydl):
        run_ingest(video_id, tmp_path, config)

    assert len(captured_opts) >= 1
    assert captured_opts[0].get("skip_download") is True


# ---------------------------------------------------------------------------
# download_audio tests
# ---------------------------------------------------------------------------


def test_download_audio_uses_bestaudio_format(tmp_path: Path) -> None:
    """download_audio should use 'bestaudio/best' format option."""
    config = _make_config(tmp_path)
    video_id = "dQw4w9WgXcQ"
    video_dir = tmp_path / video_id
    video_dir.mkdir(parents=True)
    captured_opts: list[dict] = []

    def capturing_ydl(opts: dict):
        captured_opts.append(opts)
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        # Simulate file creation
        (video_dir / "audio.webm").touch()
        return mock_ydl

    with patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL", side_effect=capturing_ydl):
        download_audio(video_id, tmp_path, config)

    assert len(captured_opts) >= 1
    assert captured_opts[0].get("format") == "bestaudio/best"


def test_download_audio_sets_fragment_retries_to_3(tmp_path: Path) -> None:
    """download_audio should set fragment_retries=3."""
    config = _make_config(tmp_path)
    video_id = "dQw4w9WgXcQ"
    video_dir = tmp_path / video_id
    video_dir.mkdir(parents=True)
    captured_opts: list[dict] = []

    def capturing_ydl(opts: dict):
        captured_opts.append(opts)
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        (video_dir / "audio.webm").touch()
        return mock_ydl

    with patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL", side_effect=capturing_ydl):
        download_audio(video_id, tmp_path, config)

    assert len(captured_opts) >= 1
    assert captured_opts[0].get("fragment_retries") == 3


def test_download_audio_skips_when_audio_file_exists(tmp_path: Path) -> None:
    """download_audio should skip download when audio.* already exists."""
    config = _make_config(tmp_path)
    video_id = "dQw4w9WgXcQ"
    video_dir = tmp_path / video_id
    video_dir.mkdir(parents=True)
    existing_audio = video_dir / "audio.webm"
    existing_audio.touch()

    with patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL") as mock_ydl_cls:
        result_path = download_audio(video_id, tmp_path, config)
        mock_ydl_cls.assert_not_called()

    assert result_path == existing_audio
