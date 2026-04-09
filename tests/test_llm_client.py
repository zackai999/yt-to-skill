"""Tests for the LLM client wrapper."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from yt_to_skill.config import PipelineConfig
from yt_to_skill.models.extraction import TradingLogicExtraction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> PipelineConfig:
    """Return a PipelineConfig with test values."""
    return PipelineConfig(
        openrouter_api_key="test-key-12345",
        translation_model="anthropic/claude-sonnet-4-20250514",
        extraction_model="anthropic/claude-sonnet-4-20250514",
        filter_model="mistralai/mistral-7b-instruct",
        max_tokens_translation=2048,
        max_tokens_extraction=4096,
    )


@pytest.fixture
def sample_glossary() -> dict:
    return {"多头": "long", "空头": "short", "止损": "stop loss", "均线": "moving average"}


# ---------------------------------------------------------------------------
# make_openai_client tests
# ---------------------------------------------------------------------------


class TestMakeOpenaiClient:
    def test_base_url_is_openrouter(self, config):
        """make_openai_client must set base_url to OpenRouter."""
        from yt_to_skill.llm.client import make_openai_client

        with patch("yt_to_skill.llm.client.openai.OpenAI") as mock_cls:
            make_openai_client(config)
            mock_cls.assert_called_once()
            kwargs = mock_cls.call_args.kwargs
            assert kwargs["base_url"] == "https://openrouter.ai/api/v1"

    def test_api_key_from_config(self, config):
        """make_openai_client must pass the api_key from config."""
        from yt_to_skill.llm.client import make_openai_client

        with patch("yt_to_skill.llm.client.openai.OpenAI") as mock_cls:
            make_openai_client(config)
            kwargs = mock_cls.call_args.kwargs
            assert kwargs["api_key"] == "test-key-12345"


# ---------------------------------------------------------------------------
# make_instructor_client tests
# ---------------------------------------------------------------------------


class TestMakeInstructorClient:
    def test_returns_instructor_patched_client(self, config):
        """make_instructor_client must return an instructor-patched client."""
        from yt_to_skill.llm.client import make_instructor_client

        with patch("yt_to_skill.llm.client.openai.OpenAI") as mock_openai, patch(
            "yt_to_skill.llm.client.instructor.from_openai"
        ) as mock_instructor:
            mock_instructor.return_value = MagicMock(name="instructor_client")
            result = make_instructor_client(config)
            mock_instructor.assert_called_once()
            assert result is mock_instructor.return_value


# ---------------------------------------------------------------------------
# translate_text tests
# ---------------------------------------------------------------------------


class TestTranslateText:
    def test_includes_glossary_terms_in_messages(self, config, sample_glossary):
        """translate_text must inject glossary terms into the messages."""
        from yt_to_skill.llm.client import translate_text

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "When MACD golden cross appears"
        mock_client.chat.completions.create.return_value = mock_response

        result = translate_text(mock_client, "当MACD金叉出现", sample_glossary, config)

        # Check glossary terms are in the request
        create_call = mock_client.chat.completions.create.call_args
        messages = create_call.kwargs.get("messages") or create_call.args[0] if create_call.args else create_call.kwargs["messages"]
        all_message_text = " ".join(m.get("content", "") for m in messages)
        assert "多头" in all_message_text or "long" in all_message_text

    def test_max_tokens_from_config(self, config, sample_glossary):
        """translate_text must pass max_tokens from config."""
        from yt_to_skill.llm.client import translate_text

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "translated text"
        mock_client.chat.completions.create.return_value = mock_response

        translate_text(mock_client, "some chinese text", sample_glossary, config)

        create_call = mock_client.chat.completions.create.call_args
        kwargs = create_call.kwargs
        assert kwargs.get("max_tokens") == config.max_tokens_translation

    def test_uses_translation_model(self, config, sample_glossary):
        """translate_text must use config.translation_model."""
        from yt_to_skill.llm.client import translate_text

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "translated"
        mock_client.chat.completions.create.return_value = mock_response

        translate_text(mock_client, "text", sample_glossary, config)

        create_call = mock_client.chat.completions.create.call_args
        kwargs = create_call.kwargs
        assert kwargs.get("model") == config.translation_model


# ---------------------------------------------------------------------------
# classify_content tests
# ---------------------------------------------------------------------------


class TestClassifyContent:
    def test_returns_bool_and_float(self, config):
        """classify_content must return (bool, float)."""
        from yt_to_skill.llm.client import classify_content

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "STRATEGY\n0.9\nClear entry and exit rules."
        mock_client.chat.completions.create.return_value = mock_response

        is_strategy, confidence = classify_content(
            mock_client, "MACD Strategy", "Learn to trade", "当MACD金叉出现时...", config
        )

        assert isinstance(is_strategy, bool)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_strategy_classification(self, config):
        """classify_content returns True when LLM returns STRATEGY."""
        from yt_to_skill.llm.client import classify_content

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "STRATEGY\n0.85\nHas entry and exit rules."
        mock_client.chat.completions.create.return_value = mock_response

        is_strategy, confidence = classify_content(
            mock_client, "Title", "Desc", "Transcript...", config
        )

        assert is_strategy is True
        assert confidence == pytest.approx(0.85)

    def test_not_strategy_classification(self, config):
        """classify_content returns False when LLM returns NOT_STRATEGY."""
        from yt_to_skill.llm.client import classify_content

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "NOT_STRATEGY\n0.2\nJust market news."
        mock_client.chat.completions.create.return_value = mock_response

        is_strategy, confidence = classify_content(
            mock_client, "Title", "Desc", "Transcript...", config
        )

        assert is_strategy is False
        assert confidence == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# extract_trading_logic tests
# ---------------------------------------------------------------------------


class TestExtractTradingLogic:
    def test_uses_response_model_trading_logic_extraction(self, config):
        """extract_trading_logic must use response_model=TradingLogicExtraction."""
        from yt_to_skill.llm.client import extract_trading_logic

        mock_instructor_client = MagicMock()
        mock_result = MagicMock(spec=TradingLogicExtraction)
        mock_instructor_client.chat.completions.create.return_value = mock_result

        result = extract_trading_logic(
            mock_instructor_client, "translated text", "test_vid_id", "zh", config
        )

        create_call = mock_instructor_client.chat.completions.create.call_args
        kwargs = create_call.kwargs
        assert kwargs.get("response_model") is TradingLogicExtraction

    def test_temperature_is_zero(self, config):
        """extract_trading_logic must set temperature=0."""
        from yt_to_skill.llm.client import extract_trading_logic

        mock_instructor_client = MagicMock()
        mock_result = MagicMock(spec=TradingLogicExtraction)
        mock_instructor_client.chat.completions.create.return_value = mock_result

        extract_trading_logic(
            mock_instructor_client, "translated text", "test_vid_id", "zh", config
        )

        create_call = mock_instructor_client.chat.completions.create.call_args
        kwargs = create_call.kwargs
        assert kwargs.get("temperature") == 0


# ---------------------------------------------------------------------------
# No direct openai imports in stages/
# ---------------------------------------------------------------------------


class TestNoDirectOpenAIImports:
    def test_stages_do_not_import_openai_directly(self):
        """No file under yt_to_skill/stages/ should import openai directly."""
        stages_dir = Path(__file__).parent.parent / "yt_to_skill" / "stages"
        if not stages_dir.exists():
            pytest.skip("stages/ directory does not exist yet")

        for py_file in stages_dir.rglob("*.py"):
            content = py_file.read_text()
            assert "from openai" not in content, (
                f"{py_file} contains 'from openai' — use yt_to_skill.llm.client instead"
            )
            assert "import openai" not in content, (
                f"{py_file} contains 'import openai' — use yt_to_skill.llm.client instead"
            )


# ---------------------------------------------------------------------------
# load_glossary tests
# ---------------------------------------------------------------------------


class TestLoadGlossary:
    def test_load_glossary_returns_dict(self, tmp_path):
        """load_glossary must return a dict from a JSON file."""
        from yt_to_skill.llm.client import load_glossary

        glossary_data = {"多头": "long", "空头": "short"}
        glossary_file = tmp_path / "test_glossary.json"
        glossary_file.write_text(json.dumps(glossary_data, ensure_ascii=False))

        result = load_glossary(glossary_file)

        assert isinstance(result, dict)
        assert result["多头"] == "long"
        assert result["空头"] == "short"
