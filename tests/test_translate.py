"""Tests for the translate stage — language detection and glossary-injected LLM translation."""

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from yt_to_skill.config import PipelineConfig
from yt_to_skill.models.artifacts import TranscriptArtifact
from yt_to_skill.stages.translate import detect_language, extract_glossary_additions, run_translate


# ---------------------------------------------------------------------------
# detect_language tests
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    def test_returns_zh_for_chinese_text(self):
        """detect_language returns 'zh' for Chinese text."""
        with patch("yt_to_skill.stages.translate.langdetect") as mock_ld:
            mock_ld.detect.return_value = "zh-cn"
            result = detect_language("当MACD金叉出现时我们就可以考虑入场做多止损设在上一个低点下方")
        assert result == "zh"

    def test_returns_en_for_english_text(self):
        """detect_language returns 'en' for English text."""
        with patch("yt_to_skill.stages.translate.langdetect") as mock_ld:
            mock_ld.detect.return_value = "en"
            result = detect_language("When the MACD crosses we look for a long entry stop loss below previous low")
        assert result == "en"

    def test_handles_langdetect_exception_gracefully(self):
        """detect_language returns 'unknown' on LangDetectException."""
        with patch("yt_to_skill.stages.translate.langdetect") as mock_ld:
            from langdetect.lang_detect_exception import LangDetectException
            mock_ld.detect.side_effect = LangDetectException(0, "No features in text")
            mock_ld.LangDetectException = LangDetectException
            result = detect_language("???")
        assert result == "unknown"

    def test_uses_first_1000_chars(self):
        """detect_language only passes first 1000 chars to langdetect."""
        long_text = "A" * 2000
        with patch("yt_to_skill.stages.translate.langdetect") as mock_ld:
            mock_ld.detect.return_value = "en"
            detect_language(long_text)
            called_text = mock_ld.detect.call_args[0][0]
        assert len(called_text) == 1000


# ---------------------------------------------------------------------------
# extract_glossary_additions tests
# ---------------------------------------------------------------------------


class TestExtractGlossaryAdditions:
    def test_extracts_additions_from_response(self):
        """Parses GLOSSARY_ADDITIONS section from LLM response."""
        response = """Translated text here.

GLOSSARY_ADDITIONS:
震仓: shakeout
洗盘: washout
"""
        additions = extract_glossary_additions(response)
        assert len(additions) == 2
        assert ("震仓", "shakeout") in additions
        assert ("洗盘", "washout") in additions

    def test_returns_empty_list_when_no_additions(self):
        """Returns empty list when no GLOSSARY_ADDITIONS section present."""
        response = "Just the translated text with no additions section."
        additions = extract_glossary_additions(response)
        assert additions == []

    def test_handles_empty_additions_section(self):
        """Returns empty list when GLOSSARY_ADDITIONS section is present but empty."""
        response = """Translated text.

GLOSSARY_ADDITIONS:
"""
        additions = extract_glossary_additions(response)
        assert additions == []


# ---------------------------------------------------------------------------
# run_translate tests
# ---------------------------------------------------------------------------


