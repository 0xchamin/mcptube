# tests/test_youtube.py
"""Tests for YouTube video extraction."""

from unittest.mock import MagicMock, patch

import pytest
import yt_dlp

from mcptube.ingestion.youtube import ExtractionError, YouTubeExtractor


class TestParseVideoId:
    def test_watch_url(self):
        assert YouTubeExtractor.parse_video_id("https://www.youtube.com/watch?v=BpibZSMGtdY") == "BpibZSMGtdY"

    def test_short_url(self):
        assert YouTubeExtractor.parse_video_id("https://youtu.be/BpibZSMGtdY") == "BpibZSMGtdY"

    def test_embed_url(self):
        assert YouTubeExtractor.parse_video_id("https://www.youtube.com/embed/BpibZSMGtdY") == "BpibZSMGtdY"

    def test_v_path_url(self):
        assert YouTubeExtractor.parse_video_id("https://www.youtube.com/v/BpibZSMGtdY") == "BpibZSMGtdY"

    def test_watch_url_with_extras(self):
        url = "https://www.youtube.com/watch?v=BpibZSMGtdY&t=120&list=PLxyz"
        assert YouTubeExtractor.parse_video_id(url) == "BpibZSMGtdY"

    def test_invalid_url(self):
        with pytest.raises(ExtractionError):
            YouTubeExtractor.parse_video_id("https://example.com/not-youtube")


class TestExtract:
    def _make_info(self, *, subtitles=None, auto_captions=None, chapters=None):
        return {
            "id": "BpibZSMGtdY",
            "title": "Test Video",
            "description": "A test video",
            "channel": "TestChannel",
            "uploader": "TestUploader",
            "duration": 120,
            "thumbnail": "https://i.ytimg.com/vi/BpibZSMGtdY/maxresdefault.jpg",
            "subtitles": subtitles or {},
            "automatic_captions": auto_captions or {},
            "chapters": chapters,
        }

    def _make_json3(self, segments):
        """Build a json3 subtitle structure from (start_ms, duration_ms, text) tuples."""
        return {
            "events": [
                {"tStartMs": s, "dDurationMs": d, "segs": [{"utf8": t}]}
                for s, d, t in segments
            ]
        }

    def _sub_entry(self, url="https://example.com/subs.json3"):
        return {"en": [{"ext": "json3", "url": url}]}

    @patch("mcptube.ingestion.youtube.urlopen")
    @patch("mcptube.ingestion.youtube.yt_dlp.YoutubeDL")
    def test_extract_returns_video(self, mock_ydl_class, mock_urlopen):
        json3 = self._make_json3([(0, 5000, "Hello"), (5000, 4000, "World")])
        import json
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value.read.return_value = json.dumps(json3).encode()

        info = self._make_info(subtitles=self._sub_entry())
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = info
        mock_ydl_class.return_value.__enter__ = lambda s: mock_ydl
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

        extractor = YouTubeExtractor()
        video = extractor.extract("https://www.youtube.com/watch?v=BpibZSMGtdY")

        assert video.video_id == "BpibZSMGtdY"
        assert video.title == "Test Video"
        assert video.channel == "TestChannel"
        assert video.duration == 120.0
        assert len(video.transcript) == 2
        assert video.transcript[0].text == "Hello"

    @patch("mcptube.ingestion.youtube.yt_dlp.YoutubeDL")
    def test_extract_with_chapters(self, mock_ydl_class):
        chapters = [
            {"title": "Intro", "start_time": 0},
            {"title": "Main", "start_time": 30},
        ]
        info = self._make_info(chapters=chapters)
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = info
        mock_ydl_class.return_value.__enter__ = lambda s: mock_ydl
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

        extractor = YouTubeExtractor()
        video = extractor.extract("https://www.youtube.com/watch?v=BpibZSMGtdY")
        assert len(video.chapters) == 2
        assert video.chapters[0].title == "Intro"
        assert video.chapters[1].start == 30.0

    @patch("mcptube.ingestion.youtube.yt_dlp.YoutubeDL")
    def test_extract_no_transcript(self, mock_ydl_class):
        info = self._make_info()
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = info
        mock_ydl_class.return_value.__enter__ = lambda s: mock_ydl
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

        extractor = YouTubeExtractor()
        video = extractor.extract("https://www.youtube.com/watch?v=BpibZSMGtdY")
        assert video.transcript == []

    @patch("mcptube.ingestion.youtube.urlopen")
    @patch("mcptube.ingestion.youtube.yt_dlp.YoutubeDL")
    def test_extract_prefers_manual_subs(self, mock_ydl_class, mock_urlopen):
        import json
        manual_json3 = self._make_json3([(0, 5000, "Manual sub")])
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value.read.return_value = json.dumps(manual_json3).encode()

        info = self._make_info(
            subtitles=self._sub_entry(),
            auto_captions={"en": [{"ext": "json3", "url": "https://example.com/auto.json3"}]},
        )
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = info
        mock_ydl_class.return_value.__enter__ = lambda s: mock_ydl
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

        extractor = YouTubeExtractor()
        video = extractor.extract("https://www.youtube.com/watch?v=BpibZSMGtdY")
        assert video.transcript[0].text == "Manual sub"

    @patch("mcptube.ingestion.youtube.yt_dlp.YoutubeDL")
    def test_extract_download_error(self, mock_ydl_class):
        mock_ydl = MagicMock()
        mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError("Network error")
        mock_ydl_class.return_value.__enter__ = lambda s: mock_ydl
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

        extractor = YouTubeExtractor()
        with pytest.raises(ExtractionError, match="Failed to extract"):
            extractor.extract("https://www.youtube.com/watch?v=BpibZSMGtdY")


class TestParseJson3:
    def test_parse_segments(self):
        extractor = YouTubeExtractor()
        data = {
            "events": [
                {"tStartMs": 1000, "dDurationMs": 3000, "segs": [{"utf8": "Hello"}]},
                {"tStartMs": 4000, "dDurationMs": 2000, "segs": [{"utf8": "World"}]},
            ]
        }
        segments = extractor._parse_json3(data)
        assert len(segments) == 2
        assert segments[0].start == 1.0
        assert segments[0].duration == 3.0
        assert segments[0].text == "Hello"

    def test_empty_segments_skipped(self):
        extractor = YouTubeExtractor()
        data = {
            "events": [
                {"tStartMs": 0, "dDurationMs": 1000, "segs": [{"utf8": ""}]},
                {"tStartMs": 1000, "dDurationMs": 1000, "segs": [{"utf8": "\n"}]},
                {"tStartMs": 2000, "dDurationMs": 1000, "segs": [{"utf8": "Real text"}]},
            ]
        }
        segments = extractor._parse_json3(data)
        assert len(segments) == 1
        assert segments[0].text == "Real text"
