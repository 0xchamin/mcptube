# tests/test_llm.py
"""Tests for LLM client."""

import json
from unittest.mock import MagicMock, patch

import pytest

from mcptube.llm import LLMClient, LLMError


class TestDetectModel:
    def test_detect_model_anthropic(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True):
            client = LLMClient()
            assert "anthropic" in client.model or "claude" in client.model

    def test_detect_model_openai(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            client = LLMClient()
            assert "gpt" in client.model

    def test_detect_model_google(self):
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "goog-test"}, clear=True):
            client = LLMClient()
            assert "gemini" in client.model


class TestAvailable:
    def test_available_with_key(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            client = LLMClient()
            assert client.available is True

    def test_available_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            client = LLMClient()
            assert client.available is False


class TestClassify:
    def test_classify_returns_tags(self, mock_llm):
        tags = mock_llm.classify("Test Video", "A description", "TestChannel")
        assert isinstance(tags, list)
        assert "AI" in tags

    def test_classify_strips_markdown_fences(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            client = LLMClient()
            result = client._parse_tags('```json\n["AI", "ML"]\n```')
            assert result == ["AI", "ML"]

    def test_classify_invalid_response(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            client = LLMClient()
            with pytest.raises(LLMError, match="Failed to parse"):
                client._parse_tags("not json at all")


class TestComplete:
    def test_complete_no_key(self):
        with patch.dict("os.environ", {}, clear=True):
            client = LLMClient()
            with pytest.raises(LLMError, match="No LLM API key"):
                client._complete("test prompt")
