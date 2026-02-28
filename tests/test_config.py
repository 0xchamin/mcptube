# tests/test_config.py
"""Tests for mcptube configuration."""

from pathlib import Path
from unittest.mock import patch

from mcptube.config import Settings


class TestSettings:
    def test_default_settings(self):
        s = Settings()
        assert s.host == "127.0.0.1"
        assert s.port == 9093
        assert s.data_dir == Path.home() / ".mcptube"

    def test_db_path_derived(self):
        s = Settings()
        assert s.db_path == s.data_dir / "mcptube.db"

    def test_frames_dir_default(self):
        s = Settings()
        assert s.frames_dir == s.data_dir / "frames"

    def test_frames_dir_override(self):
        s = Settings(frames_dir=Path("/tmp/custom_frames"))
        assert s.frames_dir == Path("/tmp/custom_frames")

    def test_ensure_dirs_creates(self, tmp_path):
        s = Settings(data_dir=tmp_path / "testdata")
        s.ensure_dirs()
        assert s.data_dir.exists()
        assert s.frames_dir.exists()

    def test_env_override(self):
        with patch.dict("os.environ", {"MCPTUBE_PORT": "1234"}):
            s = Settings()
            assert s.port == 1234
