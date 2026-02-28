# tests/conftest.py
"""Shared fixtures for mcptube tests."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from mcptube.models import Chapter, TranscriptSegment, Video
from mcptube.storage.sqlite import SQLiteVideoRepository
from mcptube.storage.vectorstore import ChromaVectorStore


@pytest.fixture
def sample_segments():
    """List of TranscriptSegment objects for testing."""
    return [
        TranscriptSegment(start=0.0, duration=5.0, text="Hello and welcome to this video."),
        TranscriptSegment(start=5.0, duration=4.5, text="Today we'll talk about machine learning."),
        TranscriptSegment(start=9.5, duration=6.0, text="Let's start with neural networks."),
        TranscriptSegment(start=15.5, duration=5.5, text="A neural network has layers of neurons."),
        TranscriptSegment(start=21.0, duration=4.0, text="Thanks for watching, see you next time."),
    ]


@pytest.fixture
def sample_video(sample_segments):
    """Pre-built Video model with transcript and chapters."""
    return Video(
        video_id="dQw4w9WgXcQ",
        title="Intro to Machine Learning",
        description="A beginner's guide to ML concepts.",
        channel="TechChannel",
        duration=25.0,
        thumbnail_url="https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        chapters=[
            Chapter(title="Introduction", start=0.0),
            Chapter(title="Neural Networks", start=9.5),
            Chapter(title="Outro", start=21.0),
        ],
        transcript=sample_segments,
        tags=["AI", "Machine Learning", "Tutorial"],
        added_at=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sqlite_repo(tmp_path):
    """SQLiteVideoRepository backed by in-memory database."""
    return SQLiteVideoRepository(":memory:")


@pytest.fixture
def chroma_store():
    """ChromaVectorStore backed by in-memory ChromaDB."""
    return ChromaVectorStore(":memory:")


@pytest.fixture
def mock_extractor(sample_video):
    """YouTubeExtractor with mocked yt-dlp returning sample_video."""
    from mcptube.ingestion.youtube import YouTubeExtractor

    extractor = YouTubeExtractor()
    with patch.object(extractor, "extract", return_value=sample_video) as mock:
        extractor._mock = mock
        yield extractor


@pytest.fixture
def mock_llm():
    """LLMClient with mocked litellm.completion."""
    from mcptube.llm import LLMClient

    with patch("mcptube.llm.litellm.completion") as mock_completion:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '["AI", "Tutorial", "Machine Learning"]'
        mock_completion.return_value = mock_response

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key-123"}):
            client = LLMClient()
            client._mock_completion = mock_completion
            yield client

@pytest.fixture
def chroma_store():
    """ChromaVectorStore backed by in-memory ChromaDB."""
    store = ChromaVectorStore(":memory:")
    yield store
    store._client.delete_collection(store._COLLECTION_NAME)


@pytest.fixture
def mock_frames(tmp_path):
    """FrameExtractor with mocked subprocess and yt-dlp."""
    from mcptube.ingestion.frames import FrameExtractor

    extractor = FrameExtractor()
    frame_path = tmp_path / "frame.jpg"
    frame_path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-data")

    with patch.object(extractor, "extract_frame", return_value=frame_path) as mock:
        extractor._mock = mock
        extractor._test_frame_path = frame_path
        yield extractor


@pytest.fixture
def service(sqlite_repo, chroma_store, mock_extractor, mock_frames, mock_llm):
    """Fully wired McpTubeService with all mocked dependencies."""
    from mcptube.service import McpTubeService

    return McpTubeService(
        repository=sqlite_repo,
        extractor=mock_extractor,
        vectorstore=chroma_store,
        frame_extractor=mock_frames,
        llm_client=mock_llm,
    )
