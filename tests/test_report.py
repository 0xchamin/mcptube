# tests/test_report.py
"""Tests for ReportBuilder."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcptube.llm import LLMClient, LLMError
from mcptube.report import ReportBuilder


@pytest.fixture
def report_builder(mock_llm, mock_frames):
    return ReportBuilder(llm=mock_llm, frame_extractor=mock_frames)


def _report_json(*, title="Test Report", with_frames=False, video_id=None):
    """Helper to build a valid report JSON string."""
    frames = []
    if with_frames:
        f = {"timestamp": 10.0, "reason": "Key moment"}
        if video_id:
            f["video_id"] = video_id
        frames = [f]
    return json.dumps({
        "title": title,
        "summary": "A test summary.",
        "sections": [
            {"heading": "Section 1", "content": "Content here.", "frames": frames}
        ],
        "key_takeaways": ["Takeaway 1", "Takeaway 2"],
    })


class TestGenerateSingle:
    def test_returns_report(self, report_builder, sample_video, mock_llm):
        mock_llm._mock_completion.return_value.choices[0].message.content = _report_json()
        report = report_builder.generate_single(sample_video)
        assert report.title == "Test Report"
        assert len(report.sections) == 1
        assert len(report.key_takeaways) == 2

    def test_with_query(self, report_builder, sample_video, mock_llm):
        mock_llm._mock_completion.return_value.choices[0].message.content = _report_json()
        report = report_builder.generate_single(sample_video, query="neural networks")
        assert report.title == "Test Report"


class TestGenerateMulti:
    def test_returns_report(self, report_builder, sample_video, mock_llm):
        mock_llm._mock_completion.return_value.choices[0].message.content = _report_json(
            with_frames=True, video_id=sample_video.video_id
        )
        report = report_builder.generate_multi([sample_video], "ML overview")
        assert report.title == "Test Report"


class TestRender:
    def test_to_markdown(self, report_builder, sample_video, mock_llm):
        mock_llm._mock_completion.return_value.choices[0].message.content = _report_json()
        report = report_builder.generate_single(sample_video)
        md = report_builder.to_markdown(report)
        assert "# Test Report" in md
        assert "Takeaway 1" in md

    def test_to_html(self, report_builder, sample_video, mock_llm):
        mock_llm._mock_completion.return_value.choices[0].message.content = _report_json()
        report = report_builder.generate_single(sample_video)
        html = report_builder.to_html(report)
        assert "<h1>Test Report</h1>" in html
        assert "Takeaway 1" in html


class TestFrameExtraction:
    def test_failure_tolerant(self, sample_video, mock_llm):
        from mcptube.ingestion.frames import FrameExtractionError, FrameExtractor
        failing_frames = FrameExtractor()
        with patch.object(failing_frames, "extract_frame", side_effect=FrameExtractionError("fail")):
            builder = ReportBuilder(llm=mock_llm, frame_extractor=failing_frames)
            mock_llm._mock_completion.return_value.choices[0].message.content = _report_json(
                with_frames=True, video_id=sample_video.video_id
            )
            report = builder.generate_single(sample_video)
            assert report.sections[0].frames[0].path is None


class TestParseReport:
    def test_invalid_json(self, report_builder):
        with pytest.raises(LLMError, match="Failed to parse"):
            report_builder._parse_report("not json", default_video_id="abc")


class TestFormatHelpers:
    def test_format_transcript(self, sample_video):
        text = ReportBuilder._format_transcript(sample_video)
        assert "[00:00]" in text
        assert "Hello and welcome" in text

    def test_format_metadata(self, sample_video):
        text = ReportBuilder._format_metadata(sample_video)
        assert "Intro to Machine Learning" in text
        assert "TechChannel" in text
        assert "AI" in text
