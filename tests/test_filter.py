"""Tests for the filter stage — two-stage non-strategy content filter."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_to_skill.config import PipelineConfig
from yt_to_skill.models.artifacts import FilterResult, TranscriptArtifact, VideoMetadata
from yt_to_skill.stages.filter import metadata_prefilter, run_filter


# ---------------------------------------------------------------------------
# metadata_prefilter tests
# ---------------------------------------------------------------------------


class TestMetadataPrefilter:
    def test_returns_false_for_vlog_title(self):
        """Non-strategy title returns False."""
        passed, reason = metadata_prefilter(
            title="My daily vlog today",
            description="Just hanging out",
            tags=[],
        )
        assert passed is False
        assert "no strategy indicators" in reason.lower()

    def test_returns_false_for_daily_life_title(self):
        """'daily life' keyword triggers non-strategy rejection."""
        passed, reason = metadata_prefilter(
            title="Daily life in the city",
            description="",
            tags=[],
        )
        assert passed is False

    def test_returns_false_for_news_recap_title(self):
        """'news recap' keyword triggers non-strategy rejection."""
        passed, reason = metadata_prefilter(
            title="News recap for Monday",
            description="",
            tags=[],
        )
        assert passed is False

    def test_returns_true_for_trading_strategy_title(self):
        """'trading strategy' keyword triggers strategy pass."""
        passed, reason = metadata_prefilter(
            title="My trading strategy for BTC",
            description="",
            tags=[],
        )
        assert passed is True
        assert "strategy indicators" in reason.lower()

    def test_returns_true_for_entry_setup_title(self):
        """'entry setup' keyword triggers strategy pass."""
        passed, reason = metadata_prefilter(
            title="Perfect entry setup explained",
            description="",
            tags=[],
        )
        assert passed is True

    def test_returns_true_for_btc_analysis_title(self):
        """Strategy keywords found in description also count."""
        passed, reason = metadata_prefilter(
            title="BTC analysis video",
            description="RSI MACD indicator breakout",
            tags=[],
        )
        assert passed is True

    def test_checks_description_for_strategy_keywords(self):
        """Description-only strategy keywords can pass the filter."""
        passed, reason = metadata_prefilter(
            title="Watch this video",
            description="Learn the support and resistance strategy",
            tags=[],
        )
        assert passed is True

    def test_checks_tags_for_strategy_keywords(self):
        """Tags can also contribute to strategy score."""
        passed, reason = metadata_prefilter(
            title="Learn more",
            description="",
            tags=["trading", "breakout"],
        )
        assert passed is True

    def test_case_insensitive_matching(self):
        """Keyword matching is case-insensitive."""
        passed, _ = metadata_prefilter(
            title="VLOG of my day",
            description="",
            tags=[],
        )
        assert passed is False

        passed2, _ = metadata_prefilter(
            title="TRADING STRATEGY for BTC",
            description="",
            tags=[],
        )
        assert passed2 is True

    def test_chinese_strategy_keyword_passes(self):
        """Chinese strategy keyword '策略' passes the filter."""
        passed, reason = metadata_prefilter(
            title="BTC交易策略分析",
            description="",
            tags=[],
        )
        assert passed is True

    def test_chinese_strategy_keyword_entry(self):
        """Chinese strategy keyword '入场' passes the filter."""
        passed, _ = metadata_prefilter(
            title="入场点详解",
            description="",
            tags=[],
        )
        assert passed is True

    def test_title_strategy_keyword_outweighs_description_noise(self):
        """Strategy keyword in title (3x weight) should outweigh non-strategy in description."""
        passed, reason = metadata_prefilter(
            title="公开策略分析",
            description="#btcnews #比特幣新聞 news recap",
            tags=[],
        )
        assert passed is True

    def test_empty_inputs_returns_false(self):
        """Empty title/description/tags should fail (no strategy indicators)."""
        passed, reason = metadata_prefilter(title="", description="", tags=[])
        assert passed is False


# ---------------------------------------------------------------------------
# run_filter tests
# ---------------------------------------------------------------------------


class TestRunFilter:
    def _make_metadata(self, video_dir: Path, title: str = "BTC Trading Strategy", description: str = "RSI breakout setup") -> Path:
        """Write a metadata.json for testing."""
        metadata = VideoMetadata(
            video_id="test_video",
            title=title,
            description=description,
            duration_seconds=300.0,
            channel="TestChannel",
            tags=["trading"],
        )
        metadata_path = video_dir / "metadata.json"
        metadata.to_json(metadata_path)
        return metadata_path

    def _make_transcript(self, video_dir: Path, segments=None) -> Path:
        """Write a raw_transcript.json for testing."""
        if segments is None:
            segments = [
                {"start": 0.0, "end": 5.0, "text": "When the MACD crosses we go long"},
                {"start": 5.0, "end": 10.0, "text": "Stop loss below the previous low"},
            ]
        artifact = TranscriptArtifact(
            video_id="test_video",
            source_language="en",
            segments=segments,
            method="captions",
            caption_quality="good",
        )
        transcript_path = video_dir / "raw_transcript.json"
        artifact.to_json(transcript_path)
        return transcript_path

    def test_skips_when_filter_result_exists(self, tmp_work_dir, mock_config, sample_video_id):
        """Artifact guard: run_filter skips if filter_result.json exists."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        filter_path = video_dir / "filter_result.json"

        existing = FilterResult(
            video_id=sample_video_id,
            is_strategy=True,
            confidence=0.9,
            reason="Already computed",
            metadata_pass=True,
        )
        existing.to_json(filter_path)

        result = run_filter(sample_video_id, tmp_work_dir, mock_config)
        assert result.skipped is True
        assert result.artifact_path == filter_path

    def test_stage1_fail_skips_llm_call(self, tmp_work_dir, mock_config, sample_video_id):
        """When metadata_prefilter returns False, LLM classify_content is NOT called."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        self._make_metadata(video_dir, title="Daily vlog compilation", description="")
        self._make_transcript(video_dir)

        mock_llm = MagicMock()

        with patch("yt_to_skill.stages.filter.classify_content") as mock_classify:
            result = run_filter(sample_video_id, tmp_work_dir, mock_config, mock_llm)
            mock_classify.assert_not_called()

        filter_path = video_dir / "filter_result.json"
        assert filter_path.exists()
        filter_result = FilterResult.from_json(filter_path)
        assert filter_result.is_strategy is False
        assert result.skipped is False

    def test_stage2_called_when_stage1_passes(self, tmp_work_dir, mock_config, sample_video_id):
        """When metadata_prefilter returns True, classify_content is called."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        self._make_metadata(video_dir, title="BTC Trading Strategy", description="RSI breakout")
        self._make_transcript(video_dir)

        with patch("yt_to_skill.stages.filter.classify_content") as mock_classify:
            mock_classify.return_value = (True, 0.95)
            mock_llm = MagicMock()
            result = run_filter(sample_video_id, tmp_work_dir, mock_config, mock_llm)
            mock_classify.assert_called_once()

        assert result.skipped is False

    def test_writes_filter_result_json(self, tmp_work_dir, mock_config, sample_video_id):
        """run_filter writes FilterResult to filter_result.json."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        self._make_metadata(video_dir, title="BTC Trading Strategy", description="RSI breakout")
        self._make_transcript(video_dir)

        with patch("yt_to_skill.stages.filter.classify_content") as mock_classify:
            mock_classify.return_value = (True, 0.9)
            mock_llm = MagicMock()
            run_filter(sample_video_id, tmp_work_dir, mock_config, mock_llm)

        filter_path = video_dir / "filter_result.json"
        assert filter_path.exists()
        filter_result = FilterResult.from_json(filter_path)
        assert filter_result.video_id == sample_video_id

    def test_returns_false_with_reason_when_filtered_out(self, tmp_work_dir, mock_config, sample_video_id):
        """run_filter returns is_strategy=False and a reason when video is filtered out."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        self._make_metadata(video_dir, title="Daily vlog today", description="")
        self._make_transcript(video_dir)

        mock_llm = MagicMock()
        result = run_filter(sample_video_id, tmp_work_dir, mock_config, mock_llm)

        filter_path = video_dir / "filter_result.json"
        filter_result = FilterResult.from_json(filter_path)
        assert filter_result.is_strategy is False
        assert filter_result.reason != ""

    def test_none_llm_client_passes_stage2(self, tmp_work_dir, mock_config, sample_video_id):
        """When llm_client is None and Stage 1 passes, Stage 2 is skipped (conservative)."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        self._make_metadata(video_dir, title="BTC Trading Strategy", description="RSI breakout")
        self._make_transcript(video_dir)

        # llm_client=None — should conservatively assume strategy
        result = run_filter(sample_video_id, tmp_work_dir, mock_config, llm_client=None)

        filter_path = video_dir / "filter_result.json"
        assert filter_path.exists()
        filter_result = FilterResult.from_json(filter_path)
        assert filter_result.is_strategy is True
