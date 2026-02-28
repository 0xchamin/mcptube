# tests/test_resolve.py
"""Tests for smart video resolver."""

from datetime import datetime, timezone

import pytest

from mcptube.models import Video
from mcptube.service import AmbiguousVideoError, VideoNotFoundError


class TestResolveVideo:
    def _add_videos(self, service, sqlite_repo, mock_extractor, sample_video):
        """Helper to populate the library with multiple videos."""
        service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        v2 = Video(
            video_id="abc12345678",
            title="Advanced Deep Learning",
            channel="AIChannel",
            duration=300.0,
            added_at=datetime(2025, 7, 1, tzinfo=timezone.utc),
        )
        v3 = Video(
            video_id="xyz98765432",
            title="Cooking Pasta Like a Chef",
            channel="FoodChannel",
            duration=600.0,
            added_at=datetime(2025, 8, 1, tzinfo=timezone.utc),
        )
        sqlite_repo.save(v2)
        sqlite_repo.save(v3)

    def test_resolve_by_exact_id(self, service, sqlite_repo, mock_extractor, sample_video):
        self._add_videos(service, sqlite_repo, mock_extractor, sample_video)
        video = service.resolve_video("dQw4w9WgXcQ")
        assert video.video_id == "dQw4w9WgXcQ"

    def test_resolve_by_index(self, service, sqlite_repo, mock_extractor, sample_video):
        self._add_videos(service, sqlite_repo, mock_extractor, sample_video)
        video = service.resolve_video("1")
        assert video is not None

    def test_resolve_by_index_out_of_range(self, service, sqlite_repo, mock_extractor, sample_video):
        self._add_videos(service, sqlite_repo, mock_extractor, sample_video)
        with pytest.raises(VideoNotFoundError, match="out of range"):
            service.resolve_video("99")

    def test_resolve_by_substring_title(self, service, sqlite_repo, mock_extractor, sample_video):
        self._add_videos(service, sqlite_repo, mock_extractor, sample_video)
        video = service.resolve_video("Cooking")
        assert video.video_id == "xyz98765432"

    def test_resolve_by_substring_channel(self, service, sqlite_repo, mock_extractor, sample_video):
        self._add_videos(service, sqlite_repo, mock_extractor, sample_video)
        video = service.resolve_video("FoodChannel")
        assert video.video_id == "xyz98765432"

    def test_resolve_ambiguous(self, service, sqlite_repo, mock_extractor, sample_video):
        self._add_videos(service, sqlite_repo, mock_extractor, sample_video)
        with pytest.raises(AmbiguousVideoError):
            service.resolve_video("Channel")

    def test_resolve_not_found(self, service, sqlite_repo, mock_extractor, sample_video):
        self._add_videos(service, sqlite_repo, mock_extractor, sample_video)
        with pytest.raises(VideoNotFoundError, match="No video matching"):
            service.resolve_video("nonexistent_query")
