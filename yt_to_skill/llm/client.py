"""OpenRouter LLM client wrapper — single gateway for all model calls.

All LLM calls in the pipeline route through this module.  No file outside
this module should import openai directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import instructor
import openai
from loguru import logger
from openai import APIConnectionError, APITimeoutError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from yt_to_skill.config import PipelineConfig
from yt_to_skill.models.extraction import TradingLogicExtraction

# Path to prompt templates bundled with the package
_PROMPTS_DIR = Path(__file__).parent / "prompts"


# ---------------------------------------------------------------------------
# Retry decorator shared by all API calls
# ---------------------------------------------------------------------------

_retry = retry(
    wait=wait_exponential(min=2, max=60),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((APITimeoutError, APIConnectionError, RateLimitError)),
    reraise=True,
)


# ---------------------------------------------------------------------------
# Client factories
# ---------------------------------------------------------------------------


def make_openai_client(config: PipelineConfig) -> openai.OpenAI:
    """Create an OpenAI-compatible client pointed at OpenRouter."""
    return openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=config.openrouter_api_key,
    )


def make_instructor_client(config: PipelineConfig) -> Any:
    """Create an instructor-patched OpenRouter client for structured outputs."""
    raw_client = make_openai_client(config)
    return instructor.from_openai(raw_client)


# ---------------------------------------------------------------------------
# Glossary helper
# ---------------------------------------------------------------------------


def load_glossary(glossary_path: Path) -> dict:
    """Load a Chinese-English trading glossary JSON file."""
    return json.loads(glossary_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# LLM functions
# ---------------------------------------------------------------------------


@_retry
def translate_text(
    client: openai.OpenAI,
    text: str,
    glossary: dict,
    config: PipelineConfig,
) -> str:
    """Translate *text* to English using the trading glossary for term consistency.

    Loads translate.txt prompt, injects glossary terms, and calls
    chat.completions.create with config.translation_model and
    config.max_tokens_translation.
    """
    prompt_template = (_PROMPTS_DIR / "translate.txt").read_text(encoding="utf-8")

    # Format glossary as a readable list for injection
    glossary_lines = "\n".join(f"  {zh}: {en}" for zh, en in glossary.items())
    system_prompt = prompt_template.replace("{glossary}", glossary_lines)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]

    response = client.chat.completions.create(
        model=config.translation_model,
        messages=messages,
        max_tokens=config.max_tokens_translation,
    )

    usage = response.usage
    logger.info(
        "translate_text | model={} | stage=translation | prompt_tokens={} | completion_tokens={}",
        config.translation_model,
        usage.prompt_tokens if usage else "?",
        usage.completion_tokens if usage else "?",
    )

    return response.choices[0].message.content or ""


@_retry
def classify_content(
    client: openai.OpenAI,
    title: str,
    description: str,
    transcript_sample: str,
    config: PipelineConfig,
) -> tuple[bool, float]:
    """Classify whether a video presents an actionable trading strategy.

    Returns (is_strategy: bool, confidence: float).
    Uses the first 500 words of the transcript sample plus title/description.
    """
    prompt_template = (_PROMPTS_DIR / "filter_content.txt").read_text(encoding="utf-8")

    # Trim transcript to first 500 words
    words = transcript_sample.split()
    excerpt = " ".join(words[:500])

    user_content = (
        f"Title: {title}\n"
        f"Description: {description}\n"
        f"Transcript excerpt:\n{excerpt}"
    )

    messages = [
        {"role": "system", "content": prompt_template},
        {"role": "user", "content": user_content},
    ]

    response = client.chat.completions.create(
        model=config.filter_model,
        messages=messages,
        max_tokens=256,
    )

    usage = response.usage
    logger.info(
        "classify_content | model={} | stage=filter | prompt_tokens={} | completion_tokens={}",
        config.filter_model,
        usage.prompt_tokens if usage else "?",
        usage.completion_tokens if usage else "?",
    )

    raw = (response.choices[0].message.content or "").strip()
    return _parse_classification(raw)


def _parse_classification(raw: str) -> tuple[bool, float]:
    """Parse the LLM filter response into (is_strategy, confidence)."""
    lines = [line.strip() for line in raw.splitlines() if line.strip()]

    is_strategy = False
    confidence = 0.5

    if lines:
        is_strategy = lines[0].upper().startswith("STRATEGY") and not lines[0].upper().startswith(
            "NOT_STRATEGY"
        )

    if len(lines) >= 2:
        try:
            confidence = float(lines[1])
            confidence = max(0.0, min(1.0, confidence))
        except ValueError:
            pass

    return is_strategy, confidence


@_retry
def extract_trading_logic(
    instructor_client: Any,
    translated_text: str,
    video_id: str,
    source_language: str,
    config: PipelineConfig,
) -> TradingLogicExtraction:
    """Extract structured trading logic from the translated transcript.

    Uses instructor for structured output with response_model=TradingLogicExtraction,
    temperature=0 for deterministic extraction.
    """
    system_prompt = (_PROMPTS_DIR / "extract_trading.txt").read_text(encoding="utf-8")

    user_content = (
        f"video_id: {video_id}\n"
        f"source_language: {source_language}\n\n"
        f"Transcript:\n{translated_text}"
    )

    result: TradingLogicExtraction = instructor_client.chat.completions.create(
        model=config.extraction_model,
        response_model=TradingLogicExtraction,
        temperature=0,
        max_tokens=config.max_tokens_extraction,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )

    logger.info(
        "extract_trading_logic | model={} | stage=extraction | video_id={} | strategies_found={}",
        config.extraction_model,
        video_id,
        len(result.strategies) if hasattr(result, "strategies") else "?",
    )

    return result
