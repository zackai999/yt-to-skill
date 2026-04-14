"""Pipeline orchestrator — wires all five stages into a complete pipeline.

Usage:
    from yt_to_skill.orchestrator import run_pipeline, extract_video_id

    results = run_pipeline("dQw4w9WgXcQ", config)
    # -> list[StageResult] with artifact paths to all created files
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from loguru import logger

from yt_to_skill.config import PipelineConfig
from yt_to_skill.llm.client import make_instructor_client, make_openai_client
from yt_to_skill.models.artifacts import FilterResult
from yt_to_skill.stages.base import StageResult
from yt_to_skill.stages.extract import run_extract
from yt_to_skill.stages.filter import run_filter
from yt_to_skill.stages.ingest import run_ingest
from yt_to_skill.stages.skill import run_skill
from yt_to_skill.stages.transcript import run_transcript
from yt_to_skill.stages.translate import run_translate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_video_id(url: str) -> str:
    """Parse YouTube URL and return the video ID.

    Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/shorts/VIDEO_ID

    Args:
        url: YouTube video URL.

    Returns:
        The video ID string.

    Raises:
        ValueError: For unrecognized YouTube URL formats.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    # youtu.be/<video_id>
    if "youtu.be" in host:
        video_id = parsed.path.lstrip("/").split("/")[0]
        if video_id:
            return video_id

    # youtube.com/watch?v=<video_id>
    if "youtube.com" in host:
        # /watch?v=VIDEO_ID
        if parsed.path in ("/watch", "/watch/"):
            params = parse_qs(parsed.query)
            if "v" in params:
                return params["v"][0]

        # /shorts/VIDEO_ID
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "shorts":
            return parts[1]

    raise ValueError(f"Unrecognized YouTube URL: {url!r}")


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------


def run_pipeline(
    video_id: str, config: PipelineConfig, *, force: bool = False
) -> list[StageResult]:
    """Run all pipeline stages in sequence: ingest -> transcript -> filter -> translate -> extract -> skill.

    Creates work/<video_id>/ directory.  Creates LLM clients once and passes to
    all stages that need them.

    Skips translate+extract+skill when filter marks video as non-strategy.
    Wraps each stage in try/except — on error, appends a StageResult with the
    error field set and continues (downstream stages that depend on failed stage
    artifacts may also fail or skip naturally).

    Args:
        video_id: YouTube video ID.
        config: Pipeline configuration.
        force: When True, regenerate existing artifacts.

    Returns:
        List of StageResults (one per stage attempted).
    """
    work_dir = config.work_dir
    video_dir = work_dir / video_id
    video_dir.mkdir(parents=True, exist_ok=True)

    results: list[StageResult] = []

    # Create LLM clients once
    openai_client = make_openai_client(config)
    instructor_client = make_instructor_client(config)

    # -----------------------------------------------------------------------
    # Stage 1: Ingest
    # -----------------------------------------------------------------------
    try:
        ingest_result = run_ingest(video_id, work_dir, config)
        results.append(ingest_result)
        status = "skipped" if ingest_result.skipped else "completed"
        logger.info("Stage: ingest — {}", status)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Stage: ingest — ERROR | video_id={} | error={}",
            video_id,
            exc,
        )
        results.append(
            StageResult(
                stage_name="ingest",
                artifact_path=video_dir / "metadata.json",
                skipped=False,
                error=str(exc),
            )
        )
        return results

    # -----------------------------------------------------------------------
    # Stage 2: Transcript
    # -----------------------------------------------------------------------
    try:
        transcript_result = run_transcript(video_id, work_dir, config)
        results.append(transcript_result)
        status = "skipped" if transcript_result.skipped else "completed"
        logger.info("Stage: transcript — {}", status)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Stage: transcript — ERROR | video_id={} | error={}",
            video_id,
            exc,
        )
        results.append(
            StageResult(
                stage_name="transcript",
                artifact_path=video_dir / "raw_transcript.json",
                skipped=False,
                error=str(exc),
            )
        )
        return results

    # -----------------------------------------------------------------------
    # Stage 3: Filter
    # -----------------------------------------------------------------------
    try:
        filter_result = run_filter(video_id, work_dir, config, llm_client=openai_client)
        results.append(filter_result)
        status = "skipped" if filter_result.skipped else "completed"
        logger.info("Stage: filter — {}", status)

        # Read filter result to determine if we should continue
        filter_data = FilterResult.from_json(filter_result.artifact_path)
        if not filter_data.is_strategy:
            logger.info(
                "Stage: filter — Video {} filtered as non-strategy (confidence={:.2f}), stopping pipeline",
                video_id,
                filter_data.confidence,
            )
            return results

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Stage: filter — ERROR | video_id={} | error={}",
            video_id,
            exc,
        )
        results.append(
            StageResult(
                stage_name="filter",
                artifact_path=video_dir / "filter_result.json",
                skipped=False,
                error=str(exc),
            )
        )
        return results

    # -----------------------------------------------------------------------
    # Stage 4: Translate
    # -----------------------------------------------------------------------
    try:
        translate_result = run_translate(video_id, work_dir, config, llm_client=openai_client)
        results.append(translate_result)
        status = "skipped" if translate_result.skipped else "completed"
        logger.info("Stage: translate — {}", status)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Stage: translate — ERROR | video_id={} | error={}",
            video_id,
            exc,
        )
        results.append(
            StageResult(
                stage_name="translate",
                artifact_path=video_dir / "translated.txt",
                skipped=False,
                error=str(exc),
            )
        )

    # -----------------------------------------------------------------------
    # Stage 5: Extract
    # -----------------------------------------------------------------------
    try:
        extract_result = run_extract(
            video_id, work_dir, config, instructor_client=instructor_client
        )
        results.append(extract_result)
        status = "skipped" if extract_result.skipped else "completed"
        logger.info("Stage: extract — {}", status)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Stage: extract — ERROR | video_id={} | error={}",
            video_id,
            exc,
        )
        results.append(
            StageResult(
                stage_name="extract",
                artifact_path=video_dir / "extracted_logic.json",
                skipped=False,
                error=str(exc),
            )
        )

    # -----------------------------------------------------------------------
    # Stage 6: Skill generation
    # -----------------------------------------------------------------------
    try:
        skill_result = run_skill(video_id, work_dir, config.skills_dir, force=force)
        results.append(skill_result)
        status = "skipped" if skill_result.skipped else "completed"
        logger.info("Stage: skill — {}", status)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Stage: skill — ERROR | video_id={} | error={}",
            video_id,
            exc,
        )
        results.append(
            StageResult(
                stage_name="skill",
                artifact_path=config.skills_dir / video_id / "SKILL.md",
                skipped=False,
                error=str(exc),
            )
        )

    return results
