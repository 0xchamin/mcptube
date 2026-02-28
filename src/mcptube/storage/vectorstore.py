"""Vector store interface and ChromaDB implementation for semantic search."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import chromadb

from mcptube.config import settings
from mcptube.models import TranscriptSegment

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single semantic search result."""

    video_id: str
    text: str
    start: float
    end: float
    score: float  # lower = more similar (distance)


class VectorStore(ABC):
    """Abstract interface for vector-based transcript search.

    Concrete implementations (ChromaDB, pgvector, etc.) must
    implement this interface. Keeps the service layer decoupled
    from any specific vector database.
    """

    @abstractmethod
    def index_video(self, video_id: str, segments: list[TranscriptSegment]) -> int:
        """Embed and store transcript segments for a video.

        Args:
            video_id: YouTube video ID.
            segments: Transcript segments to index.

        Returns:
            Number of segments indexed.
        """

    @abstractmethod
    def search(
        self,
        query: str,
        video_id: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Semantic search across indexed transcripts.

        Args:
            query: Natural language search query.
            video_id: If provided, scope search to a single video.
            tags: If provided, filter to videos with any of these tags.
            limit: Maximum number of results.

        Returns:
            List of SearchResult ordered by relevance.
        """

    @abstractmethod
    def delete_video(self, video_id: str) -> None:
        """Remove all indexed segments for a video."""


class ChromaVectorStore(VectorStore):
    """ChromaDB-backed vector store using default local embeddings.

    Uses ChromaDB's built-in embedding function (all-MiniLM-L6-v2)
    for zero-config operation. Persistent storage in the mcptube data dir.
    """

    _COLLECTION_NAME = "mcptube_transcripts"
    _BATCH_SIZE = 500  # ChromaDB add batch limit

    def __init__(self, path: str | None = None) -> None:
        """Initialize ChromaDB persistent client.

        Args:
            path: Directory for ChromaDB storage. Defaults to settings.data_dir / "chroma".
                  Use ":memory:" for testing.
        """
        if path == ":memory:":
            self._client = chromadb.Client()
        else:
            chroma_path = path or str(settings.data_dir / "chroma")
            self._client = chromadb.PersistentClient(path=chroma_path)

        self._collection = self._client.get_or_create_collection(
            name=self._COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def index_video(self, video_id: str, segments: list[TranscriptSegment]) -> int:
        """Embed and store transcript segments for a video."""
        if not segments:
            logger.warning("No segments to index for video: %s", video_id)
            return 0

        # Remove existing segments for this video (upsert-like behavior)
        self.delete_video(video_id)

        documents = []
        metadatas = []
        ids = []

        for i, seg in enumerate(segments):
            text = seg.text.strip()
            if not text:
                continue

            documents.append(text)
            metadatas.append({
                "video_id": video_id,
                "start": seg.start,
                "end": seg.end,
                "segment_index": i,
            })
            ids.append(f"{video_id}_{i}")

        # ChromaDB has batch size limits — add in chunks
        indexed = 0
        for batch_start in range(0, len(documents), self._BATCH_SIZE):
            batch_end = batch_start + self._BATCH_SIZE
            self._collection.add(
                documents=documents[batch_start:batch_end],
                metadatas=metadatas[batch_start:batch_end],
                ids=ids[batch_start:batch_end],
            )
            indexed += len(documents[batch_start:batch_end])

        logger.info("Indexed %d segments for video: %s", indexed, video_id)
        return indexed

    def search(
        self,
        query: str,
        video_id: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Semantic search across indexed transcripts."""
        where = None
        if video_id:
            where = {"video_id": video_id}

        # Note: tag filtering requires cross-referencing with SQLite metadata.
        # For now, video_id filtering is handled natively by ChromaDB.
        # Tag-based filtering will be added when auto-classification lands (F4).

        results = self._collection.query(
            query_texts=[query],
            n_results=limit,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if results and results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                search_results.append(SearchResult(
                    video_id=meta["video_id"],
                    text=doc,
                    start=meta["start"],
                    end=meta["end"],
                    score=dist,
                ))

        return search_results

    def delete_video(self, video_id: str) -> None:
        """Remove all indexed segments for a video."""
        try:
            self._collection.delete(where={"video_id": video_id})
            logger.info("Deleted vectors for video: %s", video_id)
        except Exception:
            # No documents to delete — this is fine
            pass
