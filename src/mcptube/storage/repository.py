"""Abstract repository interface for video storage."""

from abc import ABC, abstractmethod

from mcptube.models import Video


class VideoRepository(ABC):
    """Abstract base class defining the video storage contract.

    All concrete storage implementations (SQLite, PostgreSQL, etc.)
    must implement this interface. This ensures the service layer
    depends on abstractions, not concrete implementations (DIP).
    """

    @abstractmethod
    def save(self, video: Video) -> None:
        """Persist a video to storage. Upserts if video_id already exists."""

    @abstractmethod
    def get(self, video_id: str) -> Video | None:
        """Retrieve a video by ID, including full transcript. Returns None if not found."""

    @abstractmethod
    def list_all(self) -> list[Video]:
        """List all videos in the library.

        Returns metadata only — transcript and chapters are excluded
        for efficiency. Use get() to load full video data.
        """

    @abstractmethod
    def delete(self, video_id: str) -> None:
        """Remove a video from storage. No-op if video_id does not exist."""

    @abstractmethod
    def exists(self, video_id: str) -> bool:
        """Check whether a video with the given ID is in storage."""
