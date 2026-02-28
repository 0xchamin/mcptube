"""Configuration management for mcptube."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable overrides.

    All settings can be overridden via environment variables
    prefixed with MCPTUBE_ (e.g. MCPTUBE_DATA_DIR, MCPTUBE_HOST).
    """

    model_config = {"env_prefix": "MCPTUBE_"}

    # Storage
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".mcptube",
        description="Root directory for all mcptube data",
    )

    # Server
    host: str = "127.0.0.1"
    port: int = 9093


    # LLM (BYOK — used in CLI mode, wired up later)
    default_model: str = "gpt-4o"

    @property
    def db_path(self) -> Path:
        """SQLite database path."""
        return self.data_dir / "mcptube.db"

    @property
    def frames_dir(self) -> Path:
        """Directory for cached extracted frames."""
        return self.data_dir / "frames"

    def ensure_dirs(self) -> None:
        """Create all required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir.mkdir(parents=True, exist_ok=True)


# Module-level singleton — import this throughout the app
settings = Settings()
