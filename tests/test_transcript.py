"""Tests for the transcript stage: captions + Whisper fallback with quality heuristics."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_to_skill.config import PipelineConfig
from yt_to_skill.models.artifacts import TranscriptArtifact, VideoMetadata
from yt_to_skill.stages.transcript import (
    fetch_captions,
    is_caption_quality_acceptable,
    run_transcript,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

GOOD_SEGMENTS = [
    {"start": 0.0, "end": 4.0, "text": "当MACD金叉出现时"},
    {"start": 4.0, "end": 8.0, "text": "我们就可以考虑入场做多"},
    {"start": 8.0, "end": 12.0, "text": "止损设在上一个低点下方"},
    {"start": 12.0, "end": 16.0, "text": "目标位看前高附近"},
    {"start": 16.0, "end": 20.0, "text": "风险收益比至少要达到一比二"},
]

VIDEO_DURATION_S = 360.0


def _make_config(tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(
        openrouter_api_key="test-key",
        work_dir=tmp_path,
    )


def _write_metadata(video_dir: Path, video_id: str, duration: float = VIDEO_DURATION_S) -> None:
    """Write a minimal metadata.json for testing."""
    metadata = VideoMetadata(
        video_id=video_id,
        title="Test Video",
        description="Trading strategy video",
        duration_seconds=duration,
        channel="Test Channel",
    )
    metadata.to_json(video_dir / "metadata.json")


def _make_snippet(text: str, start: float = 0.0, duration: float = 4.0) -> MagicMock:
    """Create a mock FetchedTranscriptSnippet."""
    snippet = MagicMock()
    snippet.text = text
    snippet.start = start
    snippet.duration = duration
    return snippet


# ---------------------------------------------------------------------------
# fetch_captions tests
# ---------------------------------------------------------------------------


def test_fetch_captions_returns_segments_and_language(tmp_path: Path) -> None:
    """fetch_captions returns (segments, language_code) when captions are available."""
    snippets = [
        _make_snippet("当MACD金叉", 0.0, 4.0),
        _make_snippet("我们可以入场", 4.0, 4.0),
    ]
    mock_transcript = MagicMock()
    mock_transcript.language_code = "zh"
    mock_transcript.fetch.return_value = snippets

    mock_transcript_list = MagicMock()
    mock_transcript_list.find_transcript.return_value = mock_transcript

    with patch(
        "yt_to_skill.stages.transcript.YouTubeTranscriptApi.list_transcripts",
        return_value=mock_transcript_list,
    ):
        result = fetch_captions("test_video_id")

    assert result is not None
    segments, lang = result
    assert lang == "zh"
    assert len(segments) == 2
    assert segments[0]["text"] == "当MACD金叉"
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 4.0  # start + duration


def test_fetch_captions_returns_none_on_transcripts_disabled() -> None:
    """fetch_captions returns None when TranscriptsDisabled is raised."""
    from youtube_transcript_api._errors import TranscriptsDisabled

    with patch(
        "yt_to_skill.stages.transcript.YouTubeTranscriptApi.list_transcripts",
        side_effect=TranscriptsDisabled("test_video_id", ""),
    ):
        result = fetch_captions("test_video_id")

    assert result is None


def test_fetch_captions_returns_none_on_no_transcript_available() -> None:
    """fetch_captions returns None when NoTranscriptAvailable is raised."""
    from youtube_transcript_api._errors import NoTranscriptAvailable

    with patch(
        "yt_to_skill.stages.transcript.YouTubeTranscriptApi.list_transcripts",
        side_effect=NoTranscriptAvailable("test_video_id", "", []),
    ):
        result = fetch_captions("test_video_id")

    assert result is None


def test_fetch_captions_prioritizes_zh_languages() -> None:
    """fetch_captions tries zh/zh-Hans/zh-Hant in priority order."""
    snippets = [_make_snippet("中文内容", 0.0, 3.0)]
    mock_transcript = MagicMock()
    mock_transcript.language_code = "zh"
    mock_transcript.fetch.return_value = snippets

    mock_transcript_list = MagicMock()
    mock_transcript_list.find_transcript.return_value = mock_transcript

    with patch(
        "yt_to_skill.stages.transcript.YouTubeTranscriptApi.list_transcripts",
        return_value=mock_transcript_list,
    ) as mock_list:
        result = fetch_captions("test_video_id")

    assert result is not None
    # Verify it tried to find a Chinese language transcript
    mock_transcript_list.find_transcript.assert_called()
    call_args = mock_transcript_list.find_transcript.call_args_list[0][0][0]
    # First call should include zh language codes
    assert any(lang.startswith("zh") for lang in call_args)


def test_fetch_captions_falls_back_to_any_when_priority_unavailable() -> None:
    """fetch_captions falls back to any available transcript when priority langs unavailable."""
    from youtube_transcript_api._errors import NoTranscriptFound

    snippets = [_make_snippet("English content", 0.0, 3.0)]
    mock_transcript = MagicMock()
    mock_transcript.language_code = "en"
    mock_transcript.fetch.return_value = snippets

    mock_transcript_list = MagicMock()
    # Priority languages fail, but iteration (fallback) succeeds
    mock_transcript_list.find_transcript.side_effect = NoTranscriptFound(
        "test_video_id", [], []
    )
    mock_transcript_list.__iter__ = MagicMock(return_value=iter([mock_transcript]))

    with patch(
        "yt_to_skill.stages.transcript.YouTubeTranscriptApi.list_transcripts",
        return_value=mock_transcript_list,
    ):
        result = fetch_captions("test_video_id")

    assert result is not None
    segments, lang = result
    assert lang == "en"


# ---------------------------------------------------------------------------
# is_caption_quality_acceptable tests
# ---------------------------------------------------------------------------


def test_quality_acceptable_for_good_segments() -> None:
    """is_caption_quality_acceptable returns True for normal quality segments."""
    result = is_caption_quality_acceptable(GOOD_SEGMENTS, VIDEO_DURATION_S)
    assert result is True


def test_quality_rejects_high_music_tag_ratio() -> None:
    """is_caption_quality_acceptable returns False when Music tag ratio > 0.3."""
    music_segments = [
        {"start": i * 4.0, "end": (i + 1) * 4.0, "text": "[Music]"}
        for i in range(4)
    ]
    normal_segments = [
        {"start": 16.0, "end": 20.0, "text": "Trading strategy content here"},
    ]
    segments = music_segments + normal_segments  # 4/5 = 80% music → bad
    result = is_caption_quality_acceptable(segments, VIDEO_DURATION_S)
    assert result is False


def test_quality_rejects_insufficient_character_count() -> None:
    """is_caption_quality_acceptable returns False when total chars < duration * 2."""
    # Very sparse captions for a 360-second video — need at least 720 chars
    sparse_segments = [
        {"start": 0.0, "end": 60.0, "text": "Hi"},  # only 2 chars
    ]
    result = is_caption_quality_acceptable(sparse_segments, VIDEO_DURATION_S)
    assert result is False


def test_quality_rejects_high_short_segment_ratio() -> None:
    """is_caption_quality_acceptable returns False when short segment ratio > 0.6."""
    # Short segments = < 3 words
    short_segments = [
        {"start": i * 4.0, "end": (i + 1) * 4.0, "text": "Hi there"}  # 2 words
        for i in range(7)
    ]
    normal_segments = [
        {"start": 28.0, "end": 32.0, "text": "This is a good quality segment with enough words"},
        {"start": 32.0, "end": 36.0, "text": "Another high quality transcript segment with words"},
        {"start": 36.0, "end": 40.0, "text": "More content that has enough words to count"},
    ]
    segments = short_segments + normal_segments  # 7/10 = 70% short → bad
    result = is_caption_quality_acceptable(segments, VIDEO_DURATION_S)
    assert result is False


# ---------------------------------------------------------------------------
# run_transcript tests
# ---------------------------------------------------------------------------


def test_run_transcript_uses_captions_when_available(tmp_path: Path) -> None:
    """run_transcript uses captions when available and writes raw_transcript.json."""
    config = _make_config(tmp_path)
    video_id = "dQw4w9WgXcQ"
    video_dir = tmp_path / video_id
    video_dir.mkdir(parents=True)
    _write_metadata(video_dir, video_id)

    with patch(
        "yt_to_skill.stages.transcript.fetch_captions",
        return_value=(GOOD_SEGMENTS, "zh"),
    ):
        result = run_transcript(video_id, tmp_path, config)

    transcript_path = video_dir / "raw_transcript.json"
    assert transcript_path.exists()
    artifact = TranscriptArtifact.from_json(transcript_path)
    assert artifact.method == "captions"
    assert artifact.caption_quality == "good"
    assert artifact.segments == GOOD_SEGMENTS
    assert artifact.source_language == "zh"
    assert result.artifact_path == transcript_path
    assert result.skipped is False


def test_run_transcript_falls_back_to_whisper_on_no_captions(tmp_path: Path) -> None:
    """run_transcript falls back to Whisper when captions are unavailable."""
    config = _make_config(tmp_path)
    video_id = "dQw4w9WgXcQ"
    video_dir = tmp_path / video_id
    video_dir.mkdir(parents=True)
    _write_metadata(video_dir, video_id)

    fake_audio = video_dir / "audio.webm"
    fake_audio.touch()

    whisper_segments = [{"start": 0.0, "end": 4.0, "text": "Whisper result"}]

    with (
        patch("yt_to_skill.stages.transcript.fetch_captions", return_value=None),
        patch(
            "yt_to_skill.stages.transcript.download_audio",
            return_value=fake_audio,
        ),
        patch(
            "yt_to_skill.stages.transcript.transcribe_audio",
            return_value=whisper_segments,
        ),
    ):
        result = run_transcript(video_id, tmp_path, config)

    transcript_path = video_dir / "raw_transcript.json"
    artifact = TranscriptArtifact.from_json(transcript_path)
    assert artifact.method == "whisper"
    assert artifact.caption_quality == "missing"
    assert artifact.segments == whisper_segments


def test_run_transcript_falls_back_to_whisper_on_poor_caption_quality(tmp_path: Path) -> None:
    """run_transcript falls back to Whisper when caption quality is poor."""
    config = _make_config(tmp_path)
    video_id = "dQw4w9WgXcQ"
    video_dir = tmp_path / video_id
    video_dir.mkdir(parents=True)
    _write_metadata(video_dir, video_id)

    fake_audio = video_dir / "audio.webm"
    fake_audio.touch()

    # Poor quality captions — all music tags
    poor_segments = [
        {"start": i * 4.0, "end": (i + 1) * 4.0, "text": "[Music]"}
        for i in range(10)
    ]
    whisper_segments = [{"start": 0.0, "end": 4.0, "text": "Whisper result"}]

    with (
        patch("yt_to_skill.stages.transcript.fetch_captions", return_value=(poor_segments, "zh")),
        patch(
            "yt_to_skill.stages.transcript.download_audio",
            return_value=fake_audio,
        ),
        patch(
            "yt_to_skill.stages.transcript.transcribe_audio",
            return_value=whisper_segments,
        ),
    ):
        result = run_transcript(video_id, tmp_path, config)

    artifact = TranscriptArtifact.from_json(video_dir / "raw_transcript.json")
    assert artifact.method == "whisper"
    assert artifact.caption_quality == "poor"


def test_run_transcript_skips_when_transcript_json_exists(tmp_path: Path) -> None:
    """run_transcript skips when raw_transcript.json already exists."""
    config = _make_config(tmp_path)
    video_id = "dQw4w9WgXcQ"
    video_dir = tmp_path / video_id
    video_dir.mkdir(parents=True)

    transcript_path = video_dir / "raw_transcript.json"
    cached_artifact = TranscriptArtifact(
        video_id=video_id,
        source_language="zh",
        segments=GOOD_SEGMENTS,
        method="captions",
        caption_quality="good",
    )
    cached_artifact.to_json(transcript_path)

    with patch("yt_to_skill.stages.transcript.fetch_captions") as mock_fetch:
        result = run_transcript(video_id, tmp_path, config)
        mock_fetch.assert_not_called()

    assert result.skipped is True
    assert result.artifact_path == transcript_path


def test_whisper_transcription_uses_vad_filter(tmp_path: Path) -> None:
    """Whisper transcription uses vad_filter=True to suppress hallucination."""
    config = _make_config(tmp_path)
    video_id = "dQw4w9WgXcQ"
    video_dir = tmp_path / video_id
    video_dir.mkdir(parents=True)
    _write_metadata(video_dir, video_id)

    fake_audio = video_dir / "audio.webm"
    fake_audio.touch()

    # Import here to test the actual transcribe_audio function behavior
    from yt_to_skill.stages.transcript import transcribe_audio

    mock_segment = MagicMock()
    mock_segment.start = 0.0
    mock_segment.end = 4.0
    mock_segment.text = " Whisper result"

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], MagicMock())

    with patch("yt_to_skill.stages.transcript.get_whisper_model", return_value=mock_model):
        result = transcribe_audio(fake_audio)

    # Verify vad_filter=True was passed
    call_kwargs = mock_model.transcribe.call_args[1]
    assert call_kwargs.get("vad_filter") is True


def test_whisper_model_uses_belle_model_id() -> None:
    """Whisper model is loaded with the Belle-whisper model ID."""
    from yt_to_skill.stages.transcript import BELLE_WHISPER_MODEL_ID

    assert "Belle-whisper-large-v3-zh-punct" in BELLE_WHISPER_MODEL_ID


def test_transcribe_audio_returns_segments(tmp_path: Path) -> None:
    """transcribe_audio returns list of {start, end, text} dicts."""
    from yt_to_skill.stages.transcript import transcribe_audio

    fake_audio = tmp_path / "audio.webm"
    fake_audio.touch()

    mock_segment = MagicMock()
    mock_segment.start = 0.0
    mock_segment.end = 5.0
    mock_segment.text = " 这是一段测试内容"

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], MagicMock())

    with patch("yt_to_skill.stages.transcript.get_whisper_model", return_value=mock_model):
        segments = transcribe_audio(fake_audio)

    assert len(segments) == 1
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 5.0
    assert segments[0]["text"] == "这是一段测试内容"  # stripped
