"""Filter stage: two-stage non-strategy content filter.

Stage 1: Metadata pre-filter — fast, free keyword scoring on title/description/tags.
Stage 2: Transcript LLM classification — cheap LLM call on first 500 words.

Both stages must pass for a video to proceed to extraction.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
from openai import OpenAI

from yt_to_skill.config import PipelineConfig
from yt_to_skill.llm.client import classify_content
from yt_to_skill.models.artifacts import FilterResult, TranscriptArtifact, VideoMetadata
from yt_to_skill.stages.base import StageResult, artifact_guard

# ---------------------------------------------------------------------------
# Keyword sets for metadata pre-filter
# ---------------------------------------------------------------------------

STRATEGY_KEYWORDS: frozenset[str] = frozenset({
    # English
    "strategy", "trading", "entry", "exit", "setup", "indicator",
    "rsi", "macd", "support", "resistance", "breakout", "pullback",
    # Chinese (must be lowercase-safe — CJK chars are not affected by .lower())
    "策略", "入场", "出场", "止损", "止盈", "指标", "趋势", "突破", "回调", "均线", "布林",
})

NON_STRATEGY_KEYWORDS: frozenset[str] = frozenset({
    "vlog", "daily life", "news", "reaction", "unboxing", "review",
    "opinion", "podcast", "interview", "q&a", "giveaway",
    # Chinese
    "新闻", "日常", "开箱",
})


# ---------------------------------------------------------------------------
# Stage 1: Metadata pre-filter
# ---------------------------------------------------------------------------


def metadata_prefilter(
    title: str, description: str, tags: list[str]
) -> tuple[bool, str]:
    """Score video metadata for strategy vs. non-strategy indicators.

    Scores: +1 for each STRATEGY_KEYWORD found, -1 for each NON_STRATEGY_KEYWORD.
    If score <= 0: return (False, reason). If score > 0: return (True, reason).

    Args:
        title: Video title.
        description: Video description.
        tags: Video tags.

    Returns:
        (passed, reason) tuple — passed is True when metadata suggests strategy content.
    """
    combined = " ".join([title, description, *tags]).lower()

    score = 0
    for kw in STRATEGY_KEYWORDS:
        if kw in combined:
            score += 1
    for kw in NON_STRATEGY_KEYWORDS:
        if kw in combined:
            score -= 1

    if score > 0:
        return True, "Metadata pre-filter: strategy indicators found"
    return False, "Metadata pre-filter: no strategy indicators found"


# ---------------------------------------------------------------------------
# Stage 2 / orchestrator: run_filter
# ---------------------------------------------------------------------------


def run_filter(
    video_id: str,
    work_dir: Path,
    config: PipelineConfig,
    llm_client: OpenAI | None = None,
) -> StageResult:
    """Run the two-stage non-strategy content filter.

    Artifact guard: if filter_result.json already exists, return cached result.

    Stage 1: metadata_prefilter on title + description + tags.
             If rejected, write FilterResult(is_strategy=False) and return.

    Stage 2 (only if Stage 1 passes): LLM classify_content on first 500 words
             of transcript. If llm_client is None, conservatively assume strategy.

    Args:
        video_id: YouTube video ID.
        work_dir: Root directory for pipeline artifacts.
        config: Pipeline configuration.
        llm_client: Optional OpenAI-compatible client for Stage 2.

    Returns:
        StageResult pointing to filter_result.json.
    """
    video_dir = work_dir / video_id
    filter_path = video_dir / "filter_result.json"

    # Artifact guard
    if artifact_guard(filter_path):
        return StageResult(
            stage_name="filter",
            artifact_path=filter_path,
            skipped=True,
        )

    video_dir.mkdir(parents=True, exist_ok=True)

    # Load metadata
    metadata = VideoMetadata.from_json(video_dir / "metadata.json")

    # Stage 1: metadata pre-filter
    meta_passed, meta_reason = metadata_prefilter(
        title=metadata.title,
        description=metadata.description,
        tags=metadata.tags,
    )

    logger.info(
        "run_filter | video_id={} | stage1_passed={} | reason={}",
        video_id,
        meta_passed,
        meta_reason,
    )

    if not meta_passed:
        filter_result = FilterResult(
            video_id=video_id,
            is_strategy=False,
            confidence=0.0,
            reason=meta_reason,
            metadata_pass=False,
            transcript_pass=None,
        )
        filter_result.to_json(filter_path)
        return StageResult(
            stage_name="filter",
            artifact_path=filter_path,
            skipped=False,
        )

    # Stage 2: transcript LLM classification
    if llm_client is None:
        logger.warning(
            "run_filter | video_id={} | llm_client=None — skipping Stage 2 (conservative: assume strategy)",
            video_id,
        )
        filter_result = FilterResult(
            video_id=video_id,
            is_strategy=True,
            confidence=0.5,
            reason="Stage 2 skipped (no LLM client): conservative pass",
            metadata_pass=True,
            transcript_pass=None,
        )
        filter_result.to_json(filter_path)
        return StageResult(
            stage_name="filter",
            artifact_path=filter_path,
            skipped=False,
        )

    # Load transcript for Stage 2
    transcript = TranscriptArtifact.from_json(video_dir / "raw_transcript.json")
    transcript_text = " ".join(seg["text"] for seg in transcript.segments)

    is_strategy, confidence = classify_content(
        client=llm_client,
        title=metadata.title,
        description=metadata.description,
        transcript_sample=transcript_text,
        config=config,
    )

    reason = (
        "LLM classification: strategy content confirmed"
        if is_strategy
        else "LLM classification: non-strategy content detected"
    )

    filter_result = FilterResult(
        video_id=video_id,
        is_strategy=is_strategy,
        confidence=confidence,
        reason=reason,
        metadata_pass=True,
        transcript_pass=is_strategy,
    )
    filter_result.to_json(filter_path)

    logger.info(
        "run_filter | video_id={} | is_strategy={} | confidence={:.2f}",
        video_id,
        is_strategy,
        confidence,
    )

    return StageResult(
        stage_name="filter",
        artifact_path=filter_path,
        skipped=False,
    )
