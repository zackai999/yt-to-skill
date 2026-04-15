"""Transcript stage: caption extraction with Whisper fallback and quality heuristics."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
)
from youtube_transcript_api._transcripts import TranscriptList

from yt_to_skill.config import PipelineConfig
from yt_to_skill.models.artifacts import TranscriptArtifact, VideoMetadata
from yt_to_skill.stages.base import StageResult, artifact_guard
from yt_to_skill.stages.ingest import download_audio

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# mlx-whisper needs MLX-converted models from mlx-community
MLX_WHISPER_MODEL_ID = "mlx-community/whisper-large-v3-mlx"
# faster-whisper uses CTranslate2 format models
FASTER_WHISPER_MODEL_ID = "Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper"

_IS_APPLE_SILICON = platform.system() == "Darwin" and platform.machine() == "arm64"

_DEFAULT_LANGUAGE_PRIORITY = ["zh", "zh-Hans", "zh-Hant", "en"]

# ---------------------------------------------------------------------------
# Whisper model singleton (faster-whisper only; mlx-whisper is stateless)
# ---------------------------------------------------------------------------

_whisper_model: "WhisperModel | None" = None


def get_whisper_model(device: str = "cpu", compute_type: str = "int8") -> "WhisperModel":
    """Lazy-load the faster-whisper model (singleton). Used on non-Apple-Silicon systems.

    Args:
        device: Inference device ("cpu" or "cuda")
        compute_type: Quantization type ("int8", "float16", etc.)

    Returns:
        Loaded WhisperModel instance
    """
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        logger.info(
            "Loading Whisper model {model_id} on {device}",
            model_id=FASTER_WHISPER_MODEL_ID,
            device=device,
        )
        _whisper_model = WhisperModel(
            FASTER_WHISPER_MODEL_ID,
            device=device,
            compute_type=compute_type,
        )
    return _whisper_model


# ---------------------------------------------------------------------------
# Caption extraction
# ---------------------------------------------------------------------------


def fetch_captions(
    video_id: str,
    language_priority: list[str] | None = None,
) -> tuple[list[dict], str] | None:
    """Fetch YouTube captions for a video.

    Tries priority languages first (zh/zh-Hans/zh-Hant/en), then falls
    back to any available transcript.

    Args:
        video_id: YouTube video ID
        language_priority: Languages to try in order; defaults to
            ["zh", "zh-Hans", "zh-Hant", "en"]

    Returns:
        (segments, language_code) or None if captions are unavailable
    """
    if language_priority is None:
        language_priority = _DEFAULT_LANGUAGE_PRIORITY

    api = YouTubeTranscriptApi()
    try:
        transcript_list: TranscriptList = api.list(video_id)
    except CouldNotRetrieveTranscript as exc:
        logger.warning("Captions unavailable for {video_id}: {exc}", video_id=video_id, exc=exc)
        return None

    # Try priority languages
    transcript = None
    try:
        transcript = transcript_list.find_transcript(language_priority)
    except NoTranscriptFound:
        # Fall back to the first available transcript
        try:
            transcript = next(iter(transcript_list))
        except StopIteration:
            logger.warning("No transcripts at all for {video_id}", video_id=video_id)
            return None

    try:
        fetched = transcript.fetch()
    except CouldNotRetrieveTranscript as exc:
        logger.warning("Failed to fetch transcript for {video_id}: {exc}", video_id=video_id, exc=exc)
        return None

    segments = [
        {
            "start": snippet.start,
            "end": snippet.start + snippet.duration,
            "text": snippet.text,
        }
        for snippet in fetched
    ]

    return segments, transcript.language_code


# ---------------------------------------------------------------------------
# Quality heuristics
# ---------------------------------------------------------------------------


def is_caption_quality_acceptable(
    segments: list[dict],
    video_duration_s: float,
) -> bool:
    """Check if caption quality is sufficient to avoid Whisper fallback.

    Heuristics:
    - total_chars >= duration_s * 2 (density check)
    - music_tag_ratio <= 0.3 (noise check)
    - short_segment_ratio <= 0.6 (fragmentation check)

    Args:
        segments: List of transcript segment dicts with 'text' key
        video_duration_s: Video duration in seconds

    Returns:
        True if captions appear usable, False if Whisper fallback is needed
    """
    if not segments:
        return False

    total_chars = sum(len(seg.get("text", "")) for seg in segments)
    n = len(segments)

    music_count = sum(
        1 for seg in segments if "[Music]" in seg.get("text", "")
    )
    music_tag_ratio = music_count / n

    # Short segment: fewer than 3 space-separated tokens OR fewer than 5 characters
    # The 5-char minimum handles Chinese text where spaces are absent
    short_count = sum(
        1
        for seg in segments
        if len(seg.get("text", "").split()) < 3 and len(seg.get("text", "")) < 5
    )
    short_segment_ratio = short_count / n

    if total_chars < video_duration_s * 2:
        logger.debug(
            "Poor caption quality: total_chars={chars} < duration*2={threshold}",
            chars=total_chars,
            threshold=video_duration_s * 2,
        )
        return False

    if music_tag_ratio > 0.3:
        logger.debug(
            "Poor caption quality: music_tag_ratio={ratio:.2f} > 0.3",
            ratio=music_tag_ratio,
        )
        return False

    if short_segment_ratio > 0.6:
        logger.debug(
            "Poor caption quality: short_segment_ratio={ratio:.2f} > 0.6",
            ratio=short_segment_ratio,
        )
        return False

    return True


# ---------------------------------------------------------------------------
# Whisper transcription
# ---------------------------------------------------------------------------


def _transcribe_mlx(audio_path: Path) -> list[dict]:
    """Transcribe using mlx-whisper on Apple Silicon (Metal GPU)."""
    import mlx_whisper

    logger.info(
        "Transcribing with mlx-whisper ({model}) on Metal GPU",
        model=MLX_WHISPER_MODEL_ID,
    )
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=MLX_WHISPER_MODEL_ID,
        language="zh",
        task="transcribe",
    )

    return [
        {
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
        }
        for seg in result.get("segments", [])
    ]


def _transcribe_faster_whisper(
    audio_path: Path,
    device: str = "cpu",
    compute_type: str = "int8",
) -> list[dict]:
    """Transcribe using faster-whisper on CPU/CUDA."""
    model = get_whisper_model(device=device, compute_type=compute_type)

    segments_iter, _info = model.transcribe(
        str(audio_path),
        language="zh",
        task="transcribe",
        vad_filter=True,
        beam_size=5,
    )

    return [
        {
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
        }
        for seg in segments_iter
    ]


def transcribe_audio(
    audio_path: Path,
    device: str = "cpu",
    compute_type: str = "int8",
) -> list[dict]:
    """Transcribe audio file using the best available backend.

    On Apple Silicon: uses mlx-whisper (Metal GPU acceleration).
    On other systems: uses faster-whisper (CPU/CUDA).

    Args:
        audio_path: Path to the audio file
        device: Inference device for faster-whisper ("cpu" or "cuda")
        compute_type: Quantization type for faster-whisper

    Returns:
        List of {start, end, text} segment dicts
    """
    if _IS_APPLE_SILICON:
        return _transcribe_mlx(audio_path)
    return _transcribe_faster_whisper(audio_path, device=device, compute_type=compute_type)


# ---------------------------------------------------------------------------
# Stage entry point
# ---------------------------------------------------------------------------


def run_transcript(
    video_id: str,
    work_dir: Path,
    config: PipelineConfig,
) -> StageResult:
    """Extract transcript for a video using captions or Whisper fallback.

    Artifact guard: if raw_transcript.json already exists, returns cached
    StageResult with skipped=True.

    Caption quality heuristics determine whether Whisper fallback is needed:
    - If captions are good quality: method="captions"
    - If captions exist but poor quality: method="whisper", caption_quality="poor"
    - If no captions available: method="whisper", caption_quality="missing"

    Args:
        video_id: YouTube video ID
        work_dir: Root directory for pipeline artifacts
        config: Pipeline configuration

    Returns:
        StageResult pointing to raw_transcript.json
    """
    video_dir = work_dir / video_id
    transcript_path = video_dir / "raw_transcript.json"

    if artifact_guard(transcript_path):
        return StageResult(
            stage_name="transcript",
            artifact_path=transcript_path,
            skipped=True,
        )

    # Load metadata for video duration
    metadata_path = video_dir / "metadata.json"
    metadata = VideoMetadata.from_json(metadata_path)
    video_duration_s = metadata.duration_seconds

    # Attempt caption extraction
    caption_result = fetch_captions(video_id)

    method: str
    caption_quality: str
    segments: list[dict]
    source_language: str

    if caption_result is not None:
        raw_segments, lang = caption_result
        if is_caption_quality_acceptable(raw_segments, video_duration_s):
            logger.info(
                "Using captions for {video_id} (language={lang})",
                video_id=video_id,
                lang=lang,
            )
            method = "captions"
            caption_quality = "good"
            segments = raw_segments
            source_language = lang
        else:
            logger.warning(
                "Caption quality poor for {video_id} — falling back to Whisper",
                video_id=video_id,
            )
            caption_quality = "poor"
            audio_path = download_audio(video_id, work_dir, config)
            segments = transcribe_audio(
                audio_path,
                device=config.whisper_device,
                compute_type=config.whisper_compute_type,
            )
            method = "whisper"
            source_language = "zh"
    else:
        logger.info(
            "No captions for {video_id} — using Whisper",
            video_id=video_id,
        )
        caption_quality = "missing"
        audio_path = download_audio(video_id, work_dir, config)
        segments = transcribe_audio(
            audio_path,
            device=config.whisper_device,
            compute_type=config.whisper_compute_type,
        )
        method = "whisper"
        source_language = "zh"

    artifact = TranscriptArtifact(
        video_id=video_id,
        source_language=source_language,
        segments=segments,
        method=method,  # type: ignore[arg-type]
        caption_quality=caption_quality,  # type: ignore[arg-type]
    )
    artifact.to_json(transcript_path)
    logger.info("Transcript written to {path}", path=transcript_path)

    return StageResult(
        stage_name="transcript",
        artifact_path=transcript_path,
        skipped=False,
    )
