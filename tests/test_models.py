"""Tests for data models — artifacts and extraction schema."""

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from yt_to_skill.models.artifacts import (
    FilterResult,
    TranscriptArtifact,
    VideoMetadata,
)
from yt_to_skill.models.extraction import (
    EntryCondition,
    StrategyObject,
    TradingLogicExtraction,
)
from yt_to_skill.stages.base import StageResult, artifact_guard


# ============================================================================
# VideoMetadata tests
# ============================================================================


def test_video_metadata_can_be_created():
    """VideoMetadata can be created with required fields."""
    meta = VideoMetadata(
        video_id="abc123",
        title="BTC Trading Strategy",
        description="Learn my MACD strategy",
        duration_seconds=600.0,
        channel="Trader Feng Ge",
    )
    assert meta.video_id == "abc123"
    assert meta.title == "BTC Trading Strategy"
    assert meta.duration_seconds == 600.0
    assert meta.channel == "Trader Feng Ge"


def test_video_metadata_optional_fields():
    """VideoMetadata upload_date is optional, tags has default."""
    meta = VideoMetadata(
        video_id="abc123",
        title="Test",
        description="Desc",
        duration_seconds=100.0,
        channel="Channel",
    )
    assert meta.upload_date is None
    assert meta.tags == []


def test_video_metadata_to_json_and_from_json(tmp_path):
    """VideoMetadata serializes to JSON and deserializes back."""
    meta = VideoMetadata(
        video_id="abc123",
        title="BTC Strategy",
        description="Test desc",
        duration_seconds=300.0,
        channel="Test Channel",
        upload_date="2024-01-15",
        tags=["bitcoin", "macd"],
    )
    path = tmp_path / "metadata.json"
    meta.to_json(path)
    assert path.exists()
    loaded = VideoMetadata.from_json(path)
    assert loaded.video_id == "abc123"
    assert loaded.tags == ["bitcoin", "macd"]
    assert loaded.upload_date == "2024-01-15"


# ============================================================================
# TranscriptArtifact tests
# ============================================================================


def test_transcript_artifact_validates_method_literal():
    """TranscriptArtifact validates method is Literal['captions', 'whisper']."""
    ta = TranscriptArtifact(
        video_id="abc123",
        source_language="zh",
        segments=[{"start": 0.0, "end": 3.0, "text": "hello"}],
        method="captions",
        caption_quality="good",
    )
    assert ta.method == "captions"

    ta2 = TranscriptArtifact(
        video_id="abc123",
        source_language="zh",
        segments=[],
        method="whisper",
        caption_quality="missing",
    )
    assert ta2.method == "whisper"


def test_transcript_artifact_rejects_invalid_method():
    """TranscriptArtifact rejects invalid method value."""
    with pytest.raises((ValueError, TypeError)):
        TranscriptArtifact(
            video_id="abc123",
            source_language="zh",
            segments=[],
            method="invalid_method",  # type: ignore
            caption_quality="good",
        )


def test_transcript_artifact_to_json_from_json(tmp_path):
    """TranscriptArtifact serializes to and from JSON."""
    ta = TranscriptArtifact(
        video_id="abc123",
        source_language="zh",
        segments=[{"start": 0.0, "end": 3.0, "text": "hello"}],
        method="captions",
        caption_quality="good",
    )
    path = tmp_path / "transcript.json"
    ta.to_json(path)
    loaded = TranscriptArtifact.from_json(path)
    assert loaded.video_id == "abc123"
    assert loaded.method == "captions"
    assert len(loaded.segments) == 1


# ============================================================================
# FilterResult tests
# ============================================================================


def test_filter_result_has_required_fields():
    """FilterResult has is_strategy bool and reason string."""
    fr = FilterResult(
        video_id="abc123",
        is_strategy=True,
        confidence=0.9,
        reason="Video clearly presents a trading strategy",
        metadata_pass=True,
    )
    assert fr.is_strategy is True
    assert isinstance(fr.reason, str)
    assert fr.confidence == 0.9


def test_filter_result_non_strategy():
    """FilterResult captures non-strategy videos."""
    fr = FilterResult(
        video_id="abc123",
        is_strategy=False,
        confidence=0.95,
        reason="Video is a vlog, no trading content",
        metadata_pass=False,
    )
    assert fr.is_strategy is False
    assert fr.metadata_pass is False
    assert fr.transcript_pass is None


# ============================================================================
# EntryCondition tests
# ============================================================================


def test_entry_condition_with_null_value():
    """EntryCondition with null value field produces REQUIRES_SPECIFICATION semantics."""
    ec = EntryCondition(
        indicator="RSI",
        condition="below",
        value=None,  # REQUIRES_SPECIFICATION
        raw_text="RSI below some threshold",
    )
    assert ec.value is None
    assert ec.indicator == "RSI"


def test_entry_condition_with_full_fields():
    """EntryCondition with all fields set."""
    ec = EntryCondition(
        indicator="MACD",
        condition="golden_cross",
        value="0",
        timeframe="4h",
        confirmation="volume spike",
        raw_text="MACD golden cross on 4h with volume spike",
    )
    assert ec.value == "0"
    assert ec.timeframe == "4h"
    assert ec.confirmation == "volume spike"


# ============================================================================
# StrategyObject tests
# ============================================================================


