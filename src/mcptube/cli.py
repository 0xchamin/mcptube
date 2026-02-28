"""CLI interface — thin wrapper over McpTubeService and FastMCP server."""

import typer
from pathlib import Path

from mcptube.config import settings
from mcptube.ingestion.frames import FrameExtractionError
from mcptube.ingestion.youtube import ExtractionError
from mcptube.service import (
    AmbiguousVideoError,
    McpTubeService,
    VideoAlreadyExistsError,
    VideoNotFoundError,
)
from mcptube.storage.sqlite import SQLiteVideoRepository
from mcptube.storage.vectorstore import ChromaVectorStore
from mcptube.llm import LLMClient, LLMError


app = typer.Typer(
    name="mcptube",
    help="Convert any YouTube video into an AI-queryable MCP server.",
    no_args_is_help=True,
)


def _get_service() -> McpTubeService:
    """Create a service instance with default dependencies."""
    settings.ensure_dirs()
    return McpTubeService(
        repository=SQLiteVideoRepository(),
        vectorstore=ChromaVectorStore(),
    )


def _resolve_or_exit(svc: McpTubeService, query: str):
    """Resolve a video from human-friendly input or exit with error."""
    try:
        return svc.resolve_video(query)
    except VideoNotFoundError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(code=1)
    except AmbiguousVideoError as e:
        typer.echo(f"⚠️  {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def add(url: str = typer.Argument(..., help="YouTube video URL to ingest.")) -> None:
    """Ingest a YouTube video into the mcptube library."""
    svc = _get_service()
    try:
        video = svc.add_video(url)
        typer.echo(f"✅ Added: {video.title}")
        typer.echo(f"   ID:       {video.video_id}")
        typer.echo(f"   Channel:  {video.channel}")
        typer.echo(f"   Duration: {video.duration:.0f}s")
        typer.echo(f"   Segments: {len(video.transcript)}")
    except VideoAlreadyExistsError as e:
        typer.echo(f"⚠️  {e}", err=True)
        raise typer.Exit(code=1)
    except ExtractionError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(code=1)


@app.command(name="list")
def list_videos() -> None:
    """List all videos in the mcptube library."""
    svc = _get_service()
    videos = svc.list_videos()
    if not videos:
        typer.echo("Library is empty. Use 'mcptube add <url>' to add a video.")
        return
    for i, v in enumerate(videos, 1):
        tags = f" [{', '.join(v.tags)}]" if v.tags else ""
        typer.echo(f"  {i}. {v.video_id}  {v.duration:>6.0f}s  {v.channel:<20s}  {v.title}{tags}")


@app.command()
def info(query: str = typer.Argument(..., help="Video ID, index number, or search text.")) -> None:
    """Show full details for a video."""
    svc = _get_service()
    video = _resolve_or_exit(svc, query)
    typer.echo(f"Title:       {video.title}")
    typer.echo(f"Channel:     {video.channel}")
    typer.echo(f"Duration:    {video.duration:.0f}s")
    typer.echo(f"URL:         {video.url}")
    typer.echo(f"Thumbnail:   {video.thumbnail_url}")
    typer.echo(f"Tags:        {', '.join(video.tags) or '(none)'}")
    typer.echo(f"Chapters:    {len(video.chapters)}")
    typer.echo(f"Segments:    {len(video.transcript)}")
    typer.echo(f"Added:       {video.added_at}")
    if video.chapters:
        typer.echo("\nChapters:")
        for ch in video.chapters:
            typer.echo(f"  [{ch.start:>7.1f}s] {ch.title}")


@app.command()
def remove(query: str = typer.Argument(..., help="Video ID, index number, or search text.")) -> None:
    """Remove a video from the mcptube library."""
    svc = _get_service()
    video = _resolve_or_exit(svc, query)
    svc.remove_video(video.video_id)
    typer.echo(f"🗑️  Removed: {video.title} ({video.video_id})")


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural language search query."),
    video: str | None = typer.Option(None, "--video", "-v", help="Scope to a specific video (ID, index, or text)."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results."),
) -> None:
    """Semantic search across video transcripts."""
    svc = _get_service()

    video_id = None
    if video:
        resolved = _resolve_or_exit(svc, video)
        video_id = resolved.video_id

    results = svc.search(query, video_id=video_id, limit=limit)
    if not results:
        typer.echo("No results found.")
        return

    for i, r in enumerate(results, 1):
        mins, secs = divmod(int(r.start), 60)
        typer.echo(f"  {i}. [{mins:02d}:{secs:02d}] ({r.video_id}) {r.text}")


@app.command()
def frame(
    query: str = typer.Argument(..., help="Video ID, index number, or search text."),
    timestamp: float = typer.Argument(..., help="Timestamp in seconds to extract frame at."),
) -> None:
    """Extract a frame from a video at a specific timestamp."""
    svc = _get_service()
    video = _resolve_or_exit(svc, query)
    try:
        path = svc.get_frame(video.video_id, timestamp)
        typer.echo(f"🖼️  Frame extracted: {path}")
    except FrameExtractionError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def frame_query(
    query: str = typer.Argument(..., help="Video ID, index number, or search text."),
    search_query: str = typer.Argument(..., help="Natural language description of the moment to capture."),
) -> None:
    """Extract a frame by searching the transcript for the best matching moment."""
    svc = _get_service()
    video = _resolve_or_exit(svc, query)
    try:
        result = svc.get_frame_by_query(video.video_id, search_query)
        mins, secs = divmod(int(result["start"]), 60)
        typer.echo(f"🖼️  Frame extracted: {result['path']}")
        typer.echo(f"   Timestamp: [{mins:02d}:{secs:02d}]")
        typer.echo(f"   Matched:   {result['text']}")
    except (FrameExtractionError, RuntimeError) as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(code=1)

@app.command()
def classify(
    query: str = typer.Argument(..., help="Video ID, index number, or search text."),
) -> None:
    """Classify or re-classify a video using LLM."""
    svc = _get_service()
    video = _resolve_or_exit(svc, query)
    try:
        tags = svc.classify_video(video.video_id)
        typer.echo(f"🏷️  Tags for: {video.title}")
        typer.echo(f"   {', '.join(tags)}")
    except (LLMError, RuntimeError) as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(code=1)

@app.command()
def report(
    query: str = typer.Argument(..., help="Video ID, index number, or search text."),
    focus: str | None = typer.Option(None, "--focus", "-f", help="Focus query to guide the report."),
    fmt: str = typer.Option("markdown", "--format", help="Output format: markdown or html."),
    output: str | None = typer.Option(None, "--output", "-o", help="Save report to file."),
) -> None:
    """Generate an illustrated report for a single video."""
    svc = _get_service()
    video = _resolve_or_exit(svc, query)
    try:
        typer.echo(f"📝 Generating report for: {video.title}...")
        rpt, rendered = svc.generate_report(video.video_id, query=focus, fmt=fmt)
        if output:
            Path(output).write_text(rendered, encoding="utf-8")
            typer.echo(f"✅ Report saved: {output}")
        else:
            typer.echo(rendered)
    except (RuntimeError, Exception) as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def report_query(
    query: str = typer.Argument(..., help="Topic or question for the cross-video report."),
    tags: list[str] | None = typer.Option(None, "--tag", "-t", help="Filter by tag (repeatable)."),
    fmt: str = typer.Option("markdown", "--format", help="Output format: markdown or html."),
    output: str | None = typer.Option(None, "--output", "-o", help="Save report to file."),
) -> None:
    """Generate an illustrated report across matching library videos."""
    svc = _get_service()
    try:
        typer.echo(f"📝 Generating cross-video report for: {query}...")
        rpt, rendered = svc.generate_report_from_query(query, tags=tags, fmt=fmt)
        if output:
            Path(output).write_text(rendered, encoding="utf-8")
            typer.echo(f"✅ Report saved: {output}")
        else:
            typer.echo(rendered)
    except (RuntimeError, Exception) as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(code=1)

@app.command()
def discover(
    topic: str = typer.Argument(..., help="Topic to search YouTube for."),
) -> None:
    """Discover YouTube videos on a topic — filtered and clustered."""
    svc = _get_service()
    try:
        typer.echo(f"🔍 Searching YouTube for: {topic}...")
        result = svc.discover_videos(topic)
        if not result.clusters:
            typer.echo("No relevant videos found.")
            return
        typer.echo(f"Found {result.total_found} results, clustered:\n")
        for cluster_name, videos in result.clusters.items():
            typer.echo(f"  📁 {cluster_name}")
            for v in videos:
                mins, secs = divmod(int(v.duration), 60)
                typer.echo(f"     • {v.title} ({v.channel}, {mins}:{secs:02d})")
                typer.echo(f"       {v.url}")
            typer.echo("")
    except RuntimeError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(code=1)

@app.command()
def synthesize_cmd(
    topic: str = typer.Argument(..., help="Focus topic for cross-video synthesis."),
    videos: list[str] = typer.Option(..., "--video", "-v", help="Video IDs to synthesize (repeatable)."),
    fmt: str = typer.Option("markdown", "--format", help="Output format: markdown or html."),
    output: str | None = typer.Option(None, "--output", "-o", help="Save report to file."),
) -> None:
    """Cross-reference themes across multiple library videos."""
    svc = _get_service()
    try:
        typer.echo(f"🔗 Synthesizing {len(videos)} videos on: {topic}...")
        rpt, rendered = svc.synthesize(videos, topic, fmt=fmt)
        if output:
            Path(output).write_text(rendered, encoding="utf-8")
            typer.echo(f"✅ Synthesis saved: {output}")
        else:
            typer.echo(rendered)
    except (VideoNotFoundError, RuntimeError) as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(code=1)

@app.command()
def serve(
    stdio: bool = typer.Option(False, "--stdio", help="Use stdio transport instead of HTTP."),
    host: str = typer.Option(settings.host, "--host", help="Host to bind to."),
    port: int = typer.Option(settings.port, "--port", help="Port to bind to."),
    reload: bool = typer.Option(False, "--reload", help="Enable hot-reload for development."),
) -> None:
    """Start the mcptube MCP server."""
    from mcptube.server import mcp

    if stdio:
        typer.echo("Starting mcptube MCP server (stdio)...", err=True )
        mcp.run(transport="stdio")
    else:
        typer.echo(f"Starting mcptube MCP server on http://{host}:{port}/mcp")
        mcp.run(transport="streamable-http", host=host, port=port)
