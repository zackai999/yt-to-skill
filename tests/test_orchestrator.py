"""Tests for yt_to_skill/orchestrator.py — TDD RED phase."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from yt_to_skill.config import PipelineConfig
from yt_to_skill.orchestrator import extract_video_id, run_pipeline
from yt_to_skill.stages.base import StageResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def config(tmp_path: Path) -> PipelineConfig:
    """Pipeline config with work_dir in tmp_path."""
    return PipelineConfig(
        openrouter_api_key="test-key",
        work_dir=tmp_path,
    )


@pytest.fixture()
def video_id() -> str:
    return "testVideoId1"


def _make_stage_result(stage_name: str, work_dir: Path, video_id: str, skipped: bool = False) -> StageResult:
    """Create a StageResult for testing."""
    artifact_map = {
        "ingest": "metadata.json",
        "transcript": "raw_transcript.json",
        "filter": "filter_result.json",
        "translate": "translated.txt",
        "extract": "extracted_logic.json",
    }
    return StageResult(
        stage_name=stage_name,
        artifact_path=work_dir / video_id / artifact_map[stage_name],
        skipped=skipped,
    )


# ---------------------------------------------------------------------------
# Test: run_pipeline creates work/<video_id>/ directory
# ---------------------------------------------------------------------------


def test_run_pipeline_creates_work_directory(config: PipelineConfig, video_id: str) -> None:
    """run_pipeline creates work/<video_id>/ directory."""
    expected_dir = config.work_dir / video_id

    with patch("yt_to_skill.orchestrator.run_ingest") as mock_ingest, \
         patch("yt_to_skill.orchestrator.run_transcript") as mock_transcript, \
         patch("yt_to_skill.orchestrator.run_filter") as mock_filter, \
         patch("yt_to_skill.orchestrator.run_translate") as mock_translate, \
         patch("yt_to_skill.orchestrator.run_extract") as mock_extract, \
         patch("yt_to_skill.orchestrator.make_openai_client") as mock_openai, \
         patch("yt_to_skill.orchestrator.make_instructor_client") as mock_instructor:
        # Set up filter to return is_strategy=True (need to read filter result JSON)
        mock_filter_result = StageResult(
            stage_name="filter",
            artifact_path=config.work_dir / video_id / "filter_result.json",
            skipped=False,
        )
        # Write filter JSON with is_strategy=True
        expected_dir.mkdir(parents=True, exist_ok=True)
        (expected_dir / "filter_result.json").write_text(
            '{"video_id": "testVideoId1", "is_strategy": true, "confidence": 0.9, '
            '"reason": "test", "metadata_pass": true, "transcript_pass": true}',
        )
        mock_ingest.return_value = _make_stage_result("ingest", config.work_dir, video_id)
        mock_transcript.return_value = _make_stage_result("transcript", config.work_dir, video_id)
        mock_filter.return_value = mock_filter_result
        mock_translate.return_value = _make_stage_result("translate", config.work_dir, video_id)
        mock_extract.return_value = _make_stage_result("extract", config.work_dir, video_id)

        run_pipeline(video_id, config)

    assert expected_dir.exists()


# ---------------------------------------------------------------------------
# Test: run_pipeline calls stages in order
# ---------------------------------------------------------------------------


def test_run_pipeline_calls_stages_in_order(config: PipelineConfig, video_id: str) -> None:
    """run_pipeline calls stages in order: ingest, transcript, filter, translate, extract."""
    call_order = []

    def _track(name: str):
        def _inner(*args, **kwargs):
            call_order.append(name)
            result = _make_stage_result(name, config.work_dir, video_id)
            if name == "filter":
                # Write filter_result.json so orchestrator can read is_strategy
                result.artifact_path.parent.mkdir(parents=True, exist_ok=True)
                result.artifact_path.write_text(
                    '{"video_id": "testVideoId1", "is_strategy": true, "confidence": 0.9, '
                    '"reason": "test", "metadata_pass": true, "transcript_pass": true}',
                )
            return result
        return _inner

    with patch("yt_to_skill.orchestrator.run_ingest", side_effect=_track("ingest")), \
         patch("yt_to_skill.orchestrator.run_transcript", side_effect=_track("transcript")), \
         patch("yt_to_skill.orchestrator.run_filter", side_effect=_track("filter")), \
         patch("yt_to_skill.orchestrator.run_translate", side_effect=_track("translate")), \
         patch("yt_to_skill.orchestrator.run_extract", side_effect=_track("extract")), \
         patch("yt_to_skill.orchestrator.make_openai_client"), \
         patch("yt_to_skill.orchestrator.make_instructor_client"):
        run_pipeline(video_id, config)

    assert call_order == ["ingest", "transcript", "filter", "translate", "extract"]


# ---------------------------------------------------------------------------
# Test: run_pipeline skips translate+extract when filter returns is_strategy=False
# ---------------------------------------------------------------------------


def test_run_pipeline_skips_when_not_strategy(config: PipelineConfig, video_id: str) -> None:
    """run_pipeline skips translate+extract when filter returns is_strategy=False."""
    video_dir = config.work_dir / video_id
    video_dir.mkdir(parents=True, exist_ok=True)

    filter_result_path = video_dir / "filter_result.json"
    filter_result_path.write_text(
        '{"video_id": "testVideoId1", "is_strategy": false, "confidence": 0.1, '
        '"reason": "not strategy", "metadata_pass": false, "transcript_pass": null}',
    )
    filter_stage_result = StageResult(
        stage_name="filter",
        artifact_path=filter_result_path,
        skipped=False,
    )

    with patch("yt_to_skill.orchestrator.run_ingest") as mock_ingest, \
         patch("yt_to_skill.orchestrator.run_transcript") as mock_transcript, \
         patch("yt_to_skill.orchestrator.run_filter", return_value=filter_stage_result), \
         patch("yt_to_skill.orchestrator.run_translate") as mock_translate, \
         patch("yt_to_skill.orchestrator.run_extract") as mock_extract, \
         patch("yt_to_skill.orchestrator.make_openai_client"), \
         patch("yt_to_skill.orchestrator.make_instructor_client"):
        mock_ingest.return_value = _make_stage_result("ingest", config.work_dir, video_id)
        mock_transcript.return_value = _make_stage_result("transcript", config.work_dir, video_id)

        results = run_pipeline(video_id, config)

    mock_translate.assert_not_called()
    mock_extract.assert_not_called()
    # Only ingest, transcript, filter returned
    assert len(results) == 3


# ---------------------------------------------------------------------------
# Test: run_pipeline returns list of StageResults
# ---------------------------------------------------------------------------


def test_run_pipeline_returns_list_of_stage_results(config: PipelineConfig, video_id: str) -> None:
    """run_pipeline returns list of StageResults."""
    video_dir = config.work_dir / video_id
    video_dir.mkdir(parents=True, exist_ok=True)
    (video_dir / "filter_result.json").write_text(
        '{"video_id": "testVideoId1", "is_strategy": true, "confidence": 0.9, '
        '"reason": "test", "metadata_pass": true, "transcript_pass": true}',
    )

    with patch("yt_to_skill.orchestrator.run_ingest") as mock_ingest, \
         patch("yt_to_skill.orchestrator.run_transcript") as mock_transcript, \
         patch("yt_to_skill.orchestrator.run_filter") as mock_filter, \
         patch("yt_to_skill.orchestrator.run_translate") as mock_translate, \
         patch("yt_to_skill.orchestrator.run_extract") as mock_extract, \
         patch("yt_to_skill.orchestrator.make_openai_client"), \
         patch("yt_to_skill.orchestrator.make_instructor_client"):
        mock_ingest.return_value = _make_stage_result("ingest", config.work_dir, video_id)
        mock_transcript.return_value = _make_stage_result("transcript", config.work_dir, video_id)
        mock_filter.return_value = _make_stage_result("filter", config.work_dir, video_id)
        mock_translate.return_value = _make_stage_result("translate", config.work_dir, video_id)
        mock_extract.return_value = _make_stage_result("extract", config.work_dir, video_id)

        results = run_pipeline(video_id, config)

    assert isinstance(results, list)
    assert all(isinstance(r, StageResult) for r in results)
    assert len(results) == 5


# ---------------------------------------------------------------------------
# Test: idempotency — all stages report skipped=True on re-run
# ---------------------------------------------------------------------------


def test_run_pipeline_all_skipped_on_rerun(config: PipelineConfig, video_id: str) -> None:
    """When all artifacts exist (re-run), all stages report skipped=True."""
    video_dir = config.work_dir / video_id
    video_dir.mkdir(parents=True, exist_ok=True)
    (video_dir / "filter_result.json").write_text(
        '{"video_id": "testVideoId1", "is_strategy": true, "confidence": 0.9, '
        '"reason": "test", "metadata_pass": true, "transcript_pass": true}',
    )

    def _skipped_result(name: str, *args, **kwargs) -> StageResult:
        return _make_stage_result(name, config.work_dir, video_id, skipped=True)

    with patch("yt_to_skill.orchestrator.run_ingest", side_effect=lambda *a, **k: _skipped_result("ingest")), \
         patch("yt_to_skill.orchestrator.run_transcript", side_effect=lambda *a, **k: _skipped_result("transcript")), \
         patch("yt_to_skill.orchestrator.run_filter", side_effect=lambda *a, **k: _skipped_result("filter")), \
         patch("yt_to_skill.orchestrator.run_translate", side_effect=lambda *a, **k: _skipped_result("translate")), \
         patch("yt_to_skill.orchestrator.run_extract", side_effect=lambda *a, **k: _skipped_result("extract")), \
         patch("yt_to_skill.orchestrator.make_openai_client"), \
         patch("yt_to_skill.orchestrator.make_instructor_client"):
        results = run_pipeline(video_id, config)

    assert all(r.skipped for r in results), "All stages should be skipped on re-run"
    assert len(results) == 5


# ---------------------------------------------------------------------------
# Test: LLM clients created once and passed to relevant stages
# ---------------------------------------------------------------------------


def test_run_pipeline_creates_llm_clients_once(config: PipelineConfig, video_id: str) -> None:
    """run_pipeline creates LLM clients once and passes to all stages that need them."""
    video_dir = config.work_dir / video_id
    video_dir.mkdir(parents=True, exist_ok=True)
    (video_dir / "filter_result.json").write_text(
        '{"video_id": "testVideoId1", "is_strategy": true, "confidence": 0.9, '
        '"reason": "test", "metadata_pass": true, "transcript_pass": true}',
    )

    fake_openai_client = MagicMock(name="openai_client")
    fake_instructor_client = MagicMock(name="instructor_client")

    with patch("yt_to_skill.orchestrator.run_ingest") as mock_ingest, \
         patch("yt_to_skill.orchestrator.run_transcript") as mock_transcript, \
         patch("yt_to_skill.orchestrator.run_filter") as mock_filter, \
         patch("yt_to_skill.orchestrator.run_translate") as mock_translate, \
         patch("yt_to_skill.orchestrator.run_extract") as mock_extract, \
         patch("yt_to_skill.orchestrator.make_openai_client", return_value=fake_openai_client) as mock_make_openai, \
         patch("yt_to_skill.orchestrator.make_instructor_client", return_value=fake_instructor_client) as mock_make_instructor:
        mock_ingest.return_value = _make_stage_result("ingest", config.work_dir, video_id)
        mock_transcript.return_value = _make_stage_result("transcript", config.work_dir, video_id)
        mock_filter.return_value = _make_stage_result("filter", config.work_dir, video_id)
        mock_translate.return_value = _make_stage_result("translate", config.work_dir, video_id)
        mock_extract.return_value = _make_stage_result("extract", config.work_dir, video_id)

        run_pipeline(video_id, config)

    # Client factories called exactly once each
    mock_make_openai.assert_called_once_with(config)
    mock_make_instructor.assert_called_once_with(config)

    # filter and translate receive the openai client
    _, filter_kwargs = mock_filter.call_args
    assert filter_kwargs.get("llm_client") is fake_openai_client

    _, translate_kwargs = mock_translate.call_args
    assert translate_kwargs.get("llm_client") is fake_openai_client

    # extract receives the instructor client
    _, extract_kwargs = mock_extract.call_args
    assert extract_kwargs.get("instructor_client") is fake_instructor_client


# ---------------------------------------------------------------------------
# Test: error handling — stage error logged, partial results returned
# ---------------------------------------------------------------------------


def test_run_pipeline_handles_stage_errors_gracefully(config: PipelineConfig, video_id: str) -> None:
    """run_pipeline handles stage errors gracefully (logs error, returns partial results)."""
    video_dir = config.work_dir / video_id
    video_dir.mkdir(parents=True, exist_ok=True)
    (video_dir / "filter_result.json").write_text(
        '{"video_id": "testVideoId1", "is_strategy": true, "confidence": 0.9, '
        '"reason": "test", "metadata_pass": true, "transcript_pass": true}',
    )

    with patch("yt_to_skill.orchestrator.run_ingest") as mock_ingest, \
         patch("yt_to_skill.orchestrator.run_transcript") as mock_transcript, \
         patch("yt_to_skill.orchestrator.run_filter", side_effect=RuntimeError("LLM call failed")), \
         patch("yt_to_skill.orchestrator.run_translate") as mock_translate, \
         patch("yt_to_skill.orchestrator.run_extract") as mock_extract, \
         patch("yt_to_skill.orchestrator.make_openai_client"), \
         patch("yt_to_skill.orchestrator.make_instructor_client"):
        mock_ingest.return_value = _make_stage_result("ingest", config.work_dir, video_id)
        mock_transcript.return_value = _make_stage_result("transcript", config.work_dir, video_id)

        results = run_pipeline(video_id, config)

    # Should not raise — returns partial results
    assert isinstance(results, list)
    # Should have at least ingest and transcript results
    assert len(results) >= 2
    # The failed stage should have an error result
    stage_names = [r.stage_name for r in results]
    assert "filter" in stage_names
    filter_result = next(r for r in results if r.stage_name == "filter")
    assert filter_result.error is not None


# ---------------------------------------------------------------------------
# Test: extract_video_id with various URL formats
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url,expected_id", [
    ("https://www.youtube.com/watch?v=abc123XYZ", "abc123XYZ"),
    ("https://youtube.com/watch?v=abc123XYZ", "abc123XYZ"),
    ("https://youtu.be/abc123XYZ", "abc123XYZ"),
    ("https://www.youtube.com/shorts/abc123XYZ", "abc123XYZ"),
    ("http://youtu.be/abc123XYZ?t=30", "abc123XYZ"),
    ("https://www.youtube.com/watch?v=abc123XYZ&list=PLtest", "abc123XYZ"),
])
def test_extract_video_id_valid_urls(url: str, expected_id: str) -> None:
    """extract_video_id parses various YouTube URL formats correctly."""
    assert extract_video_id(url) == expected_id


def test_extract_video_id_raises_on_invalid_url() -> None:
    """extract_video_id raises ValueError for unrecognized URL formats."""
    with pytest.raises(ValueError, match="Unrecognized YouTube URL"):
        extract_video_id("https://vimeo.com/12345")


def test_extract_video_id_raises_on_non_youtube() -> None:
    """extract_video_id raises ValueError for non-YouTube URLs."""
    with pytest.raises(ValueError):
        extract_video_id("https://example.com/video/abc123")
