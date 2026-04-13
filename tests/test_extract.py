"""Tests for yt_to_skill/stages/extract.py — TDD RED phase."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_to_skill.config import PipelineConfig
from yt_to_skill.models.artifacts import TranscriptArtifact
from yt_to_skill.models.extraction import EntryCondition, StrategyObject, TradingLogicExtraction
from yt_to_skill.stages.extract import run_extract


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def config(tmp_path: Path) -> PipelineConfig:
    """Pipeline config with work_dir pointing to tmp_path."""
    return PipelineConfig(
        openrouter_api_key="test-key",
        work_dir=tmp_path,
        extraction_model="anthropic/claude-sonnet-4",
        max_tokens_extraction=4096,
    )


@pytest.fixture()
def video_id() -> str:
    return "testVideoId1"


@pytest.fixture()
def video_dir(config: PipelineConfig, video_id: str) -> Path:
    d = config.work_dir / video_id
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture()
def transcript_artifact(video_id: str, video_dir: Path) -> TranscriptArtifact:
    """Write a raw_transcript.json with source_language=zh and return it."""
    artifact = TranscriptArtifact(
        video_id=video_id,
        source_language="zh",
        segments=[
            {"start": 0.0, "end": 2.0, "text": "这是测试文本"},
            {"start": 2.0, "end": 4.0, "text": "关于交易策略"},
        ],
        method="captions",
        caption_quality="good",
    )
    artifact.to_json(video_dir / "raw_transcript.json")
    return artifact


@pytest.fixture()
def translated_txt(video_dir: Path) -> Path:
    """Write a translated.txt and return its path."""
    p = video_dir / "translated.txt"
    p.write_text(
        "This is test content about a trading strategy with entry and exit rules.",
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def sample_extraction(video_id: str) -> TradingLogicExtraction:
    """A pre-built TradingLogicExtraction to return from the mock."""
    return TradingLogicExtraction(
        video_id=video_id,
        source_language="zh",
        strategies=[
            StrategyObject(
                strategy_name="Moving Average Crossover",
                market_conditions=["trending market"],
                entry_criteria=[
                    EntryCondition(
                        indicator="MA",
                        condition="crossover",
                        value="20/50",
                        timeframe="1h",
                        confirmation=None,  # will populate unspecified_params
                        raw_text="When the 20 MA crosses above the 50 MA",
                    )
                ],
                exit_criteria=[
                    EntryCondition(
                        indicator="MA",
                        condition="crossunder",
                        value=None,  # will populate unspecified_params
                        timeframe=None,
                        confirmation=None,
                        raw_text="When the 20 MA crosses below the 50 MA",
                    )
                ],
                indicators=["MA20", "MA50"],
                risk_rules=["Stop loss at 2%"],
                unspecified_params=[],  # will be overwritten by model_validator
            )
        ],
        is_strategy_content=True,
    )


# ---------------------------------------------------------------------------
# Test: extract_trading_logic is called with correct params
# ---------------------------------------------------------------------------


def test_run_extract_calls_extract_trading_logic_with_correct_params(
    config: PipelineConfig,
    video_id: str,
    video_dir: Path,
    transcript_artifact: TranscriptArtifact,
    translated_txt: Path,
    sample_extraction: TradingLogicExtraction,
) -> None:
    """run_extract calls extract_trading_logic with translated text + video metadata."""
    mock_instructor_client = MagicMock()

    with patch(
        "yt_to_skill.stages.extract.extract_trading_logic",
        return_value=sample_extraction,
    ) as mock_extract:
        run_extract(video_id, config.work_dir, config, instructor_client=mock_instructor_client)

    mock_extract.assert_called_once()
    call_kwargs = mock_extract.call_args

    # First positional arg is the instructor_client
    assert call_kwargs.args[0] is mock_instructor_client
    # Second positional arg is the translated text
    assert "trading strategy" in call_kwargs.args[1]
    # video_id passed
    assert call_kwargs.args[2] == video_id
    # source_language from transcript
    assert call_kwargs.args[3] == "zh"
    # config passed
    assert call_kwargs.args[4] is config


# ---------------------------------------------------------------------------
# Test: run_extract writes extracted_logic.json
# ---------------------------------------------------------------------------


def test_run_extract_writes_extracted_logic_json(
    config: PipelineConfig,
    video_id: str,
    video_dir: Path,
    transcript_artifact: TranscriptArtifact,
    translated_txt: Path,
    sample_extraction: TradingLogicExtraction,
) -> None:
    """run_extract writes extracted_logic.json containing TradingLogicExtraction data."""
    mock_instructor_client = MagicMock()

    with patch(
        "yt_to_skill.stages.extract.extract_trading_logic",
        return_value=sample_extraction,
    ):
        result = run_extract(video_id, config.work_dir, config, instructor_client=mock_instructor_client)

    assert result.artifact_path.exists()
    assert result.artifact_path.name == "extracted_logic.json"
    assert result.skipped is False


# ---------------------------------------------------------------------------
# Test: artifact guard skips when extracted_logic.json exists
# ---------------------------------------------------------------------------


def test_run_extract_skips_when_artifact_exists(
    config: PipelineConfig,
    video_id: str,
    video_dir: Path,
) -> None:
    """run_extract skips when extracted_logic.json already exists (idempotency)."""
    # Pre-write artifact
    artifact_path = video_dir / "extracted_logic.json"
    artifact_path.write_text("{}", encoding="utf-8")

    mock_instructor_client = MagicMock()

    with patch(
        "yt_to_skill.stages.extract.extract_trading_logic",
    ) as mock_extract:
        result = run_extract(video_id, config.work_dir, config, instructor_client=mock_instructor_client)

    mock_extract.assert_not_called()
    assert result.skipped is True
    assert result.artifact_path == artifact_path


# ---------------------------------------------------------------------------
# Test: unspecified_params populated for null fields
# ---------------------------------------------------------------------------


def test_run_extract_unspecified_params_for_null_fields(
    config: PipelineConfig,
    video_id: str,
    video_dir: Path,
    transcript_artifact: TranscriptArtifact,
    translated_txt: Path,
    sample_extraction: TradingLogicExtraction,
) -> None:
    """Extraction result includes unspecified_params paths for null fields."""
    mock_instructor_client = MagicMock()

    with patch(
        "yt_to_skill.stages.extract.extract_trading_logic",
        return_value=sample_extraction,
    ):
        result = run_extract(video_id, config.work_dir, config, instructor_client=mock_instructor_client)

    extracted = TradingLogicExtraction.model_validate_json(result.artifact_path.read_text())
    strategy = extracted.strategies[0]

    # entry_criteria[0].confirmation is None
    assert "entry_criteria[0].confirmation" in strategy.unspecified_params
    # exit_criteria[0].value is None
    assert "exit_criteria[0].value" in strategy.unspecified_params
    # exit_criteria[0].timeframe is None
    assert "exit_criteria[0].timeframe" in strategy.unspecified_params
    # exit_criteria[0].confirmation is None
    assert "exit_criteria[0].confirmation" in strategy.unspecified_params


# ---------------------------------------------------------------------------
# Test: raw_text preserved in each EntryCondition
# ---------------------------------------------------------------------------


def test_run_extract_raw_text_preserved_in_entry_conditions(
    config: PipelineConfig,
    video_id: str,
    video_dir: Path,
    transcript_artifact: TranscriptArtifact,
    translated_txt: Path,
    sample_extraction: TradingLogicExtraction,
) -> None:
    """Extraction result preserves raw_text in every EntryCondition."""
    mock_instructor_client = MagicMock()

    with patch(
        "yt_to_skill.stages.extract.extract_trading_logic",
        return_value=sample_extraction,
    ):
        result = run_extract(video_id, config.work_dir, config, instructor_client=mock_instructor_client)

    extracted = TradingLogicExtraction.model_validate_json(result.artifact_path.read_text())
    for strategy in extracted.strategies:
        for condition in strategy.entry_criteria + strategy.exit_criteria:
            assert condition.raw_text, "raw_text must be non-empty in every EntryCondition"


# ---------------------------------------------------------------------------
# Test: source_language from TranscriptArtifact passed to extraction
# ---------------------------------------------------------------------------


def test_run_extract_passes_source_language_from_transcript(
    config: PipelineConfig,
    video_id: str,
    video_dir: Path,
    translated_txt: Path,
    sample_extraction: TradingLogicExtraction,
) -> None:
    """run_extract passes source_language from TranscriptArtifact to extraction."""
    # Write transcript with source_language="ja" (Japanese)
    transcript = TranscriptArtifact(
        video_id=video_id,
        source_language="ja",
        segments=[{"start": 0.0, "end": 2.0, "text": "テスト"}],
        method="whisper",
        caption_quality="good",
    )
    transcript.to_json(video_dir / "raw_transcript.json")

    mock_instructor_client = MagicMock()

    with patch(
        "yt_to_skill.stages.extract.extract_trading_logic",
        return_value=sample_extraction,
    ) as mock_extract:
        run_extract(video_id, config.work_dir, config, instructor_client=mock_instructor_client)

    call_args = mock_extract.call_args
    # source_language should be "ja" from the transcript
    assert call_args.args[3] == "ja"


# ---------------------------------------------------------------------------
# Test: extracted_logic.json round-trips to TradingLogicExtraction
# ---------------------------------------------------------------------------


def test_run_extract_json_round_trips(
    config: PipelineConfig,
    video_id: str,
    video_dir: Path,
    transcript_artifact: TranscriptArtifact,
    translated_txt: Path,
    sample_extraction: TradingLogicExtraction,
) -> None:
    """extracted_logic.json is valid JSON parseable back into TradingLogicExtraction."""
    mock_instructor_client = MagicMock()

    with patch(
        "yt_to_skill.stages.extract.extract_trading_logic",
        return_value=sample_extraction,
    ):
        result = run_extract(video_id, config.work_dir, config, instructor_client=mock_instructor_client)

    # Round-trip: file -> JSON -> model
    raw_json = result.artifact_path.read_text()
    parsed = json.loads(raw_json)
    assert parsed["video_id"] == video_id

    reconstructed = TradingLogicExtraction.model_validate_json(raw_json)
    assert reconstructed.video_id == video_id
    assert len(reconstructed.strategies) == len(sample_extraction.strategies)
