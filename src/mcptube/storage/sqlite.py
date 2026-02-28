"""SQLite implementation of the video repository."""

import json
import sqlite3

from mcptube.config import settings
from mcptube.models import Chapter, TranscriptSegment, Video
from mcptube.storage.repository import VideoRepository


class SQLiteVideoRepository(VideoRepository):
    """SQLite-backed video storage.

    Implements VideoRepository interface using stdlib sqlite3.
    JSON columns for transcript, chapters, and tags keep the schema
    simple while ChromaDB handles searchable vector storage separately.
    """

    _CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS videos (
            video_id      TEXT PRIMARY KEY,
            title         TEXT NOT NULL,
            description   TEXT DEFAULT '',
            channel       TEXT DEFAULT '',
            duration      REAL DEFAULT 0.0,
            thumbnail_url TEXT DEFAULT '',
            chapters      TEXT DEFAULT '[]',
            transcript    TEXT DEFAULT '[]',
            tags          TEXT DEFAULT '[]',
            added_at      TEXT NOT NULL
        )
    """

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize the repository.

        Args:
            db_path: Path to SQLite database file. Defaults to settings.db_path.
                     Use ":memory:" for testing.
        """
        self._db_path = db_path or str(settings.db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        self._conn.execute(self._CREATE_TABLE)
        self._conn.commit()

    def save(self, video: Video) -> None:
        """Persist a video to storage. Upserts if video_id already exists."""
        sql = """
            INSERT INTO videos (
                video_id, title, description, channel, duration,
                thumbnail_url, chapters, transcript, tags, added_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                channel = excluded.channel,
                duration = excluded.duration,
                thumbnail_url = excluded.thumbnail_url,
                chapters = excluded.chapters,
                transcript = excluded.transcript,
                tags = excluded.tags
        """
        self._conn.execute(sql, (
            video.video_id,
            video.title,
            video.description,
            video.channel,
            video.duration,
            video.thumbnail_url,
            json.dumps([ch.model_dump() for ch in video.chapters]),
            json.dumps([seg.model_dump() for seg in video.transcript]),
            json.dumps(video.tags),
            video.added_at.isoformat(),
        ))
        self._conn.commit()

    def get(self, video_id: str) -> Video | None:
        """Retrieve a video by ID with full transcript. Returns None if not found."""
        sql = "SELECT * FROM videos WHERE video_id = ?"
        row = self._conn.execute(sql, (video_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_video(row, include_transcript=True)

    def list_all(self) -> list[Video]:
        """List all videos — metadata only, no transcript or chapters for efficiency."""
        sql = "SELECT * FROM videos ORDER BY added_at DESC"
        rows = self._conn.execute(sql).fetchall()
        return [self._row_to_video(row, include_transcript=False) for row in rows]

    def delete(self, video_id: str) -> None:
        """Remove a video from storage. No-op if video_id does not exist."""
        sql = "DELETE FROM videos WHERE video_id = ?"
        self._conn.execute(sql, (video_id,))
        self._conn.commit()

    def exists(self, video_id: str) -> bool:
        """Check whether a video with the given ID is in storage."""
        sql = "SELECT 1 FROM videos WHERE video_id = ? LIMIT 1"
        return self._conn.execute(sql, (video_id,)).fetchone() is not None

    @staticmethod
    def _row_to_video(row: sqlite3.Row, *, include_transcript: bool) -> Video:
        """Convert a database row to a Video model.

        Args:
            row: SQLite row with all video columns.
            include_transcript: If False, transcript and chapters are
                                left empty to avoid unnecessary deserialization.
        """
        chapters = []
        transcript = []

        if include_transcript:
            chapters = [Chapter(**ch) for ch in json.loads(row["chapters"])]
            transcript = [TranscriptSegment(**seg) for seg in json.loads(row["transcript"])]

        return Video(
            video_id=row["video_id"],
            title=row["title"],
            description=row["description"],
            channel=row["channel"],
            duration=row["duration"],
            thumbnail_url=row["thumbnail_url"],
            chapters=chapters,
            transcript=transcript,
            tags=json.loads(row["tags"]),
            added_at=row["added_at"],
        )
