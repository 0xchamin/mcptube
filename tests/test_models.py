# tests/test_models.py
"""Tests for mcptube domain models."""

from datetime import datetime, timezone

from mcptube.models import Chapter, TranscriptSegment, Video


class TestTranscriptSegment:
    def test_end_computed(self):
        seg = TranscriptSegment(start=10.0, duration=5.0, text="hello")
        assert seg.end == 15.0

    def test_end_computed_fractional(self):
        seg = TranscriptSegment(start=1.5, duration=2.3, text="hello")
        assert abs(seg.end - 3.8) < 1e-9

    def test_serialization_includes_end(self):
        seg = TranscriptSegment(start=10.0, duration=5.0, text="hello")
        data = seg.model_dump()
        assert "end" in data
        assert data["end"] == 15.0


class TestChapter:
    def test_creation(self):
        ch = Chapter(title="Introduction", start=0.0)
        assert ch.title == "Introduction"
        assert ch.start == 0.0


class TestVideo:
    def test_url_computed(self):
        video = Video(video_id="abc12345678", title="Test")
        assert video.url == "https://www.youtube.com/watch?v=abc12345678"

    def test_defaults(self):
        video = Video(video_id="abc12345678", title="Test")
        assert video.chapters == []
        assert video.transcript == []
        assert video.tags == []
        assert video.description == ""
        assert video.channel == ""
        assert video.duration == 0.0

    def test_added_at_utc(self):
        video = Video(video_id="abc12345678", title="Test")
        assert video.added_at.tzinfo is not None
        assert video.added_at.tzinfo == timezone.utc

    def test_full_construction(self, sample_video):
        v = sample_video
        assert v.video_id == "dQw4w9WgXcQ"
        assert v.title == "Intro to Machine Learning"
        assert v.channel == "TechChannel"
        assert v.duration == 25.0
        assert len(v.chapters) == 3
        assert len(v.transcript) == 5
        assert len(v.tags) == 3
        assert v.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_serialization_json_roundtrip(self, sample_video):
        data = sample_video.model_dump(mode="json")
        restored = Video(**data)
        assert restored.video_id == sample_video.video_id
        assert restored.title == sample_video.title
        assert len(restored.transcript) == len(sample_video.transcript)
        assert len(restored.chapters) == len(sample_video.chapters)
        assert restored.tags == sample_video.tags
