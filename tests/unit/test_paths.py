"""Unit tests for path utilities."""

from datetime import datetime
from pathlib import Path

import pytest

from orca_backup.utils.paths import ensure_directory, get_backup_name, get_default_backup_dir


class TestEnsureDirectory:
    """Tests for ensure_directory function."""

    def test_creates_new_directory(self, tmp_path):
        """Test that ensure_directory creates a new directory."""
        new_dir = tmp_path / "test_dir"
        assert not new_dir.exists()

        result = ensure_directory(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()
        assert result == new_dir

    def test_handles_existing_directory(self, tmp_path):
        """Test that ensure_directory handles existing directory."""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()

        result = ensure_directory(existing_dir)

        assert existing_dir.exists()
        assert result == existing_dir

    def test_creates_parent_directories(self, tmp_path):
        """Test that ensure_directory creates parent directories."""
        nested_dir = tmp_path / "parent" / "child" / "grandchild"
        assert not nested_dir.exists()
        assert not nested_dir.parent.exists()

        result = ensure_directory(nested_dir)

        assert nested_dir.exists()
        assert nested_dir.parent.exists()
        assert result == nested_dir

    def test_returns_path_object(self, tmp_path):
        """Test that ensure_directory returns a Path object."""
        new_dir = tmp_path / "test"
        result = ensure_directory(new_dir)

        assert isinstance(result, Path)


class TestGetBackupName:
    """Tests for get_backup_name function."""

    def test_default_compressed(self):
        """Test default backup name with compression."""
        timestamp = datetime(2025, 11, 14, 15, 30, 45)
        name = get_backup_name("orcaslicer", timestamp, compressed=True)

        assert name == "Orcaslicer_backup_2025-11-14_15-30-45.zip"

    def test_uncompressed(self):
        """Test backup name without compression."""
        timestamp = datetime(2025, 11, 14, 15, 30, 45)
        name = get_backup_name("orcaslicer", timestamp, compressed=False)

        assert name == "Orcaslicer_backup_2025-11-14_15-30-45"

    def test_orca_flashforge_name(self):
        """Test backup name for Orca-Flashforge."""
        timestamp = datetime(2025, 11, 14, 15, 30, 45)
        name = get_backup_name("orca-flashforge", timestamp, compressed=True)

        assert name == "Orca_Flashforge_backup_2025-11-14_15-30-45.zip"

    def test_timestamp_format(self):
        """Test timestamp formatting."""
        timestamp = datetime(2025, 1, 5, 9, 5, 3)
        name = get_backup_name("orcaslicer", timestamp)

        # Should have zero-padded values
        assert "2025-01-05_09-05-03" in name

    def test_no_timestamp_uses_now(self):
        """Test that None timestamp uses current time."""
        name = get_backup_name("orcaslicer", timestamp=None)

        # Should contain a timestamp in the correct format
        assert "_backup_" in name
        assert name.endswith(".zip")
        # Basic format check (YYYY-MM-DD_HH-MM-SS)
        parts = name.split("_backup_")
        assert len(parts) == 2
        timestamp_part = parts[1].replace(".zip", "")
        assert len(timestamp_part) == 19  # YYYY-MM-DD_HH-MM-SS

    def test_title_case_formatting(self):
        """Test that slicer name is title-cased."""
        timestamp = datetime(2025, 11, 14, 12, 0, 0)

        # lowercase input
        name1 = get_backup_name("orcaslicer", timestamp)
        assert name1.startswith("Orcaslicer_")

        # mixed case input
        name2 = get_backup_name("OrCaSlIcEr", timestamp)
        assert name2.startswith("Orcaslicer_")

    def test_hyphen_to_underscore(self):
        """Test that hyphens are replaced with underscores."""
        timestamp = datetime(2025, 11, 14, 12, 0, 0)
        name = get_backup_name("orca-flashforge", timestamp)

        # Should replace hyphen with underscore
        assert "Orca_Flashforge_" in name
        # Should not contain hyphens except in timestamp
        name_part = name.split("_backup_")[0]
        assert "-" not in name_part


class TestGetDefaultBackupDir:
    """Tests for get_default_backup_dir function."""

    def test_returns_path_object(self):
        """Test that get_default_backup_dir returns a Path object."""
        result = get_default_backup_dir()
        assert isinstance(result, Path)

    def test_default_directory_name(self):
        """Test that default directory is OrcaBackups in home."""
        result = get_default_backup_dir()
        expected = Path.home() / "OrcaBackups"

        assert result == expected

    def test_in_home_directory(self):
        """Test that default backup dir is in user's home."""
        result = get_default_backup_dir()
        home = Path.home()

        assert result.parent == home
        assert result.name == "OrcaBackups"
