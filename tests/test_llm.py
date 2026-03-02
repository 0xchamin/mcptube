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

    def test_detect_model_with_custom_endpoint_and_openai_key(self):
        """Test that openai/ prefix is prepended when using OpenAI-compatible endpoint with OpenAI key."""
        with patch.dict("os.environ", {
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_BASE_URL": "https://custom.endpoint.com/v1"
        }, clear=True):
            client = LLMClient()
            assert client.model.startswith("openai/")

    def test_detect_model_with_custom_endpoint_and_anthropic_key(self):
        """Test that openai/ prefix is NOT prepended when using custom endpoint with Anthropic key."""
        with patch.dict("os.environ", {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "OPENAI_BASE_URL": "https://custom.endpoint.com/v1"
        }, clear=True):
            client = LLMClient()
            assert not client.model.startswith("openai/")
            assert "anthropic" in client.model or "claude" in client.model

    def test_detect_model_with_custom_endpoint_and_google_key(self):
        """Test that openai/ prefix is NOT prepended when using custom endpoint with Google key."""
        with patch.dict("os.environ", {
            "GOOGLE_API_KEY": "goog-test",
            "OPENAI_BASE_URL": "https://custom.endpoint.com/v1"
        }, clear=True):
            client = LLMClient()
            assert not client.model.startswith("openai/")
            assert "gemini" in client.model

    def test_detect_model_with_custom_endpoint_but_no_openai_key(self):
        """Test that openai/ prefix is NOT prepended when custom endpoint is set but no OpenAI key."""
        with patch.dict("os.environ", {
            "OPENAI_BASE_URL": "https://custom.endpoint.com/v1",
            "ANTHROPIC_API_KEY": "sk-ant-test"
        }, clear=True):
            client = LLMClient()
            assert not client.model.startswith("openai/")

    def test_detect_model_with_openai_key_but_no_custom_endpoint(self):
        """Test that model name is NOT prefixed when using OpenAI key without custom endpoint."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            client = LLMClient()
            assert not client.model.startswith("openai/")

    def test_detect_model_with_explicit_model_and_custom_endpoint(self):
        """Test explicit model is prefixed when using OpenAI-compatible endpoint."""
        with patch.dict("os.environ", {
            "MCPTUBE_DEFAULT_MODEL": "gpt-3.5-turbo",
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_BASE_URL": "https://custom.endpoint.com/v1"
        }, clear=True):
            client = LLMClient()
            assert client.model == "openai/gpt-3.5-turbo"

    def test_detect_model_with_explicit_model_and_custom_endpoint_no_openai_key(self):
        """Test explicit model is NOT prefixed when no OpenAI key is present."""
        with patch.dict("os.environ", {
            "MCPTUBE_DEFAULT_MODEL": "gpt-3.5-turbo",
            "OPENAI_BASE_URL": "https://custom.endpoint.com/v1",
            "ANTHROPIC_API_KEY": "sk-ant-test"
        }, clear=True):
            client = LLMClient()
            assert client.model == "gpt-3.5-turbo"
            assert not client.model.startswith("openai/")

    def test_detect_model_with_explicit_model_already_prefixed(self):
        """Test model already prefixed with openai/ is not double-prefixed."""
        with patch.dict("os.environ", {
            "MCPTUBE_DEFAULT_MODEL": "openai/gpt-3.5-turbo",
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_BASE_URL": "https://custom.endpoint.com/v1"
        }, clear=True):
            client = LLMClient()
            assert client.model == "openai/gpt-3.5-turbo"

    def test_detect_model_constructor_parameter_takes_precedence(self):
        """Test that constructor model parameter takes precedence over environment."""
        client = LLMClient(model="custom-model-from-constructor")
        assert client.model == "custom-model-from-constructor"

    def test_detect_model_fallback_to_settings_default(self):
        """Test fallback to settings.default_model when no env vars or keys are set."""
        with patch.dict("os.environ", {}, clear=True):
            client = LLMClient()
            assert client.model == "gpt-4o"

    def test_detect_model_with_custom_endpoint_no_keys_no_model(self):
        """Test behavior with custom endpoint set but no keys or model specified."""
        with patch.dict("os.environ", {
            "OPENAI_BASE_URL": "https://custom.endpoint.com/v1"
        }, clear=True):
            client = LLMClient()
            # Should use default_model without prefix since no OpenAI key
            assert client.model == "gpt-4o"
            assert not client.model.startswith("openai/")


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
