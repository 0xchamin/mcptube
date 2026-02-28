# tests/test_cli_integration.py
"""CLI integration tests using Typer's CliRunner."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from mcptube.cli import app
from mcptube.models import Video
from mcptube.storage.sqlite import SQLiteVideoRepository
from mcptube.storage.vectorstore import ChromaVectorStore


runner = CliRunner()


@pytest.fixture
def mock_service(sample_video):
    """Patch _get_service to return a service with in-memory backends."""
    repo = SQLiteVideoRepository(":memory:")
    store = ChromaVectorStore(":memory:")

    from mcptube.ingestion.youtube import YouTubeExtractor
    extractor = YouTubeExtractor()

    with patch.object(extractor, "extract", return_value=sample_video):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            from mcptube.llm import LLMClient
            with patch("mcptube.llm.litellm.completion") as mock_comp:
                mock_resp = MagicMock()
                mock_resp.choices = [MagicMock()]
                mock_resp.choices[0].message.content = '["AI", "Tutorial"]'
                mock_comp.return_value = mock_resp

                from mcptube.service import McpTubeService
                svc = McpTubeService(
                    repository=repo,
                    extractor=extractor,
                    vectorstore=store,
                    llm_client=LLMClient(),
                )
                with patch("mcptube.cli._get_service", return_value=svc):
                    yield svc


class TestCLI:
    def test_add_and_list(self, mock_service):
        result = runner.invoke(app, ["add", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
        assert result.exit_code == 0
        assert "Added" in result.stdout

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "dQw4w9WgXcQ" in result.stdout

    def test_add_duplicate_error(self, mock_service):
        runner.invoke(app, ["add", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
        result = runner.invoke(app, ["add", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
        assert result.exit_code == 1

    def test_info_by_id(self, mock_service):
        runner.invoke(app, ["add", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
        result = runner.invoke(app, ["info", "dQw4w9WgXcQ"])
        assert result.exit_code == 0
        assert "Intro to Machine Learning" in result.stdout

    def test_info_by_index(self, mock_service):
        runner.invoke(app, ["add", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
        result = runner.invoke(app, ["info", "1"])
        assert result.exit_code == 0
        assert "Intro to Machine Learning" in result.stdout

    def test_remove_and_list(self, mock_service):
        runner.invoke(app, ["add", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
        result = runner.invoke(app, ["remove", "dQw4w9WgXcQ"])
        assert result.exit_code == 0
        assert "Removed" in result.stdout

        result = runner.invoke(app, ["list"])
        assert "empty" in result.stdout.lower()

    def test_search_returns_results(self, mock_service):
        runner.invoke(app, ["add", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
        result = runner.invoke(app, ["search", "neural networks"])
        assert result.exit_code == 0
        assert "neural" in result.stdout.lower()

    def test_no_args_shows_help(self):
        result = runner.invoke(app, [])
        assert result.exit_code == 2
        assert "mcptube" in result.stdout.lower()

