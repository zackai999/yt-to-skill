"""Extraction stage: structured LLM extraction via instructor + Pydantic.

Uses the instructor-patched OpenRouter client to extract TradingLogicExtraction
from translated transcript text.  Temperature=0 ensures deterministic output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from yt_to_skill.config import PipelineConfig
from yt_to_skill.llm.client import extract_trading_logic
from yt_to_skill.models.artifacts import TranscriptArtifact
from yt_to_skill.models.extraction import TradingLogicExtraction
from yt_to_skill.stages.base import StageResult, artifact_guard


def run_extract(
    video_id: str,
    work_dir: Path,
    config: PipelineConfig,
    instructor_client: Any | None = None,
) -> StageResult:
    """Extract structured trading logic from the translated transcript.

    Artifact guard: if extracted_logic.json already exists, return cached result.

    Loads translated.txt for the translated text and raw_transcript.json for
    source_language metadata.  Calls extract_trading_logic which uses instructor
    for structured output into TradingLogicExtraction.

    Serializes result to extracted_logic.json via model_dump_json(indent=2).

    Args:
        video_id: YouTube video ID.
        work_dir: Root directory for pipeline artifacts.
        config: Pipeline configuration.
        instructor_client: Optional instructor-patched OpenAI client.

    Returns:
        StageResult pointing to extracted_logic.json.
    """
    video_dir = work_dir / video_id
    extracted_path = video_dir / "extracted_logic.json"

    # Artifact guard
    if artifact_guard(extracted_path):
        return StageResult(
            stage_name="extract",
            artifact_path=extracted_path,
            skipped=True,
        )

    video_dir.mkdir(parents=True, exist_ok=True)

    # Load translated text
    translated_path = video_dir / "translated.txt"
    translated_text = translated_path.read_text(encoding="utf-8")

    # Load transcript for source_language metadata
    transcript = TranscriptArtifact.from_json(video_dir / "raw_transcript.json")
    source_language = transcript.source_language

    logger.info(
        "run_extract | video_id={} | source_language={} | text_len={}",
        video_id,
        source_language,
        len(translated_text),
    )

    # Call extraction via instructor client
    result: TradingLogicExtraction = extract_trading_logic(
        instructor_client,
        translated_text,
        video_id,
        source_language,
        config,
    )

    # Count unspecified params across all strategies
    total_unspecified = sum(len(s.unspecified_params) for s in result.strategies)

    logger.info(
        "run_extract | video_id={} | strategies_found={} | total_unspecified_params={}",
        video_id,
        len(result.strategies),
        total_unspecified,
    )

    # Serialize to disk
    extracted_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    logger.info(
        "run_extract | video_id={} | extracted_logic.json written to {}",
        video_id,
        extracted_path,
    )

    return StageResult(
        stage_name="extract",
        artifact_path=extracted_path,
        skipped=False,
    )
