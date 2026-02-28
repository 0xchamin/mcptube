"""FastMCP server — thin wrapper exposing McpTubeService as MCP tools."""

# import base64

from fastmcp import FastMCP
from fastmcp.utilities.types import Image


from mcptube.config import settings
from mcptube.ingestion.frames import FrameExtractionError
from mcptube.ingestion.youtube import YouTubeExtractor
from mcptube.models import Video
from mcptube.service import McpTubeService, VideoAlreadyExistsError, VideoNotFoundError
from mcptube.storage.sqlite import SQLiteVideoRepository
from mcptube.storage.vectorstore import ChromaVectorStore


mcp = FastMCP(
    name="mcptube",
    instructions=(
        "mcptube makes YouTube videos searchable and queryable. "
        "Use add_video to ingest a YouTube URL, then list_videos, "
        "get_info, search, and get_frame to explore the library."
    ),
)

_service: McpTubeService | None = None


def _get_service() -> McpTubeService:
    """Lazy-initialise the service singleton with default dependencies."""
    global _service
    if _service is None:
        settings.ensure_dirs()
        _service = McpTubeService(
            repository=SQLiteVideoRepository(),
            extractor=YouTubeExtractor(),
            vectorstore=ChromaVectorStore(),
        )
    return _service


@mcp.tool(annotations={"readOnlyHint": False, "idempotentHint": False})
def add_video(url: str) -> dict:
    """Ingest a YouTube video into the mcptube library.

    Extracts metadata and transcript, indexes the video for future queries.

    Args:
        url: YouTube video URL (supports youtube.com/watch, youtu.be, /embed/).
    """
    try:
        video = _get_service().add_video(url)
        return _video_summary(video)
    except VideoAlreadyExistsError as e:
        return {"error": str(e)}


@mcp.tool(annotations={"readOnlyHint": True})
def list_videos() -> list[dict]:
    """List all videos in the mcptube library.

    Returns metadata for each video (title, channel, duration, tags).
    Transcripts are not included — use get_info for full details.
    """
    videos = _get_service().list_videos()
    return [_video_summary(v) for v in videos]


@mcp.tool(annotations={"readOnlyHint": True})
def get_info(video_id: str) -> dict:
    """Get full details for a video including transcript and chapters.

    Args:
        video_id: The YouTube video ID (11-character string).
    """
    try:
        video = _get_service().get_info(video_id)
        return video.model_dump(mode="json")
    except VideoNotFoundError as e:
        return {"error": str(e)}


@mcp.tool(annotations={"readOnlyHint": True})
def search(query: str, video_id: str | None = None, limit: int = 10) -> list[dict]:
    """Semantic search within a single video's transcript.

    Args:
        query: Natural language search query.
        video_id: YouTube video ID to search within. If omitted, searches all videos.
        limit: Maximum number of results (default 10).
    """
    results = _get_service().search(query, video_id=video_id, limit=limit)
    return [
        {
            "video_id": r.video_id,
            "text": r.text,
            "start": r.start,
            "end": r.end,
            "score": r.score,
        }
        for r in results
    ]


@mcp.tool(annotations={"readOnlyHint": True})
def search_library(query: str, tags: list[str] | None = None, limit: int = 10) -> list[dict]:
    """Semantic search across all videos in the library.

    Args:
        query: Natural language search query.
        tags: Optional list of tags to filter by (e.g. ["AI", "LLM"]).
        limit: Maximum number of results (default 10).
    """
    results = _get_service().search(query, tags=tags, limit=limit)
    return [
        {
            "video_id": r.video_id,
            "text": r.text,
            "start": r.start,
            "end": r.end,
            "score": r.score,
        }
        for r in results
    ]


# @mcp.tool(annotations={"readOnlyHint": True})
# def get_frame(video_id: str, timestamp: float) -> dict:
#     """Extract a frame from a video at a specific timestamp.

#     Args:
#         video_id: YouTube video ID.
#         timestamp: Time in seconds to extract the frame at.
#     """
#     try:
#         path = _get_service().get_frame(video_id, timestamp)
#         return {
#             "video_id": video_id,
#             "timestamp": timestamp,
#             "path": str(path),
#             "image_base64": _encode_frame(path),
#         }
#     except (VideoNotFoundError, FrameExtractionError) as e:
#         return {"error": str(e)}


