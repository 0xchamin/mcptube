# tests/test_service.py
"""Tests for McpTubeService."""

from unittest.mock import MagicMock, patch

import pytest

from mcptube.service import (
    McpTubeService,
    VideoAlreadyExistsError,
    VideoNotFoundError,
)


class TestAddVideo:
    def test_add_video(self, service, mock_extractor):
        video = service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert video.video_id == "dQw4w9WgXcQ"
        assert video.title == "Intro to Machine Learning"

    def test_add_video_duplicate(self, service):
        service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        with pytest.raises(VideoAlreadyExistsError):
            service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_add_video_auto_classify(self, service):
        video = service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert len(video.tags) > 0

    def test_add_video_no_llm(self, sqlite_repo, chroma_store, mock_extractor, sample_video):
        sample_video.tags = []
        mock_extractor._mock.return_value = sample_video
        with patch.dict("os.environ", {}, clear=True):
            from mcptube.llm import LLMClient
            llm = LLMClient()
            svc = McpTubeService(
                repository=sqlite_repo,
                extractor=mock_extractor,
                vectorstore=chroma_store,
                llm_client=llm,
            )
            video = svc.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            assert video.tags == []



class TestListAndInfo:
    def test_list_videos(self, service):
        service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        videos = service.list_videos()
        assert len(videos) == 1

    def test_get_info(self, service):
        service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        video = service.get_info("dQw4w9WgXcQ")
        assert video.title == "Intro to Machine Learning"
        assert len(video.transcript) > 0

    def test_get_info_not_found(self, service):
        with pytest.raises(VideoNotFoundError):
            service.get_info("nonexistent")


class TestRemoveVideo:
    def test_remove_video(self, service):
        service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        service.remove_video("dQw4w9WgXcQ")
        assert service.list_videos() == []

    def test_remove_video_not_found(self, service):
        with pytest.raises(VideoNotFoundError):
            service.remove_video("nonexistent")


class TestSearch:
    def test_search(self, service):
        service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        results = service.search("neural networks")
        assert len(results) > 0

    def test_search_no_vectorstore(self, sqlite_repo, mock_extractor):
        svc = McpTubeService(
            repository=sqlite_repo,
            extractor=mock_extractor,
            vectorstore=None,
        )
        with pytest.raises(RuntimeError, match="vector store"):
            svc.search("anything")


class TestGetFrame:
    def test_get_frame(self, service, mock_frames):
        service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        path = service.get_frame("dQw4w9WgXcQ", 10.0)
        assert path.exists()

    def test_get_frame_not_found(self, service):
        with pytest.raises(VideoNotFoundError):
            service.get_frame("nonexistent", 10.0)

    def test_get_frame_by_query(self, service, mock_frames):
        service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        result = service.get_frame_by_query("dQw4w9WgXcQ", "neural networks")
        assert "path" in result
        assert "start" in result
        assert "text" in result


class TestClassify:
    def test_classify_video(self, service):
        service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        tags = service.classify_video("dQw4w9WgXcQ")
        assert isinstance(tags, list)
        assert len(tags) > 0

    def test_classify_video_no_llm(self, sqlite_repo, chroma_store, mock_extractor, sample_video):
        with patch.dict("os.environ", {}, clear=True):
            from mcptube.llm import LLMClient
            llm = LLMClient()
            svc = McpTubeService(
                repository=sqlite_repo,
                extractor=mock_extractor,
                vectorstore=chroma_store,
                llm_client=llm,
            )
            sqlite_repo.save(sample_video)
            with pytest.raises(RuntimeError, match="LLM"):
                svc.classify_video(sample_video.video_id)


class TestReport:
    def test_generate_report(self, service, mock_llm):
        service.add_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        mock_llm._mock_completion.return_value.choices[0].message.content = (
            '{"title": "Test Report", "summary": "A summary.", '
            '"sections": [{"heading": "Intro", "content": "Content.", "frames": []}], '
            '"key_takeaways": ["Takeaway 1"]}'
        )
        report, rendered = service.generate_report("dQw4w9WgXcQ")
        assert report.title == "Test Report"
        assert "Test Report" in rendered

    def test_generate_report_no_llm(self, sqlite_repo, chroma_store, mock_extractor):
        with patch.dict("os.environ", {}, clear=True):
            from mcptube.llm import LLMClient
            llm = LLMClient()
            svc = McpTubeService(
                repository=sqlite_repo,
                extractor=mock_extractor,
                vectorstore=chroma_store,
                llm_client=llm,
            )
            with pytest.raises(RuntimeError, match="LLM"):
                svc.generate_report("dQw4w9WgXcQ")
