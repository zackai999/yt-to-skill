"""Ingest stage: yt-dlp metadata fetch and lazy audio download."""

from pathlib import Path

import yt_dlp
from loguru import logger

from yt_to_skill.config import PipelineConfig
from yt_to_skill.models.artifacts import VideoMetadata
from yt_to_skill.stages.base import StageResult, artifact_guard


def run_ingest(video_id: str, work_dir: Path, config: PipelineConfig) -> StageResult:
    """Fetch YouTube video metadata without downloading video/audio.

    Artifact guard: if work_dir/<video_id>/metadata.json already exists,
    returns cached StageResult with skipped=True.

    Args:
        video_id: YouTube video ID (e.g. "dQw4w9WgXcQ")
        work_dir: Root directory for pipeline artifacts
        config: Pipeline configuration

    Returns:
        StageResult pointing to metadata.json
    """
    video_dir = work_dir / video_id
    metadata_path = video_dir / "metadata.json"

    if artifact_guard(metadata_path):
        return StageResult(
            stage_name="ingest",
            artifact_path=metadata_path,
            skipped=True,
        )

    video_dir.mkdir(parents=True, exist_ok=True)

    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }

    logger.info("Fetching metadata for video {video_id}", video_id=video_id)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)

    metadata = VideoMetadata(
        video_id=video_id,
        title=info_dict.get("title", ""),
        description=info_dict.get("description", "") or "",
        duration_seconds=float(info_dict.get("duration", 0)),
        channel=info_dict.get("channel") or info_dict.get("uploader", ""),
        upload_date=info_dict.get("upload_date"),
        tags=info_dict.get("tags") or [],
    )

    metadata.to_json(metadata_path)
    logger.info("Metadata written to {path}", path=metadata_path)

    return StageResult(
        stage_name="ingest",
        artifact_path=metadata_path,
        skipped=False,
    )


def download_audio(video_id: str, work_dir: Path, config: PipelineConfig) -> Path:
    """Download best-quality audio for a video.

    Artifact guard: if any audio.* file already exists in work_dir/<video_id>/,
    returns the existing path without downloading.

    Args:
        video_id: YouTube video ID
        work_dir: Root directory for pipeline artifacts
        config: Pipeline configuration

    Returns:
        Path to the downloaded audio file

    Raises:
        FileNotFoundError: If download completes but no audio file is found
    """
    video_dir = work_dir / video_id
    video_dir.mkdir(parents=True, exist_ok=True)

    # Artifact guard: check for existing audio file
    existing = list(video_dir.glob("audio.*"))
    if existing:
        logger.info("Audio already exists at {path} — skipping download", path=existing[0])
        return existing[0]

    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(video_dir / "audio.%(ext)s"),
        "fragment_retries": 3,
        "quiet": True,
        "no_warnings": True,
    }

    logger.info("Downloading audio for video {video_id}", video_id=video_id)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Find the downloaded audio file
    audio_files = list(video_dir.glob("audio.*"))
    if not audio_files:
        raise FileNotFoundError(
            f"Audio download for video {video_id!r} produced no output file"
        )

    logger.info("Audio downloaded to {path}", path=audio_files[0])
    return audio_files[0]
