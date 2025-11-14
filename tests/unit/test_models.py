"""Unit tests for Pydantic models."""

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from orca_backup.models.backup import BackupInfo, BackupManifest, FileEntry
from orca_backup.models.slicer import SlicerInfo, SlicerType


class TestSlicerType:
    """Tests for SlicerType enum."""

    def test_valid_values(self):
        """Test valid slicer type values."""
        assert SlicerType.ORCASLICER.value == "orcaslicer"
        assert SlicerType.ORCA_FLASHFORGE.value == "orca-flashforge"

    def test_from_string(self):
        """Test creating SlicerType from string."""
        assert SlicerType("orcaslicer") == SlicerType.ORCASLICER
        assert SlicerType("orca-flashforge") == SlicerType.ORCA_FLASHFORGE

    def test_invalid_value(self):
        """Test invalid slicer type raises ValueError."""
        with pytest.raises(ValueError):
            SlicerType("invalid-slicer")


class TestSlicerInfo:
    """Tests for SlicerInfo model."""

    def test_valid_slicer_info(self, tmp_path):
        """Test creating valid SlicerInfo."""
        config_path = tmp_path / "OrcaSlicer"
        config_path.mkdir()
        conf_file = config_path / "OrcaSlicer.conf"
        conf_file.write_text("{}")
        user_dir = config_path / "user"
        user_dir.mkdir()

        slicer = SlicerInfo(
            name=SlicerType.ORCASLICER,
            display_name="OrcaSlicer",
            config_path=config_path,
            exists=True,
            version="2.1.0-beta",
            conf_file=conf_file,
            user_dir=user_dir,
        )

        assert slicer.name == "orcaslicer"  # use_enum_values=True
        assert slicer.display_name == "OrcaSlicer"
        assert slicer.config_path == config_path
        assert slicer.exists is True
        assert slicer.version == "2.1.0-beta"
        assert slicer.conf_file == conf_file
        assert slicer.user_dir == user_dir

    def test_use_enum_values(self, tmp_path):
        """Test that name uses enum values (string, not enum)."""
        slicer = SlicerInfo(
            name=SlicerType.ORCASLICER,
            display_name="OrcaSlicer",
            config_path=tmp_path,
            exists=True,
        )

        # Should be a string, not an enum
        assert isinstance(slicer.name, str)
        assert slicer.name == "orcaslicer"

    def test_optional_fields(self, tmp_path):
        """Test optional fields can be None."""
        slicer = SlicerInfo(
            name=SlicerType.ORCASLICER,
            display_name="OrcaSlicer",
            config_path=tmp_path,
            exists=False,
            version=None,
            conf_file=None,
            user_dir=None,
            custom_scripts_dir=None,
        )

        assert slicer.version is None
        assert slicer.conf_file is None
        assert slicer.user_dir is None
        assert slicer.custom_scripts_dir is None

    def test_is_valid_complete_installation(self, tmp_path):
        """Test is_valid() returns True for complete installation."""
        config_path = tmp_path / "OrcaSlicer"
        config_path.mkdir()
        conf_file = config_path / "OrcaSlicer.conf"
        conf_file.write_text("{}")
        user_dir = config_path / "user"
        user_dir.mkdir()

        slicer = SlicerInfo(
            name=SlicerType.ORCASLICER,
            display_name="OrcaSlicer",
            config_path=config_path,
            exists=True,
            conf_file=conf_file,
            user_dir=user_dir,
        )

        assert slicer.is_valid() is True

    def test_is_valid_not_exists(self, tmp_path):
        """Test is_valid() returns False if not exists."""
        slicer = SlicerInfo(
            name=SlicerType.ORCASLICER,
            display_name="OrcaSlicer",
            config_path=tmp_path,
            exists=False,
        )

        assert slicer.is_valid() is False

    def test_is_valid_missing_conf_file(self, tmp_path):
        """Test is_valid() returns False if conf_file is None."""
        user_dir = tmp_path / "user"
        user_dir.mkdir()

        slicer = SlicerInfo(
            name=SlicerType.ORCASLICER,
            display_name="OrcaSlicer",
            config_path=tmp_path,
            exists=True,
            conf_file=None,
            user_dir=user_dir,
        )

        assert slicer.is_valid() is False

    def test_is_valid_conf_file_not_exists(self, tmp_path):
        """Test is_valid() returns False if conf_file doesn't exist."""
        conf_file = tmp_path / "nonexistent.conf"
        user_dir = tmp_path / "user"
        user_dir.mkdir()

        slicer = SlicerInfo(
            name=SlicerType.ORCASLICER,
            display_name="OrcaSlicer",
            config_path=tmp_path,
            exists=True,
            conf_file=conf_file,
            user_dir=user_dir,
        )

        assert slicer.is_valid() is False

    def test_is_valid_missing_user_dir(self, tmp_path):
        """Test is_valid() returns False if user_dir is None."""
        conf_file = tmp_path / "OrcaSlicer.conf"
        conf_file.write_text("{}")

        slicer = SlicerInfo(
            name=SlicerType.ORCASLICER,
            display_name="OrcaSlicer",
            config_path=tmp_path,
            exists=True,
            conf_file=conf_file,
            user_dir=None,
        )

        assert slicer.is_valid() is False

    def test_is_valid_user_dir_not_exists(self, tmp_path):
        """Test is_valid() returns False if user_dir doesn't exist."""
        conf_file = tmp_path / "OrcaSlicer.conf"
        conf_file.write_text("{}")
        user_dir = tmp_path / "nonexistent"

        slicer = SlicerInfo(
            name=SlicerType.ORCASLICER,
            display_name="OrcaSlicer",
            config_path=tmp_path,
            exists=True,
            conf_file=conf_file,
            user_dir=user_dir,
        )

        assert slicer.is_valid() is False