def test_strategy_object_unspecified_params_from_null_fields():
    """StrategyObject.unspecified_params lists paths to null fields."""
    strategy = StrategyObject(
        strategy_name="MACD Golden Cross",
        market_conditions=["bull market", "uptrend"],
        entry_criteria=[
            EntryCondition(
                indicator="MACD",
                condition="golden_cross",
                value=None,  # should appear in unspecified_params
                raw_text="MACD golden cross",
            ),
            EntryCondition(
                indicator="RSI",
                condition="below",
                value="30",  # specified
                raw_text="RSI below 30",
            ),
        ],
        exit_criteria=[
            EntryCondition(
                indicator="Price",
                condition="reaches",
                value=None,  # should appear in unspecified_params
                timeframe=None,  # should appear in unspecified_params
                raw_text="Price reaches target",
            )
        ],
        indicators=["MACD", "RSI"],
        risk_rules=["Stop loss below last low"],
        unspecified_params=[],  # will be auto-populated by validator
    )
    assert "entry_criteria[0].value" in strategy.unspecified_params
    assert "entry_criteria[1].value" not in strategy.unspecified_params  # value=30 is specified
    assert "exit_criteria[0].value" in strategy.unspecified_params
    assert "exit_criteria[0].timeframe" in strategy.unspecified_params


# ============================================================================
# TradingLogicExtraction tests
# ============================================================================


def test_trading_logic_extraction_validates_well_formed_json():
    """TradingLogicExtraction validates a well-formed trading logic object."""
    extraction = TradingLogicExtraction(
        video_id="abc123",
        source_language="zh",
        is_strategy_content=True,
        strategies=[
            StrategyObject(
                strategy_name="BTC MACD Strategy",
                market_conditions=["bull market"],
                entry_criteria=[
                    EntryCondition(
                        indicator="MACD",
                        condition="golden_cross",
                        value="0",
                        raw_text="MACD golden cross at zero line",
                    )
                ],
                exit_criteria=[],
                indicators=["MACD"],
                risk_rules=["1% max risk per trade"],
                unspecified_params=[],
            )
        ],
    )
    assert extraction.video_id == "abc123"
    assert len(extraction.strategies) == 1


def test_trading_logic_extraction_rejects_missing_video_id():
    """TradingLogicExtraction rejects missing video_id."""
    with pytest.raises(ValidationError):
        TradingLogicExtraction(
            source_language="zh",
            strategies=[],
            # video_id is missing
        )


def test_trading_logic_extraction_rejects_missing_strategies():
    """TradingLogicExtraction rejects missing strategies field."""
    with pytest.raises(ValidationError):
        TradingLogicExtraction(
            video_id="abc123",
            source_language="zh",
            # strategies is missing
        )


def test_trading_logic_extraction_null_indicators_populates_unspecified():
    """TradingLogicExtraction with null indicator values populates unspecified_params."""
    extraction = TradingLogicExtraction(
        video_id="abc123",
        source_language="zh",
        strategies=[
            StrategyObject(
                strategy_name="Mystery Strategy",
                market_conditions=[],
                entry_criteria=[
                    EntryCondition(
                        indicator="Unknown Indicator",
                        condition="above",
                        value=None,  # REQUIRES_SPECIFICATION
                        raw_text="Unknown indicator above some level",
                    )
                ],
                exit_criteria=[],
                indicators=["Unknown Indicator"],
                risk_rules=[],
                unspecified_params=[],
            )
        ],
    )
    strategy = extraction.strategies[0]
    assert "entry_criteria[0].value" in strategy.unspecified_params


def test_trading_logic_extraction_to_file(tmp_path):
    """TradingLogicExtraction can be written to a JSON file."""
    extraction = TradingLogicExtraction(
        video_id="abc123",
        source_language="zh",
        strategies=[],
    )
    path = tmp_path / "extracted_logic.json"
    extraction.to_file(path)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["video_id"] == "abc123"


# ============================================================================
# StageResult tests
# ============================================================================


def test_stage_result_holds_required_fields():
    """StageResult dataclass holds stage_name, artifact_path, skipped flag."""
    result = StageResult(
        stage_name="ingest",
        artifact_path=Path("work/abc123/metadata.json"),
        skipped=False,
    )
    assert result.stage_name == "ingest"
    assert result.artifact_path == Path("work/abc123/metadata.json")
    assert result.skipped is False
    assert result.error is None


def test_stage_result_with_error():
    """StageResult can hold an error message."""
    result = StageResult(
        stage_name="transcript",
        artifact_path=Path("work/abc123/transcript.json"),
        skipped=False,
        error="Network timeout",
    )
    assert result.error == "Network timeout"


def test_stage_result_skipped():
    """StageResult with skipped=True indicates cache hit."""
    result = StageResult(
        stage_name="filter",
        artifact_path=Path("work/abc123/filter.json"),
        skipped=True,
    )
    assert result.skipped is True


# ============================================================================
# artifact_guard tests
# ============================================================================


def test_artifact_guard_returns_true_when_file_exists(tmp_path):
    """artifact_guard returns True when the artifact file already exists."""
    artifact = tmp_path / "existing_artifact.json"
    artifact.write_text('{"data": "cached"}')
    assert artifact_guard(artifact) is True


def test_artifact_guard_returns_false_when_file_missing(tmp_path):
    """artifact_guard returns False when the artifact file does not exist."""
    artifact = tmp_path / "missing_artifact.json"
    assert artifact_guard(artifact) is False
