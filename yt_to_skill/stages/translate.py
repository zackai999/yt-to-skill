"""Translate stage: language detection and glossary-injected LLM translation.

Detects source language from the transcript; if English, passthrough.
If non-English (or unknown), calls the LLM translation client with the
trading glossary injected to produce English output.

GLOSSARY_ADDITIONS in LLM response are extracted, logged, and stripped from
the translated output before writing to disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import langdetect
from langdetect import LangDetectException
from loguru import logger

from yt_to_skill.config import PipelineConfig
from yt_to_skill.llm.client import load_glossary, translate_text
from yt_to_skill.models.artifacts import TranscriptArtifact
from yt_to_skill.stages.base import StageResult, artifact_guard

# Default glossary path bundled with the package
_DEFAULT_GLOSSARY_PATH = Path(__file__).parent.parent / "glossary" / "trading_zh_en.json"

_GLOSSARY_SECTION_HEADER = "GLOSSARY_ADDITIONS:"


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def detect_language(text: str) -> str:
    """Detect the primary language of *text*.

    Uses langdetect on the first 1000 characters for speed.
    Maps 'zh-cn' / 'zh-tw' etc. to 'zh'.

    Returns:
        ISO 639-1 language code ('en', 'zh', etc.) or 'unknown' on failure.
    """
    sample = text[:1000]
    try:
        detected = langdetect.detect(sample)
    except LangDetectException as exc:
        logger.warning("detect_language | LangDetectException: {} — returning 'unknown'", exc)
        return "unknown"

    # Normalize Chinese variants to 'zh'
    if detected.startswith("zh"):
        return "zh"
    return detected


# ---------------------------------------------------------------------------
# Glossary additions parser
# ---------------------------------------------------------------------------


def extract_glossary_additions(response: str) -> list[tuple[str, str]]:
    """Parse GLOSSARY_ADDITIONS section from LLM translation response.

    Expected format:
        GLOSSARY_ADDITIONS:
        震仓: shakeout
        洗盘: washout

    Args:
        response: Full LLM translation response text.

    Returns:
        List of (chinese_term, english_term) tuples.
    """
    if _GLOSSARY_SECTION_HEADER not in response:
        return []

    additions: list[tuple[str, str]] = []
    in_section = False

    for line in response.splitlines():
        stripped = line.strip()
        if stripped == _GLOSSARY_SECTION_HEADER:
            in_section = True
            continue
        if in_section and stripped and ":" in stripped:
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                zh = parts[0].strip()
                en = parts[1].strip()
                if zh and en:
                    additions.append((zh, en))

    return additions


def _strip_glossary_additions(response: str) -> str:
    """Remove GLOSSARY_ADDITIONS section from translation response.

    Returns clean translation text only.
    """
    if _GLOSSARY_SECTION_HEADER not in response:
        return response

    # Find the header line and truncate from there
    idx = response.find(_GLOSSARY_SECTION_HEADER)
    return response[:idx].rstrip()


# ---------------------------------------------------------------------------
# run_translate
# ---------------------------------------------------------------------------


def run_translate(
    video_id: str,
    work_dir: Path,
    config: PipelineConfig,
    llm_client: Any | None = None,
) -> StageResult:
    """Detect source language and translate transcript to English if needed.

    Artifact guard: if translated.txt already exists, return cached result.

    For English transcripts: concatenate segments and write directly (no LLM).
    For non-English or unknown: call translate_text with glossary injection.
    Extract and log any GLOSSARY_ADDITIONS from the LLM response.
    Strip GLOSSARY_ADDITIONS before writing clean translated.txt.

    Args:
        video_id: YouTube video ID.
        work_dir: Root directory for pipeline artifacts.
        config: Pipeline configuration.
        llm_client: Optional OpenAI-compatible client for translation.

    Returns:
        StageResult pointing to translated.txt.
    """
    video_dir = work_dir / video_id
    translated_path = video_dir / "translated.txt"

    # Artifact guard
    if artifact_guard(translated_path):
        return StageResult(
            stage_name="translate",
            artifact_path=translated_path,
            skipped=True,
        )

    video_dir.mkdir(parents=True, exist_ok=True)

    # Load transcript
    transcript = TranscriptArtifact.from_json(video_dir / "raw_transcript.json")

    # Concatenate segment text (preserve timestamps as markers for readability)
    full_text = "\n".join(
        f"[{seg['start']:.1f}s] {seg['text']}" for seg in transcript.segments
    )
    plain_text = " ".join(seg["text"] for seg in transcript.segments)

    # Detect language
    lang = detect_language(plain_text)

    logger.info(
        "run_translate | video_id={} | detected_language={} | source_language={}",
        video_id,
        lang,
        transcript.source_language,
    )

    if lang == "en":
        # English passthrough — no LLM call needed
        translated_path.write_text(plain_text, encoding="utf-8")
        logger.info(
            "run_translate | video_id={} | English transcript — passthrough (no LLM call)",
            video_id,
        )
        return StageResult(
            stage_name="translate",
            artifact_path=translated_path,
            skipped=False,
        )

    # Non-English or unknown — translate via LLM
    # Resolve glossary path
    glossary_path = _DEFAULT_GLOSSARY_PATH
    glossary = load_glossary(glossary_path)

    raw_translation = translate_text(llm_client, plain_text, glossary, config)

    # Extract and log glossary additions
    additions = extract_glossary_additions(raw_translation)
    for zh_term, en_term in additions:
        logger.info(
            "run_translate | GLOSSARY_ADDITION | zh={} en={} | video_id={}",
            zh_term,
            en_term,
            video_id,
        )

    # Strip GLOSSARY_ADDITIONS section from output
    clean_translation = _strip_glossary_additions(raw_translation)

    translated_path.write_text(clean_translation, encoding="utf-8")

    logger.info(
        "run_translate | video_id={} | translation written to {}",
        video_id,
        translated_path,
    )

    return StageResult(
        stage_name="translate",
        artifact_path=translated_path,
        skipped=False,
    )
