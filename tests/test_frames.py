# tests/test_frames.py
"""Tests for frame extraction."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcptube.ingestion.frames import FrameExtractionError, FrameExtractor


class TestFrameExtractor:
    @patch("mcptube.ingestion.frames.subprocess.run")
    @patch.object(FrameExtractor, "_resolve_stream_url", return_value="https://stream.example.com/video.mp4")
    def test_extract_frame_calls_ffmpeg(self, mock_resolve, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0)

        extractor = FrameExtractor()
        cache_path = extractor._cache_path("abc123", 10.0)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(b"\xff\xd8fake-jpeg")

        with patch.object(FrameExtractor, "_cache_path", return_value=tmp_path / "test.jpg"):
            # File doesn't exist at tmp_path, so ffmpeg should be called
            result_path = tmp_path / "test.jpg"
            mock_run.return_value = MagicMock(returncode=0)

            with patch.object(extractor, "_extract_with_ffmpeg") as mock_ffmpeg:
                mock_ffmpeg.side_effect = lambda url, ts, out: out.write_bytes(b"\xff\xd8fake")
                path = extractor.extract_frame("abc123", 10.0)

            mock_resolve.assert_called_once_with("abc123")

    @patch.object(FrameExtractor, "_cache_path")
    def test_extract_frame_cached(self, mock_cache_path, tmp_path):
        cached = tmp_path / "cached_frame.jpg"
        cached.write_bytes(b"\xff\xd8fake-jpeg")
        mock_cache_path.return_value = cached

        extractor = FrameExtractor()
        path = extractor.extract_frame("abc123", 10.0)
        assert path == cached

    def test_extract_with_ffmpeg_not_found(self, tmp_path):
        extractor = FrameExtractor()
        output = tmp_path / "out.jpg"

        with patch("mcptube.ingestion.frames.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(FrameExtractionError, match="ffmpeg not found"):
                extractor._extract_with_ffmpeg("https://stream.url", 10.0, output)

    def test_extract_with_ffmpeg_fails(self, tmp_path):
        extractor = FrameExtractor()
        output = tmp_path / "out.jpg"

        mock_result = MagicMock(returncode=1, stderr="Some error")
        with patch("mcptube.ingestion.frames.subprocess.run", return_value=mock_result):
            with pytest.raises(FrameExtractionError, match="ffmpeg failed"):
                extractor._extract_with_ffmpeg("https://stream.url", 10.0, output)

    def test_extract_with_ffmpeg_timeout(self, tmp_path):
        extractor = FrameExtractor()
        output = tmp_path / "out.jpg"

        with patch("mcptube.ingestion.frames.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30)):
            with pytest.raises(FrameExtractionError, match="timed out"):
                extractor._extract_with_ffmpeg("https://stream.url", 10.0, output)

    def test_cache_path_deterministic(self):
        p1 = FrameExtractor._cache_path("abc123", 10.0)
        p2 = FrameExtractor._cache_path("abc123", 10.0)
        assert p1 == p2

    def test_cache_path_different_for_different_input(self):
        p1 = FrameExtractor._cache_path("abc123", 10.0)
        p2 = FrameExtractor._cache_path("abc123", 20.0)
        assert p1 != p2

    @patch("mcptube.ingestion.frames.yt_dlp.YoutubeDL")
    def test_resolve_stream_url(self, mock_ydl_class):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {"url": "https://stream.example.com/video.mp4"}
        mock_ydl_class.return_value.__enter__ = lambda s: mock_ydl
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

        extractor = FrameExtractor()
        url = extractor._resolve_stream_url("abc123")
        assert url == "https://stream.example.com/video.mp4"
