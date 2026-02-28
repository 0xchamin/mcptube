"""Core business logic for mcptube."""

import logging
from pathlib import Path

from mcptube.config import settings
from mcptube.ingestion.frames import FrameExtractionError, FrameExtractor
from mcptube.ingestion.youtube import ExtractionError, YouTubeExtractor
from mcptube.models import Video
from mcptube.storage.repository import VideoRepository
from mcptube.storage.vectorstore import SearchResult, VectorStore
from mcptube.llm import LLMClient, LLMError
from mcptube.report import Report, ReportBuilder
from mcptube.discovery import DiscoveryResult, VideoDiscovery




logger = logging.getLogger(__name__)


class VideoNotFoundError(Exception):
    """Raised when a requested video is not in the library."""


class VideoAlreadyExistsError(Exception):
    """Raised when attempting to add a video that is already in the library."""


class AmbiguousVideoError(Exception):
    """Raised when a query matches multiple videos and cannot be disambiguated."""


class McpTubeService:
    """Core service layer — single orchestration point for all mcptube operations.

    Both the CLI and MCP server are thin wrappers over this class.
    Dependencies are injected via constructor for testability and
    backend swappability (DIP).
    """

    def __init__(
        self,
        repository: VideoRepository,
        extractor: YouTubeExtractor | None = None,
        vectorstore: VectorStore | None = None,
        frame_extractor: FrameExtractor | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._repo = repository
        self._extractor = extractor or YouTubeExtractor()
        self._vectorstore = vectorstore
        self._frame_extractor = frame_extractor or FrameExtractor()
        self._llm = llm_client or LLMClient()
        self._report_builder: ReportBuilder | None = None
        self._discovery: VideoDiscovery | None = None

        if self._llm.available:
            self._discovery = VideoDiscovery(llm=self._llm)

        if self._llm.available:
            self._report_builder = ReportBuilder(
                llm=self._llm,
                frame_extractor=self._frame_extractor,
            )

        settings.ensure_dirs()

    def add_video(self, url: str) -> Video:
        """Ingest a YouTube video into the library.

        Extracts metadata and transcript, persists to storage,
        and indexes transcript segments into the vector store.

        Args:
            url: YouTube video URL in any standard format.

        Returns:
            The ingested Video model.

        Raises:
            ExtractionError: If video extraction fails.
            VideoAlreadyExistsError: If the video is already in the library.
        """
        video_id = YouTubeExtractor.parse_video_id(url)

        if self._repo.exists(video_id):
            raise VideoAlreadyExistsError(
                f"Video already in library: {video_id}. "
                "Use remove_video() first to re-ingest."
            )

        logger.info("Ingesting video: %s", url)
        video = self._extractor.extract(url)
        self._repo.save(video)

        # Index transcript segments into vector store
        if self._vectorstore and video.transcript:
            indexed = self._vectorstore.index_video(video.video_id, video.transcript)
            logger.info("Indexed %d segments into vector store", indexed)

        # Auto-classify if LLM client is available
        if self._llm and self._llm.available:
            try:
                video.tags = self._llm.classify(video.title, video.description, video.channel)
                self._repo.save(video)  # re-save with tags
                logger.info("Auto-classified: %s", video.tags)
            except LLMError as e:
                logger.warning("Auto-classification failed: %s", e)


        logger.info("Video added: %s — %s", video.video_id, video.title)
        return video

    def list_videos(self) -> list[Video]:
        """List all videos in the library (metadata only, no transcripts)."""
        return self._repo.list_all()

    def get_info(self, video_id: str) -> Video:
        """Get full video information including transcript.

        Args:
            video_id: YouTube video ID.

        Returns:
            Full Video model with transcript.

        Raises:
            VideoNotFoundError: If the video is not in the library.
        """
        video = self._repo.get(video_id)
        if video is None:
            raise VideoNotFoundError(f"Video not found: {video_id}")
        return video

    def remove_video(self, video_id: str) -> None:
        """Remove a video from the library and vector store.

        Args:
            video_id: YouTube video ID.

        Raises:
            VideoNotFoundError: If the video is not in the library.
        """
        if not self._repo.exists(video_id):
            raise VideoNotFoundError(f"Video not found: {video_id}")
        self._repo.delete(video_id)

        if self._vectorstore:
            self._vectorstore.delete_video(video_id)

        logger.info("Video removed: %s", video_id)

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

        Raises:
            RuntimeError: If no vector store is configured.
        """
        if not self._vectorstore:
            raise RuntimeError("Semantic search requires a vector store.")
        return self._vectorstore.search(query, video_id=video_id, tags=tags, limit=limit)

    def get_frame(self, video_id: str, timestamp: float) -> Path:
        """Extract a frame at a specific timestamp.

        Args:
            video_id: YouTube video ID.
            timestamp: Time in seconds.

        Returns:
            Path to the extracted JPEG frame.

        Raises:
            VideoNotFoundError: If the video is not in the library.
            FrameExtractionError: If frame extraction fails.
        """
        if not self._repo.exists(video_id):
            raise VideoNotFoundError(f"Video not found: {video_id}")
        return self._frame_extractor.extract_frame(video_id, timestamp)

    def get_frame_by_query(self, video_id: str, query: str) -> dict:
        """Search transcript and extract a frame at the best matching moment.

        Args:
            video_id: YouTube video ID.
            query: Natural language description of the moment to capture.

        Returns:
            Dict with 'path' (Path to frame), 'start', 'end', 'text' of matched segment.

        Raises:
            VideoNotFoundError: If the video is not in the library.
            RuntimeError: If no vector store is configured.
            FrameExtractionError: If frame extraction fails.
        """
        if not self._repo.exists(video_id):
            raise VideoNotFoundError(f"Video not found: {video_id}")
        if not self._vectorstore:
            raise RuntimeError("Frame-by-query requires a vector store.")

        results = self._vectorstore.search(query, video_id=video_id, limit=1)
        if not results:
            raise VideoNotFoundError(f"No transcript match for query: {query}")

        best = results[0]
        frame_path = self._frame_extractor.extract_frame(video_id, best.start)

        return {
            "path": frame_path,
            "start": best.start,
            "end": best.end,
            "text": best.text,
            "score": best.score,
        }
    
    def classify_video(self, video_id: str) -> list[str]:
        """Classify or re-classify a video using LLM.

        Args:
            video_id: YouTube video ID.

        Returns:
            List of classification tags.

        Raises:
            VideoNotFoundError: If the video is not in the library.
            LLMError: If classification fails.
            RuntimeError: If no LLM client is configured.
        """
        video = self.get_info(video_id)
        if not self._llm or not self._llm.available:
            raise RuntimeError("Classification requires an LLM. Set an API key.")
        tags = self._llm.classify(video.title, video.description, video.channel)
        video.tags = tags
        self._repo.save(video)
        return tags
    
    def generate_report(
        self, video_id: str, query: str | None = None, fmt: str = "markdown"
    ) -> tuple[Report, str]:
        """Generate an illustrated report for a single video.

        Args:
            video_id: YouTube video ID.
            query: Optional focus query to guide the report.
            fmt: Output format — "markdown" or "html".

        Returns:
            Tuple of (Report object, rendered string).

        Raises:
            VideoNotFoundError: If video not in library.
            RuntimeError: If no LLM configured.
        """
        if not self._report_builder:
            raise RuntimeError("Report generation requires an LLM. Set an API key.")
        video = self.get_info(video_id)
        report = self._report_builder.generate_single(video, query=query)
        rendered = (
            self._report_builder.to_html(report)
            if fmt == "html"
            else self._report_builder.to_markdown(report)
        )
        return report, rendered

    def generate_report_from_query(
        self, query: str, tags: list[str] | None = None, fmt: str = "markdown"
    ) -> tuple[Report, str]:
        """Generate an illustrated report across matching library videos.

        Args:
            query: Search query to find relevant videos.
            tags: Optional tag filter.
            fmt: Output format — "markdown" or "html".

        Returns:
            Tuple of (Report object, rendered string).

        Raises:
            RuntimeError: If no LLM or vector store configured.
        """
        if not self._report_builder:
            raise RuntimeError("Report generation requires an LLM. Set an API key.")
        if not self._vectorstore:
            raise RuntimeError("Query-based reports require a vector store.")

        results = self._vectorstore.search(query, tags=tags, limit=20)
        if not results:
            raise VideoNotFoundError(f"No matching content for: {query}")

        # Collect unique video IDs from search results
        video_ids = list(dict.fromkeys(r.video_id for r in results))
        videos = [self.get_info(vid) for vid in video_ids]

        report = self._report_builder.generate_multi(videos, query)
        rendered = (
            self._report_builder.to_html(report)
            if fmt == "html"
            else self._report_builder.to_markdown(report)
        )
        return report, rendered

    def discover_videos(self, topic: str) -> DiscoveryResult:
        """Search YouTube for videos on a topic, filter, and cluster.

        Args:
            topic: Topic to search for.

        Returns:
            DiscoveryResult with clustered videos.

        Raises:
            RuntimeError: If no LLM configured.
        """
        if not self._discovery:
            raise RuntimeError("Discovery requires an LLM. Set an API key.")
        return self._discovery.discover(topic)

    def synthesize(self, video_ids: list[str], topic: str, fmt: str = "markdown") -> tuple[Report, str]:
        """Cross-reference themes across multiple videos with illustrated output.

        Args:
            video_ids: List of YouTube video IDs to synthesize.
            topic: Focus topic for synthesis.
            fmt: Output format — "markdown" or "html".

        Returns:
            Tuple of (Report object, rendered string).

        Raises:
            VideoNotFoundError: If any video not found.
            RuntimeError: If no LLM configured.
        """
        if not self._report_builder:
            raise RuntimeError("Synthesis requires an LLM. Set an API key.")
        videos = [self.get_info(vid) for vid in video_ids]
        report = self._report_builder.generate_multi(videos, topic)
        rendered = (
            self._report_builder.to_html(report)
            if fmt == "html"
            else self._report_builder.to_markdown(report)
        )
        return report, rendered


    def resolve_video(self, query: str) -> Video:
        """Smart video resolver — tiered resolution strategy.

        Tier 1: Exact video ID match
        Tier 2: Numeric index from list (most recent first)
        Tier 3: Exact case-insensitive substring match on title/channel
        Tier 4: LLM resolution (when BYOK key available) — future

        Args:
            query: Video ID, numeric index, or search text.

        Returns:
            Resolved Video.

        Raises:
            VideoNotFoundError: If no video can be resolved.
            AmbiguousVideoError: If multiple videos match and no LLM to disambiguate.
        """
        # Tier 1: Exact video ID
        video = self._repo.get(query)
        if video is not None:
            return video

        # Tier 2: Numeric index
        if query.isdigit():
            videos = self._repo.list_all()
            idx = int(query) - 1  # 1-based for humans
            if 0 <= idx < len(videos):
                return self._repo.get(videos[idx].video_id)
            raise VideoNotFoundError(
                f"Index {query} out of range. Library has {len(videos)} video(s)."
            )

        # Tier 3: Exact substring match (case-insensitive)
        videos = self._repo.list_all()
        q = query.lower()
        matches = [v for v in videos if q in v.title.lower() or q in v.channel.lower()]

        if len(matches) == 1:
            return self._repo.get(matches[0].video_id)
        if len(matches) > 1:
            raise AmbiguousVideoError(
                f"Multiple videos match '{query}':\n"
                + "\n".join(f"  {i+1}. {v.title}" for i, v in enumerate(matches))
            )

        # Tier 4: LLM resolution — placeholder for BYOK integration
        # TODO: When LiteLLM is wired, attempt LLM-based matching here

        raise VideoNotFoundError(f"No video matching: {query}")
