# tests/test_server_integration.py
"""MCP server integration tests — test tool functions directly."""

from unittest.mock import MagicMock, patch

import pytest

from mcptube.models import Video
from mcptube.storage.sqlite import SQLiteVideoRepository
from mcptube.storage.vectorstore import ChromaVectorStore


@pytest.fixture
def server_service(sample_video):
    """Patch the server's _get_service to use in-memory backends."""
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
                import mcptube.server as server_mod
                with patch.object(server_mod, "_service", svc):
                    with patch.object(server_mod, "_get_service", return_value=svc):
                        yield svc


class TestMCPTools:
    def test_add_video_tool(self, server_service):
        from mcptube.server import add_video
        result = add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result["video_id"] == "dQw4w9WgXcQ"
        assert result["title"] == "Intro to Machine Learning"

    def test_list_videos_tool(self, server_service):
        from mcptube.server import add_video, list_videos
        add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        result = list_videos()
        assert len(result) == 1
        assert result[0]["video_id"] == "dQw4w9WgXcQ"

    def test_search_tool(self, server_service):
        from mcptube.server import add_video, search
        add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        results = search("neural networks")
        assert len(results) > 0
        assert "text" in results[0]

    def test_get_frame_tool(self, server_service, mock_frames):
        from mcptube.server import add_video, get_frame
        add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        with patch("mcptube.server._get_service") as mock_svc:
            mock_svc.return_value = server_service
            server_service._frame_extractor = mock_frames
            from fastmcp.utilities.types import Image
            result = get_frame("dQw4w9WgXcQ", 10.0)
            assert isinstance(result, Image)

    def test_generate_report_passthrough(self, server_service):
        from mcptube.server import add_video, generate_report
        add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        result = generate_report("dQw4w9WgXcQ")
        assert result["video_id"] == "dQw4w9WgXcQ"
        assert "transcript" in result
        assert "instructions" in result

    def test_discover_passthrough(self, server_service):
        from mcptube.server import discover_videos
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            "entries": [
                {"id": "vid1", "title": "Test", "channel": "Ch", "duration": 60},
            ]
        }
        with patch("yt_dlp.YoutubeDL") as mock_class:
            mock_class.return_value.__enter__ = lambda s: mock_ydl
            mock_class.return_value.__exit__ = MagicMock(return_value=False)
            result = discover_videos("test topic")
        assert result["topic"] == "test topic"
        assert len(result["results"]) == 1


    def test_remove_video_tool(self, server_service):
        from mcptube.server import add_video, remove_video
        add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        result = remove_video("dQw4w9WgXcQ")
        assert result["status"] == "removed"





