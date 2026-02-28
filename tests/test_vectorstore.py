# tests/test_vectorstore.py
"""Tests for ChromaDB vector store."""

from mcptube.models import TranscriptSegment
from mcptube.storage.vectorstore import ChromaVectorStore


class TestChromaVectorStore:
    def test_index_and_search(self, chroma_store, sample_segments):
        indexed = chroma_store.index_video("vid1", sample_segments)
        assert indexed == len(sample_segments)
        results = chroma_store.search("neural networks")
        assert len(results) > 0

    def test_search_scoped_to_video(self, chroma_store, sample_segments):
        chroma_store.index_video("vid1", sample_segments)
        chroma_store.index_video("vid2", [
            TranscriptSegment(start=0.0, duration=5.0, text="Cooking pasta is easy."),
        ])
        results = chroma_store.search("neural networks", video_id="vid2")
        for r in results:
            assert r.video_id == "vid2"

    def test_search_no_results(self, chroma_store):
        results = chroma_store.search("quantum physics")
        assert results == []

    def test_delete_video_removes_vectors(self, chroma_store, sample_segments):
        chroma_store.index_video("vid1", sample_segments)
        chroma_store.delete_video("vid1")
        results = chroma_store.search("neural networks", video_id="vid1")
        assert results == []

    def test_index_empty_segments(self, chroma_store):
        indexed = chroma_store.index_video("vid1", [])
        assert indexed == 0

    def test_index_replaces_existing(self, chroma_store, sample_segments):
        chroma_store.index_video("vid1", sample_segments)
        new_segments = [
            TranscriptSegment(start=0.0, duration=5.0, text="Completely different content about cooking."),
        ]
        chroma_store.index_video("vid1", new_segments)
        results = chroma_store.search("cooking", video_id="vid1")
        assert len(results) > 0
        assert results[0].text == "Completely different content about cooking."

    def test_search_result_has_timestamps(self, chroma_store, sample_segments):
        chroma_store.index_video("vid1", sample_segments)
        results = chroma_store.search("neural networks")
        assert len(results) > 0
        assert hasattr(results[0], "start")
        assert hasattr(results[0], "end")
        assert results[0].start >= 0.0
        assert results[0].end > results[0].start

    def test_memory_store(self):
        store = ChromaVectorStore(":memory:")
        segs = [TranscriptSegment(start=0.0, duration=3.0, text="Test segment")]
        assert store.index_video("test", segs) == 1