# @mcp.tool(annotations={"readOnlyHint": True})
# def get_frame_by_query(video_id: str, query: str) -> dict:
#     """Search a video's transcript and extract a frame at the best matching moment.

#     Combines semantic search with frame extraction in a single call.
#     Useful for requests like "show me the slide about attention mechanisms".

#     Args:
#         video_id: YouTube video ID.
#         query: Natural language description of the moment to capture.
#     """
#     try:
#         result = _get_service().get_frame_by_query(video_id, query)
#         return {
#             "video_id": video_id,
#             "query": query,
#             "text": result["text"],
#             "start": result["start"],
#             "end": result["end"],
#             "score": result["score"],
#             "path": str(result["path"]),
#             "image_base64": _encode_frame(result["path"]),
#         }
#     except (VideoNotFoundError, FrameExtractionError, RuntimeError) as e:
#         return {"error": str(e)}
@mcp.tool(annotations={"readOnlyHint": True})
def get_frame(video_id: str, timestamp: float) -> Image:
    """Extract a frame from a video at a specific timestamp.

    Returns the frame as an image rendered inline in chat.

    Args:
        video_id: YouTube video ID.
        timestamp: Time in seconds to extract the frame at.
    """
    path = _get_service().get_frame(video_id, timestamp)
    return Image(path=str(path), format="image/jpeg")


@mcp.tool(annotations={"readOnlyHint": True})
def get_frame_by_query(video_id: str, query: str) -> Image:
    """Search a video's transcript and extract a frame at the best matching moment.

    Combines semantic search with frame extraction in a single call.

    Args:
        video_id: YouTube video ID.
        query: Natural language description of the moment to capture.
    """
    result = _get_service().get_frame_by_query(video_id, query)
    #return Image(path=str(result["path"]))
    #return Image(path=str(path), format="image/jpeg")
    return Image(path=str(result["path"]), format="image/jpeg")


@mcp.tool(annotations={"readOnlyHint": True})
def get_frame_data(video_id: str, timestamp: float) -> dict:
    """Extract a frame and return as base64 for embedding in reports.

    Args:
        video_id: YouTube video ID.
        timestamp: Time in seconds.
    """
    path = _get_service().get_frame(video_id, timestamp)
    import base64
    b64 = base64.b64encode(path.read_bytes()).decode()
    return {
        "video_id": video_id,
        "timestamp": timestamp,
        "image_base64": b64,
        "mime_type": "image/jpeg",
        "embed_html": f'<img src="data:image/jpeg;base64,{b64}" alt="Frame at {timestamp}s">',
    }


@mcp.tool(annotations={"destructiveHint": True})
def remove_video(video_id: str) -> dict:
    """Remove a video from the mcptube library.

    Args:
        video_id: The YouTube video ID to remove.
    """
    try:
        _get_service().remove_video(video_id)
        return {"status": "removed", "video_id": video_id}
    except VideoNotFoundError as e:
        return {"error": str(e)}


@mcp.tool(annotations={"readOnlyHint": True})
def classify_video(video_id: str) -> dict:
    """Get or regenerate classification tags for a video.

    In MCP mode, this returns the video metadata so the connected
    AI client can classify it directly (passthrough pattern).

    Args:
        video_id: The YouTube video ID.
    """
    try:
        video = _get_service().get_info(video_id)
        return {
            "video_id": video.video_id,
            "title": video.title,
            "channel": video.channel,
            "description": video.description[:500],
            "current_tags": video.tags,
        }
    except VideoNotFoundError as e:
        return {"error": str(e)}

@mcp.tool(annotations={"readOnlyHint": True})
def generate_report(video_id: str, query: str | None = None) -> dict:
    """Get all data needed to generate an illustrated report for a video.

    Returns transcript, metadata, chapters, and tags. Use get_frame
    or get_frame_by_query to extract illustrations for key moments.

    Args:
        video_id: YouTube video ID.
        query: Optional focus query to guide the report.
    """
    try:
        video = _get_service().get_info(video_id)
        return {
            "video_id": video.video_id,
            "title": video.title,
            "channel": video.channel,
            "duration": video.duration,
            "tags": video.tags,
            "chapters": [ch.model_dump() for ch in video.chapters],
            "transcript": [
                {"start": s.start, "end": s.end, "text": s.text}
                for s in video.transcript
            ],
            "query": query,
            "instructions": (
            "Use this data to generate a comprehensive illustrated report. "
            "Call get_frame_data for key visual moments — it returns embed_html "
            "you can paste directly into the report."
            ),
        }
    except VideoNotFoundError as e:
        return {"error": str(e)}


