"""Video discovery — search YouTube by topic, filter, and cluster results."""

import logging
from dataclasses import dataclass, field

import yt_dlp

from mcptube.llm import LLMClient, LLMError

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredVideo:
    """A video found via YouTube search."""

    video_id: str
    title: str
    channel: str
    duration: float
    description: str = ""
    thumbnail_url: str = ""
    cluster: str = ""  # assigned by LLM (e.g. "Explainer", "Debate")

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


@dataclass
class DiscoveryResult:
    """Clustered discovery results for a topic."""

    topic: str
    total_found: int
    clusters: dict[str, list[DiscoveredVideo]] = field(default_factory=dict)


class VideoDiscovery:
    """Searches YouTube by topic, filters, and clusters results via LLM.

    Uses yt-dlp for YouTube search (no API key needed) and LLM
    for intelligent filtering and clustering of results.
    """

    _SEARCH_COUNT = 15  # number of results to fetch per query

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def discover(self, topic: str) -> DiscoveryResult:
        """Search YouTube for videos on a topic, filter, and cluster.

        Args:
            topic: Topic to search for.

        Returns:
            DiscoveryResult with clustered videos.

        Raises:
            LLMError: If LLM filtering/clustering fails.
        """
        raw_results = self._search_youtube(topic)
        if not raw_results:
            return DiscoveryResult(topic=topic, total_found=0)

        clustered = self._filter_and_cluster(topic, raw_results)
        clustered.total_found = len(raw_results)
        return clustered

    def _search_youtube(self, topic: str) -> list[DiscoveredVideo]:
        """Search YouTube via yt-dlp and return raw results."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }

        query = f"ytsearch{self._SEARCH_COUNT}:{topic}"
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
                if not info or "entries" not in info:
                    return []

                results = []
                for entry in info["entries"]:
                    if not entry or not entry.get("id"):
                        continue
                    results.append(DiscoveredVideo(
                        video_id=entry.get("id", ""),
                        title=entry.get("title", ""),
                        channel=entry.get("channel", "") or entry.get("uploader", ""),
                        duration=float(entry.get("duration") or 0),
                        description=entry.get("description", "") or "",
                        thumbnail_url=entry.get("thumbnail", "") or "",
                    ))
                return results

        except yt_dlp.utils.DownloadError as e:
            logger.warning("YouTube search failed: %s", e)
            return []

    def _filter_and_cluster(
        self, topic: str, videos: list[DiscoveredVideo]
    ) -> DiscoveryResult:
        """Use LLM to filter irrelevant results and cluster the rest."""
        import json

        video_list = "\n".join(
            f"- id={v.video_id} | title={v.title} | channel={v.channel} | "
            f"duration={v.duration:.0f}s | desc={v.description[:150]}"
            for v in videos
        )

        prompt = f"""You are a video curator. Given YouTube search results for the topic "{topic}",
filter out irrelevant videos and cluster the relevant ones into categories.

SEARCH RESULTS:
{video_list}

Return ONLY valid JSON:
{{
    "clusters": {{
        "Category Name": ["video_id_1", "video_id_2"],
        "Another Category": ["video_id_3"]
    }}
}}

Guidelines:
- Remove clearly irrelevant results
- Create 2-5 meaningful clusters (e.g. "Tutorials", "Conference Talks", "Debates", "Explainers")
- Each video should appear in exactly one cluster
- Cluster names should be descriptive and useful
- No markdown, no explanation"""

        raw = self._llm._complete(prompt, max_tokens=2048)

        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse cluster JSON: {e}\nResponse: {raw[:200]}")

        # Build lookup of videos by ID
        by_id = {v.video_id: v for v in videos}

        result = DiscoveryResult(topic=topic, total_found=len(videos))
        for cluster_name, video_ids in data.get("clusters", {}).items():
            cluster_videos = []
            for vid in video_ids:
                if vid in by_id:
                    by_id[vid].cluster = cluster_name
                    cluster_videos.append(by_id[vid])
            if cluster_videos:
                result.clusters[cluster_name] = cluster_videos

        return result
