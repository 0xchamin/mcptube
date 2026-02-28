"""Report generation — illustrated reports from video transcripts."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from mcptube.ingestion.frames import FrameExtractionError, FrameExtractor
from mcptube.llm import LLMClient, LLMError
from mcptube.models import Video

logger = logging.getLogger(__name__)


@dataclass
class FrameSelection:
    """A frame selected by the LLM for illustration."""

    video_id: str
    timestamp: float
    reason: str
    path: Path | None = None  # populated after extraction


@dataclass
class ReportSection:
    """A section of the generated report."""

    heading: str
    content: str
    frames: list[FrameSelection] = field(default_factory=list)


@dataclass
class Report:
    """A complete generated report."""

    title: str
    summary: str
    sections: list[ReportSection] = field(default_factory=list)
    key_takeaways: list[str] = field(default_factory=list)


class ReportBuilder:
    """Generates illustrated reports from video transcripts.

    Shared core for both single-video and multi-video reports.
    Uses LLM to analyze transcripts, select key moments for
    illustration, and produce structured content.
    """

    def __init__(
        self,
        llm: LLMClient,
        frame_extractor: FrameExtractor,
    ) -> None:
        self._llm = llm
        self._frames = frame_extractor

    def generate_single(self, video: Video, query: str | None = None) -> Report:
        """Generate an illustrated report for a single video.

        Args:
            video: Full video model with transcript.
            query: Optional focus query to guide the report.

        Returns:
            Complete Report with frames extracted.

        Raises:
            LLMError: If LLM analysis fails.
        """
        transcript_text = self._format_transcript(video)
        metadata = self._format_metadata(video)
        prompt = self._build_single_prompt(metadata, transcript_text, query)

        raw = self._llm._complete(prompt, max_tokens=16000)
        report = self._parse_report(raw, video.video_id)
        self._extract_frames(report)

        return report

    def generate_multi(
        self, videos: list[Video], query: str
    ) -> Report:
        """Generate an illustrated report across multiple videos.

        Args:
            videos: List of full video models with transcripts.
            query: Focus query for the cross-video report.

        Returns:
            Complete Report with frames from multiple videos.

        Raises:
            LLMError: If LLM analysis fails.
        """
        video_blocks = []
        for v in videos:
            transcript_text = self._format_transcript(v)
            metadata = self._format_metadata(v)
            video_blocks.append(
                f"=== VIDEO: {v.video_id} ===\n{metadata}\n\n{transcript_text}"
            )

        combined = "\n\n".join(video_blocks)
        prompt = self._build_multi_prompt(combined, query)
        raw = self._llm._complete(prompt, max_tokens=16000)

        # For multi-video, pass None — video_id comes from LLM response per frame
        report = self._parse_report(raw, default_video_id=None)
        self._extract_frames(report)

        return report

    def to_markdown(self, report: Report) -> str:
        """Render a Report as markdown with embedded frame references."""
        lines = [f"# {report.title}", "", report.summary, ""]

        for section in report.sections:
            lines.append(f"## {section.heading}")
            lines.append("")
            lines.append(section.content)
            lines.append("")
            for frame in section.frames:
                if frame.path and frame.path.exists():
                    lines.append(f"![{frame.reason}]({frame.path})")
                    lines.append(f"*{frame.reason} [{self._fmt_time(frame.timestamp)}]*")
                    lines.append("")

        if report.key_takeaways:
            lines.append("## Key Takeaways")
            lines.append("")
            for t in report.key_takeaways:
                lines.append(f"- {t}")

        return "\n".join(lines)

    def to_html(self, report: Report) -> str:
        """Render a Report as interactive HTML with embedded frames."""
        import base64

        sections_html = []
        for section in report.sections:
            frames_html = ""
            for frame in section.frames:
                if frame.path and frame.path.exists():
                    b64 = base64.b64encode(frame.path.read_bytes()).decode()
                    frames_html += (
                        f'<figure>'
                        f'<img src="data:image/jpeg;base64,{b64}" alt="{frame.reason}">'
                        f'<figcaption>{frame.reason} [{self._fmt_time(frame.timestamp)}]</figcaption>'
                        f'</figure>\n'
                    )
            sections_html.append(
                f"<section><h2>{section.heading}</h2>"
                f"<p>{section.content}</p>{frames_html}</section>"
            )

        takeaways = ""
        if report.key_takeaways:
            items = "".join(f"<li>{t}</li>" for t in report.key_takeaways)
            takeaways = f"<section><h2>Key Takeaways</h2><ul>{items}</ul></section>"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{report.title}</title>
<style>
    body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
    h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
    h2 {{ color: #2c5282; margin-top: 2rem; }}
    figure {{ margin: 1.5rem 0; text-align: center; }}
    img {{ max-width: 100%; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
    figcaption {{ font-size: 0.9rem; color: #666; margin-top: 0.5rem; font-style: italic; }}
    .summary {{ font-size: 1.1rem; color: #444; border-left: 4px solid #2c5282; padding-left: 1rem; margin: 1.5rem 0; }}
    ul {{ padding-left: 1.5rem; }}
    li {{ margin-bottom: 0.5rem; }}
</style>
</head>
<body>
<h1>{report.title}</h1>
<div class="summary">{report.summary}</div>
{"".join(sections_html)}
{takeaways}
</body>
</html>"""

    def _build_single_prompt(
        self, metadata: str, transcript: str, query: str | None
    ) -> str:
        focus = f"\nFocus the report on: {query}" if query else ""
        return f"""You are a report generator. Given a YouTube video transcript and metadata, 
produce a comprehensive illustrated report.{focus}

{metadata}

TRANSCRIPT:
{transcript}

Return ONLY valid JSON with this exact structure:
{{
    "title": "Report title",
    "summary": "2-3 sentence overview",
    "sections": [
        {{
            "heading": "Section heading",
            "content": "Detailed content (multiple paragraphs, in-depth explanation, not raw transcript)",
            "frames": [
                {{"timestamp": 123.5, "reason": "Brief description of what's shown on screen"}}
            ]
        }}
    ],
    "key_takeaways": ["takeaway 1", "takeaway 2"]
}}

Guidelines:
- Create 3-8 sections based on the content structure
- Content should be deep, enriched explanations — NOT raw transcript
- Select frames at moments with visual significance (slides, diagrams, code, demos)
- Each section can have 0, 1, or multiple frames — only where visually meaningful
- Include 3-6 key takeaways
- No markdown in JSON values"""

    def _build_multi_prompt(self, combined: str, query: str) -> str:
        return f"""You are a report generator. Given transcripts from multiple YouTube videos, 
produce a comprehensive illustrated cross-video report focused on: {query}

{combined}

Return ONLY valid JSON with this exact structure:
{{
    "title": "Report title",
    "summary": "2-3 sentence overview synthesizing across videos",
    "sections": [
        {{
            "heading": "Section heading",
            "content": "Synthesized content drawing from multiple videos",
            "frames": [
                {{"video_id": "abc123", "timestamp": 123.5, "reason": "Description of visual"}}
            ]
        }}
    ],
    "key_takeaways": ["takeaway 1", "takeaway 2"]
}}

Guidelines:
- Synthesize themes, agreements, and contradictions across videos
- Create 3-8 sections organized by theme, NOT by video
- Content should be deep analysis — NOT raw transcript
- Select frames from across different videos where visually significant
- Each frame MUST include the video_id it comes from
- Include 3-6 key takeaways
- No markdown in JSON values"""

    def _parse_report(self, raw: str, default_video_id: str | None) -> Report:
        """Parse LLM JSON response into a Report."""
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse report JSON: {e}\nResponse: {raw[:200]}")

        sections = []
        for s in data.get("sections", []):
            frames = []
            for f in s.get("frames", []):
                frames.append(FrameSelection(
                    video_id=f.get("video_id", default_video_id or ""),
                    timestamp=float(f.get("timestamp", 0)),
                    reason=f.get("reason", ""),
                ))
            sections.append(ReportSection(
                heading=s.get("heading", ""),
                content=s.get("content", ""),
                frames=frames,
            ))

        return Report(
            title=data.get("title", "Untitled Report"),
            summary=data.get("summary", ""),
            sections=sections,
            key_takeaways=data.get("key_takeaways", []),
        )

    def _extract_frames(self, report: Report) -> None:
        """Extract all frames selected by the LLM."""
        for section in report.sections:
            for frame in section.frames:
                if not frame.video_id:
                    logger.warning("Frame missing video_id, skipping")
                    continue
                try:
                    frame.path = self._frames.extract_frame(
                        frame.video_id, frame.timestamp
                    )
                except FrameExtractionError as e:
                    logger.warning("Frame extraction failed at %.1fs: %s", frame.timestamp, e)

    @staticmethod
    def _format_transcript(video: Video) -> str:
        """Format transcript segments with timestamps."""
        lines = []
        for seg in video.transcript:
            mins, secs = divmod(int(seg.start), 60)
            lines.append(f"[{mins:02d}:{secs:02d}] {seg.text}")
        return "\n".join(lines)

    @staticmethod
    def _format_metadata(video: Video) -> str:
        """Format video metadata for the LLM prompt."""
        parts = [
            f"Title: {video.title}",
            f"Channel: {video.channel}",
            f"Duration: {video.duration:.0f}s",
        ]
        if video.tags:
            parts.append(f"Tags: {', '.join(video.tags)}")
        if video.chapters:
            ch_list = ", ".join(f"{ch.title} ({ch.start:.0f}s)" for ch in video.chapters)
            parts.append(f"Chapters: {ch_list}")
        return "\n".join(parts)

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        """Format seconds as MM:SS."""
        mins, secs = divmod(int(seconds), 60)
        return f"{mins:02d}:{secs:02d}"