class TestRunTranslate:
    def _make_transcript(
        self,
        video_dir: Path,
        video_id: str,
        source_language: str = "zh",
        segments=None,
    ) -> Path:
        """Write a raw_transcript.json for testing."""
        if segments is None:
            segments = [
                {"start": 0.0, "end": 5.0, "text": "当MACD金叉出现时"},
                {"start": 5.0, "end": 10.0, "text": "我们就可以考虑入场做多"},
            ]
        artifact = TranscriptArtifact(
            video_id=video_id,
            source_language=source_language,
            segments=segments,
            method="captions",
            caption_quality="good",
        )
        transcript_path = video_dir / "raw_transcript.json"
        artifact.to_json(transcript_path)
        return transcript_path

    def test_skips_when_translated_txt_exists(self, tmp_work_dir, mock_config, sample_video_id):
        """Artifact guard: run_translate skips if translated.txt already exists."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        translated_path = video_dir / "translated.txt"
        translated_path.write_text("Already translated text.", encoding="utf-8")

        result = run_translate(sample_video_id, tmp_work_dir, mock_config)
        assert result.skipped is True
        assert result.artifact_path == translated_path

    def test_skips_translation_for_english_transcript(self, tmp_work_dir, mock_config, sample_video_id):
        """run_translate skips LLM call for English transcripts."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        self._make_transcript(
            video_dir,
            sample_video_id,
            source_language="en",
            segments=[{"start": 0.0, "end": 5.0, "text": "MACD crossed, looking for long entry"}],
        )

        with patch("yt_to_skill.stages.translate.translate_text") as mock_translate:
            with patch("yt_to_skill.stages.translate.detect_language", return_value="en"):
                mock_llm = MagicMock()
                result = run_translate(sample_video_id, tmp_work_dir, mock_config, mock_llm)
                mock_translate.assert_not_called()

        translated_path = video_dir / "translated.txt"
        assert translated_path.exists()
        content = translated_path.read_text(encoding="utf-8")
        assert "MACD crossed" in content
        assert result.skipped is False

    def test_calls_translate_text_for_non_english(self, tmp_work_dir, mock_config, sample_video_id):
        """run_translate calls translate_text for non-English transcripts."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        self._make_transcript(video_dir, sample_video_id, source_language="zh")

        with patch("yt_to_skill.stages.translate.translate_text") as mock_translate:
            with patch("yt_to_skill.stages.translate.detect_language", return_value="zh"):
                with patch("yt_to_skill.stages.translate.load_glossary") as mock_glossary:
                    mock_glossary.return_value = {"止损": "stop loss"}
                    mock_translate.return_value = "When MACD crosses, look for long entry."
                    mock_llm = MagicMock()
                    result = run_translate(sample_video_id, tmp_work_dir, mock_config, mock_llm)
                    mock_translate.assert_called_once()

        assert result.skipped is False

    def test_writes_translated_txt(self, tmp_work_dir, mock_config, sample_video_id):
        """run_translate writes the translated text to translated.txt."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        self._make_transcript(video_dir, sample_video_id, source_language="zh")

        with patch("yt_to_skill.stages.translate.translate_text") as mock_translate:
            with patch("yt_to_skill.stages.translate.detect_language", return_value="zh"):
                with patch("yt_to_skill.stages.translate.load_glossary") as mock_glossary:
                    mock_glossary.return_value = {"止损": "stop loss"}
                    mock_translate.return_value = "When MACD crosses, enter long."
                    mock_llm = MagicMock()
                    run_translate(sample_video_id, tmp_work_dir, mock_config, mock_llm)

        translated_path = video_dir / "translated.txt"
        assert translated_path.exists()
        content = translated_path.read_text(encoding="utf-8")
        assert "When MACD crosses" in content

    def test_extracts_and_logs_glossary_additions(self, tmp_work_dir, mock_config, sample_video_id):
        """run_translate extracts GLOSSARY_ADDITIONS and logs them."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        self._make_transcript(video_dir, sample_video_id, source_language="zh")

        llm_response_with_additions = """Translated text here.

GLOSSARY_ADDITIONS:
震仓: shakeout
"""

        with patch("yt_to_skill.stages.translate.translate_text") as mock_translate:
            with patch("yt_to_skill.stages.translate.detect_language", return_value="zh"):
                with patch("yt_to_skill.stages.translate.load_glossary") as mock_glossary:
                    mock_glossary.return_value = {}
                    mock_translate.return_value = llm_response_with_additions
                    mock_llm = MagicMock()

                    with patch("yt_to_skill.stages.translate.logger") as mock_logger:
                        run_translate(sample_video_id, tmp_work_dir, mock_config, mock_llm)
                        # Logger should have been called to log the glossary addition
                        assert mock_logger.info.called

        # Translated output should NOT contain GLOSSARY_ADDITIONS section
        translated_path = video_dir / "translated.txt"
        content = translated_path.read_text(encoding="utf-8")
        assert "GLOSSARY_ADDITIONS" not in content
        assert "Translated text here." in content

    def test_glossary_loaded_from_config_path(self, tmp_work_dir, mock_config, sample_video_id):
        """run_translate loads glossary from the config glossary path."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        self._make_transcript(video_dir, sample_video_id, source_language="zh")

        with patch("yt_to_skill.stages.translate.translate_text") as mock_translate:
            with patch("yt_to_skill.stages.translate.detect_language", return_value="zh"):
                with patch("yt_to_skill.stages.translate.load_glossary") as mock_glossary:
                    mock_glossary.return_value = {"止损": "stop loss"}
                    mock_translate.return_value = "Translated text."
                    mock_llm = MagicMock()
                    run_translate(sample_video_id, tmp_work_dir, mock_config, mock_llm)
                    mock_glossary.assert_called_once()

    def test_langdetect_failure_defaults_to_translation(self, tmp_work_dir, mock_config, sample_video_id):
        """run_translate translates when langdetect returns 'unknown'."""
        video_dir = tmp_work_dir / sample_video_id
        video_dir.mkdir(parents=True)
        self._make_transcript(video_dir, sample_video_id, source_language="zh")

        with patch("yt_to_skill.stages.translate.translate_text") as mock_translate:
            with patch("yt_to_skill.stages.translate.detect_language", return_value="unknown"):
                with patch("yt_to_skill.stages.translate.load_glossary") as mock_glossary:
                    mock_glossary.return_value = {}
                    mock_translate.return_value = "Translated fallback text."
                    mock_llm = MagicMock()
                    result = run_translate(sample_video_id, tmp_work_dir, mock_config, mock_llm)
                    mock_translate.assert_called_once()

        assert result.skipped is False