class TestFileEntry:
    """Tests for FileEntry model."""

    def test_valid_file_entry(self):
        """Test creating valid FileEntry."""
        entry = FileEntry(
            path="user/filament/custom.json",
            size=1024,
            sha256="a" * 64,
        )

        assert entry.path == "user/filament/custom.json"
        assert entry.size == 1024
        assert entry.sha256 == "a" * 64

    def test_required_fields(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError):
            FileEntry(path="test.txt", size=100)  # Missing sha256

        with pytest.raises(ValidationError):
            FileEntry(path="test.txt", sha256="a" * 64)  # Missing size

        with pytest.raises(ValidationError):
            FileEntry(size=100, sha256="a" * 64)  # Missing path

    def test_invalid_checksum_length(self):
        """Test that invalid checksum length is accepted (no validation)."""
        # Pydantic doesn't validate SHA256 format by default
        entry = FileEntry(path="test.txt", size=100, sha256="short")
        assert entry.sha256 == "short"


class TestBackupManifest:
    """Tests for BackupManifest model."""

    def test_valid_manifest(self, sample_file_entries):
        """Test creating valid BackupManifest."""
        manifest = BackupManifest(
            version="1.0",
            created_at=datetime(2025, 11, 14, 12, 0, 0),
            slicer="orcaslicer",
            slicer_version="2.1.0-beta",
            platform="linux",
            files=sample_file_entries,
            total_files=3,
            total_size=1792,
            compressed=True,
        )

        assert manifest.version == "1.0"
        assert manifest.slicer == "orcaslicer"
        assert manifest.slicer_version == "2.1.0-beta"
        assert manifest.platform == "linux"
        assert len(manifest.files) == 3
        assert manifest.total_files == 3
        assert manifest.total_size == 1792
        assert manifest.compressed is True

    def test_default_values(self, sample_file_entries):
        """Test default values for optional fields."""
        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            total_files=0,
            total_size=0,
        )

        assert manifest.version == "1.0"  # Default
        assert manifest.files == []  # Default empty list
        assert manifest.compressed is True  # Default

    def test_size_mb_property(self):
        """Test size_mb property calculation."""
        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            total_files=1,
            total_size=2097152,  # 2 MB
        )

        assert manifest.size_mb == 2.0

    def test_size_mb_fractional(self):
        """Test size_mb with fractional MB."""
        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            total_files=1,
            total_size=1572864,  # 1.5 MB
        )

        assert manifest.size_mb == 1.5

    def test_datetime_serialization(self, sample_file_entries):
        """Test datetime serialization in model_dump."""
        dt = datetime(2025, 11, 14, 12, 30, 45)
        manifest = BackupManifest(
            created_at=dt,
            slicer="orcaslicer",
            platform="linux",
            files=sample_file_entries,
            total_files=3,
            total_size=1792,
        )

        # Test JSON mode serialization
        data = manifest.model_dump(mode="json")
        assert data["created_at"] == dt.isoformat()

    def test_optional_slicer_version(self):
        """Test optional slicer_version field."""
        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            slicer_version=None,
            platform="linux",
            total_files=0,
            total_size=0,
        )

        assert manifest.slicer_version is None


class TestBackupInfo:
    """Tests for BackupInfo model."""

    def test_valid_backup_info(self, tmp_path, sample_backup_manifest):
        """Test creating valid BackupInfo."""
        backup_path = tmp_path / "backup.zip"
        backup_path.write_text("test")

        info = BackupInfo(
            backup_path=backup_path,
            manifest=sample_backup_manifest,
            is_valid=True,
            size_mb=1.5,
        )

        assert info.backup_path == backup_path
        assert info.manifest == sample_backup_manifest
        assert info.is_valid is True
        assert info.size_mb == 1.5

    def test_invalid_backup(self, tmp_path, sample_backup_manifest):
        """Test BackupInfo with invalid backup."""
        backup_path = tmp_path / "corrupted.zip"

        info = BackupInfo(
            backup_path=backup_path,
            manifest=sample_backup_manifest,
            is_valid=False,
            size_mb=0.0,
        )

        assert info.is_valid is False

    def test_arbitrary_types_allowed(self, tmp_path, sample_backup_manifest):
        """Test that Path objects are allowed."""
        # Should not raise validation error
        info = BackupInfo(
            backup_path=tmp_path / "test.zip",
            manifest=sample_backup_manifest,
            is_valid=True,
            size_mb=1.0,
        )

        assert isinstance(info.backup_path, Path)