@mcp.tool(annotations={"readOnlyHint": True})
def generate_report_from_query(query: str, tags: list[str] | None = None) -> dict:
    """Search the library and return data for a cross-video report.

    Returns matching videos with transcripts. Use get_frame or
    get_frame_by_query to extract illustrations from key moments.

    Args:
        query: Topic or question to build the report around.
        tags: Optional tag filter (e.g. ["AI", "LLM"]).
    """
    try:
        svc = _get_service()
        results = svc.search(query, tags=tags, limit=20)
        if not results:
            return {"error": f"No matching content for: {query}"}

        video_ids = list(dict.fromkeys(r.video_id for r in results))
        videos = []
        for vid in video_ids:
            video = svc.get_info(vid)
            videos.append({
                "video_id": video.video_id,
                "title": video.title,
                "channel": video.channel,
                "tags": video.tags,
                "chapters": [ch.model_dump() for ch in video.chapters],
                "transcript": [
                    {"start": s.start, "end": s.end, "text": s.text}
                    for s in video.transcript
                ],
            })

        return {
            "query": query,
            "videos": videos,
            "instructions": (
                "Use this data to generate a comprehensive illustrated report. "
                "Call get_frame_data for key visual moments — it returns embed_html "
                "you can paste directly into the report."
            ),

        }
    except VideoNotFoundError as e:
        return {"error": str(e)}


@mcp.tool(annotations={"readOnlyHint": True})
def discover_videos(topic: str) -> dict:
    """Search YouTube for videos on a topic.

    Returns raw search results. Use add_video to ingest any
    interesting results into the library.

    Args:
        topic: Topic to search for (e.g. "transformer architecture").
    """
    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch15:{topic}", download=False)
            if not info or "entries" not in info:
                return {"topic": topic, "results": []}

            results = []
            for entry in info.get("entries", []):
                if not entry or not entry.get("id"):
                    continue
                results.append({
                    "video_id": entry.get("id", ""),
                    "title": entry.get("title", ""),
                    "channel": entry.get("channel", "") or entry.get("uploader", ""),
                    "duration": float(entry.get("duration") or 0),
                    "url": f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                })

        return {
            "topic": topic,
            "results": results,
            "instructions": (
                "Present these results to the user. They can ask to add any "
                "video to their library using add_video."
            ),
        }
    except yt_dlp.utils.DownloadError as e:
        return {"error": f"YouTube search failed: {e}"}


@mcp.tool(annotations={"readOnlyHint": True})
def synthesize(video_ids: list[str], topic: str) -> dict:
    """Get data for cross-video synthesis on a topic.

    Returns transcripts and metadata for the specified videos.
    Use get_frame or get_frame_by_query for illustrations.

    Args:
        video_ids: List of YouTube video IDs to synthesize.
        topic: Focus topic for cross-video synthesis.
    """
    try:
        svc = _get_service()
        videos = []
        for vid in video_ids:
            video = svc.get_info(vid)
            videos.append({
                "video_id": video.video_id,
                "title": video.title,
                "channel": video.channel,
                "tags": video.tags,
                "chapters": [ch.model_dump() for ch in video.chapters],
                "transcript": [
                    {"start": s.start, "end": s.end, "text": s.text}
                    for s in video.transcript
                ],
            })

        return {
            "topic": topic,
            "videos": videos,
            "instructions": (
                "Use this data to generate a comprehensive illustrated report. "
                "Call get_frame_data for key visual moments — it returns embed_html "
                "you can paste directly into the report."
            ),
        }
    except VideoNotFoundError as e:
        return {"error": str(e)}

def _video_summary(video: Video) -> dict:
    """Create a concise summary dict for tool responses (excludes transcript)."""
    return {
        "video_id": video.video_id,
        "title": video.title,
        "channel": video.channel,
        "duration": video.duration,
        "url": video.url,
        "tags": video.tags,
        "chapters": [ch.model_dump() for ch in video.chapters],
        "added_at": video.added_at.isoformat() if video.added_at else None,
    }


# def _encode_frame(path) -> str:
#     """Encode a frame as base64 for inline display in MCP clients."""
#     with open(path, "rb") as f:
#         return base64.b64encode(f.read()).decode("utf-8")
