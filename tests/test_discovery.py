# tests/test_discovery.py
"""Tests for video discovery."""

import json
from unittest.mock import MagicMock, patch

import pytest

from mcptube.discovery import DiscoveryResult, VideoDiscovery
from mcptube.llm import LLMError


class TestVideoDiscovery:
    def _mock_search_entries(self):
        return [
            {"id": "vid1", "title": "ML Tutorial", "channel": "TechCh", "duration": 600, "description": "Learn ML", "thumbnail": ""},
            {"id": "vid2", "title": "AI Debate", "channel": "NewsCh", "duration": 1200, "description": "AI ethics", "thumbnail": ""},
            {"id": "vid3", "title": "Deep Learning Intro", "channel": "EduCh", "duration": 900, "description": "DL basics", "thumbnail": ""},
        ]

    def test_discover_returns_clusters(self, mock_llm):
        mock_llm._mock_completion.return_value.choices[0].message.content = json.dumps({
            "clusters": {
                "Tutorials": ["vid1", "vid3"],
                "Debates": ["vid2"],
            }
        })
        discovery = VideoDiscovery(llm=mock_llm)
        with patch.object(discovery, "_search_youtube", return_value=[]):
            entries = self._mock_search_entries()
            from mcptube.discovery import DiscoveredVideo
            videos = [DiscoveredVideo(video_id=e["id"], title=e["title"], channel=e["channel"], duration=e["duration"], description=e["description"]) for e in entries]
            with patch.object(discovery, "_search_youtube", return_value=videos):
                result = discovery.discover("machine learning")
        assert len(result.clusters) == 2
        assert "Tutorials" in result.clusters
        assert len(result.clusters["Tutorials"]) == 2

    def test_discover_empty_results(self, mock_llm):
        discovery = VideoDiscovery(llm=mock_llm)
        with patch.object(discovery, "_search_youtube", return_value=[]):
            result = discovery.discover("nonexistent topic xyz")
        assert result.total_found == 0
        assert result.clusters == {}

    def test_search_youtube_parses_entries(self, mock_llm):
        discovery = VideoDiscovery(llm=mock_llm)
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {"entries": self._mock_search_entries()}
        with patch("mcptube.discovery.yt_dlp.YoutubeDL") as mock_class:
            mock_class.return_value.__enter__ = lambda s: mock_ydl
            mock_class.return_value.__exit__ = MagicMock(return_value=False)
            results = discovery._search_youtube("machine learning")
        assert len(results) == 3
        assert results[0].video_id == "vid1"

    def test_filter_and_cluster(self, mock_llm):
        mock_llm._mock_completion.return_value.choices[0].message.content = json.dumps({
            "clusters": {"Group A": ["vid1"]}
        })
        from mcptube.discovery import DiscoveredVideo
        videos = [DiscoveredVideo(video_id="vid1", title="Test", channel="Ch", duration=100)]
        discovery = VideoDiscovery(llm=mock_llm)
        result = discovery._filter_and_cluster("topic", videos)
        assert "Group A" in result.clusters

    def test_discover_search_failure(self, mock_llm):
        discovery = VideoDiscovery(llm=mock_llm)
        with patch("mcptube.discovery.yt_dlp.YoutubeDL") as mock_class:
            import yt_dlp
            mock_ydl = MagicMock()
            mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError("Network error")
            mock_class.return_value.__enter__ = lambda s: mock_ydl
            mock_class.return_value.__exit__ = MagicMock(return_value=False)
            result = discovery.discover("anything")
        assert result.total_found == 0
