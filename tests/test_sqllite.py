# tests/test_sqlite.py
"""Tests for SQLite video repository."""

from datetime import datetime, timezone

import pytest

from mcptube.models import Video
from mcptube.storage.sqlite import SQLiteVideoRepository


class TestSQLiteVideoRepository:
    def test_save_and_get(self, sqlite_repo, sample_video):
        sqlite_repo.save(sample_video)
        loaded = sqlite_repo.get(sample_video.video_id)
        assert loaded is not None
        assert loaded.video_id == sample_video.video_id
        assert loaded.title == sample_video.title
        assert loaded.channel == sample_video.channel
        assert len(loaded.transcript) == len(sample_video.transcript)
        assert len(loaded.chapters) == len(sample_video.chapters)
        assert loaded.tags == sample_video.tags

    def test_save_upsert(self, sqlite_repo, sample_video):
        sqlite_repo.save(sample_video)
        sample_video.title = "Updated Title"
        sqlite_repo.save(sample_video)
        loaded = sqlite_repo.get(sample_video.video_id)
        assert loaded.title == "Updated Title"
        # Ensure no duplicate
        assert len(sqlite_repo.list_all()) == 1

    def test_get_not_found(self, sqlite_repo):
        assert sqlite_repo.get("nonexistent") is None

    def test_list_all_returns_metadata_only(self, sqlite_repo, sample_video):
        sqlite_repo.save(sample_video)
        videos = sqlite_repo.list_all()
        assert len(videos) == 1
        assert videos[0].video_id == sample_video.video_id
        assert videos[0].transcript == []
        assert videos[0].chapters == []

    def test_list_all_ordered_by_added_at(self, sqlite_repo):
        v1 = Video(video_id="aaa", title="First", added_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
        v2 = Video(video_id="bbb", title="Second", added_at=datetime(2025, 6, 1, tzinfo=timezone.utc))
        v3 = Video(video_id="ccc", title="Third", added_at=datetime(2025, 3, 1, tzinfo=timezone.utc))
        sqlite_repo.save(v1)
        sqlite_repo.save(v2)
        sqlite_repo.save(v3)
        videos = sqlite_repo.list_all()
        assert [v.video_id for v in videos] == ["bbb", "ccc", "aaa"]

    def test_delete(self, sqlite_repo, sample_video):
        sqlite_repo.save(sample_video)
        sqlite_repo.delete(sample_video.video_id)
        assert sqlite_repo.get(sample_video.video_id) is None

    def test_delete_nonexistent(self, sqlite_repo):
        sqlite_repo.delete("nonexistent")  # should not raise

    def test_exists_true(self, sqlite_repo, sample_video):
        sqlite_repo.save(sample_video)
        assert sqlite_repo.exists(sample_video.video_id) is True

    def test_exists_false(self, sqlite_repo):
        assert sqlite_repo.exists("nonexistent") is False

    def test_memory_database(self):
        repo = SQLiteVideoRepository(":memory:")
        v = Video(video_id="test123", title="Memory Test")
        repo.save(v)
        assert repo.get("test123") is not None
