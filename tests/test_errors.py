"""Tests for yt_to_skill.errors typed error hierarchy."""

import pytest

from yt_to_skill.errors import (
    ExtractionError,
    FormatError,
    LLMError,
    NetworkError,
    SkillError,
)


class TestErrorCategories:
    def test_network_error_category(self):
        err = NetworkError("connection refused")
        assert err.category == "NETWORK"

    def test_extraction_error_category(self):
        err = ExtractionError("no captions found")
        assert err.category == "EXTRACTION"

    def test_llm_error_category(self):
        err = LLMError("invalid api key")
        assert err.category == "LLM"

    def test_format_error_category(self):
        err = FormatError("malformed json")
        assert err.category == "FORMAT"


class TestErrorSuggestions:
    def test_network_error_has_suggestion(self):
        err = NetworkError("timeout")
        assert err.suggestion
        assert len(err.suggestion) > 0

    def test_extraction_error_has_suggestion(self):
        err = ExtractionError("caption unavailable")
        assert err.suggestion
        assert len(err.suggestion) > 0

    def test_llm_error_has_suggestion(self):
        err = LLMError("model not found")
        assert err.suggestion
        assert len(err.suggestion) > 0

    def test_format_error_has_suggestion(self):
        err = FormatError("parse error")
        assert err.suggestion
        assert len(err.suggestion) > 0


class TestErrorMessageFormat:
    def test_network_error_message_format(self):
        err = NetworkError("connection refused")
        msg = str(err)
        assert msg.startswith("[NETWORK]")
        assert "connection refused" in msg
        assert " — " in msg

    def test_extraction_error_message_format(self):
        err = ExtractionError("no captions")
        msg = str(err)
        assert msg.startswith("[EXTRACTION]")
        assert "no captions" in msg
        assert " — " in msg

    def test_llm_error_message_format(self):
        err = LLMError("rate limited")
        msg = str(err)
        assert msg.startswith("[LLM]")
        assert "rate limited" in msg
        assert " — " in msg

    def test_format_error_message_format(self):
        err = FormatError("invalid json")
        msg = str(err)
        assert msg.startswith("[FORMAT]")
        assert "invalid json" in msg
        assert " — " in msg


class TestSkillErrorBase:
    def test_network_error_is_skill_error(self):
        err = NetworkError("x")
        assert isinstance(err, SkillError)

    def test_extraction_error_is_skill_error(self):
        err = ExtractionError("x")
        assert isinstance(err, SkillError)

    def test_llm_error_is_skill_error(self):
        err = LLMError("x")
        assert isinstance(err, SkillError)

    def test_format_error_is_skill_error(self):
        err = FormatError("x")
        assert isinstance(err, SkillError)
