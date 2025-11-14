"""Unit tests for backup creation."""

import json
import platform
from datetime import datetime
from pathlib import Path

import pytest

from orca_backup.core.backup import (
    calculate_sha256,
    copy_file_with_metadata,
    create_backup,
    create_backup_staging,
    create_manifest,
)
from orca_backup.models.backup import FileEntry
from orca_backup.models.slicer import SlicerInfo, SlicerType


class TestCalculateSha256:
    """Tests for calculate_sha256 function (duplicate from verify)."""

    def test_calculate_checksum(self, tmp_path):
        """Test calculating SHA256 checksum."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        checksum = calculate_sha256(test_file)

        # Known SHA256 for "Hello, World!"
        expected = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        assert checksum == expected

    def test_different_files_different_checksums(self, tmp_path):
        """Test that different files have different checksums."""
        file1 = tmp_path / "file1.txt"
        file1.write_text("content1")

        file2 = tmp_path / "file2.txt"
        file2.write_text("content2")

        checksum1 = calculate_sha256(file1)
        checksum2 = calculate_sha256(file2)

        assert checksum1 != checksum2


class TestCopyFileWithMetadata:
    """Tests for copy_file_with_metadata function."""

    def test_copy_file_and_metadata(self, tmp_path):
        """Test copying file and extracting metadata."""
        # Create source structure
        base_path = tmp_path / "base"
        base_path.mkdir()
        src_file = base_path / "test.txt"
        src_file.write_text("Test content")

        # Create destination
        dst_dir = tmp_path / "dest"
        dst_file = dst_dir / "test.txt"

        entry = copy_file_with_metadata(src_file, dst_file, base_path)

        # Verify file was copied
        assert dst_file.exists()
        assert dst_file.read_text() == "Test content"

        # Verify metadata
        assert entry.path == "test.txt"
        assert entry.size == src_file.stat().st_size
        assert entry.sha256 == calculate_sha256(src_file)

    def test_copy_creates_parent_directories(self, tmp_path):
        """Test that parent directories are created."""
        base_path = tmp_path / "base"
        base_path.mkdir()
        src_file = base_path / "test.txt"
        src_file.write_text("content")

        # Destination with nested path
        dst_dir = tmp_path / "dest"
        dst_file = dst_dir / "nested" / "deep" / "test.txt"

        entry = copy_file_with_metadata(src_file, dst_file, base_path)

        assert dst_file.exists()
        assert dst_file.parent.exists()

    def test_copy_with_nested_source(self, tmp_path):
        """Test copying from nested source path."""
        base_path = tmp_path / "base"
        base_path.mkdir()

        # Create nested source
        nested_dir = base_path / "user" / "filament"
        nested_dir.mkdir(parents=True)
        src_file = nested_dir / "custom.json"
        src_file.write_text('{"temp": 210}')

        dst_dir = tmp_path / "dest"
        dst_file = dst_dir / "user" / "filament" / "custom.json"

        entry = copy_file_with_metadata(src_file, dst_file, base_path)

        # Path should be relative to base_path
        assert entry.path == "user/filament/custom.json"

    def test_copy_preserves_file_metadata(self, tmp_path):
        """Test that file metadata (timestamps) are preserved."""
        base_path = tmp_path / "base"
        base_path.mkdir()
        src_file = base_path / "test.txt"
        src_file.write_text("content")

        dst_dir = tmp_path / "dest"
        dst_file = dst_dir / "test.txt"

        copy_file_with_metadata(src_file, dst_file, base_path)

        # shutil.copy2 should preserve timestamps
        assert dst_file.stat().st_mtime == src_file.stat().st_mtime


class TestCreateBackupStaging:
    """Tests for create_backup_staging function."""

    def test_stage_conf_file(self, sample_slicer_info, tmp_path):
        """Test staging conf file."""
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        entries = create_backup_staging(sample_slicer_info, staging_dir)

        # Verify conf file was copied
        assert (staging_dir / "OrcaSlicer.conf").exists()

        # Verify entry was created
        conf_entries = [e for e in entries if e.path == "OrcaSlicer.conf"]
        assert len(conf_entries) == 1

    def test_stage_user_directory(self, sample_slicer_info, tmp_path):
        """Test staging user directory."""
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        entries = create_backup_staging(sample_slicer_info, staging_dir)

        # Verify user directory was copied
        assert (staging_dir / "user").exists()

        # Verify user files have entries
        user_entries = [e for e in entries if e.path.startswith("user/")]
        assert len(user_entries) > 0

    def test_stage_custom_scripts(self, sample_flashforge_info, tmp_path):
        """Test staging custom_scripts directory."""
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        entries = create_backup_staging(sample_flashforge_info, staging_dir)

        # Verify custom_scripts was copied
        assert (staging_dir / "custom_scripts").exists()

        # Verify custom_scripts entries
        script_entries = [e for e in entries if e.path.startswith("custom_scripts/")]
        assert len(script_entries) > 0

    def test_stage_without_custom_scripts(self, sample_slicer_info, tmp_path):
        """Test staging without custom_scripts directory."""
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        entries = create_backup_staging(sample_slicer_info, staging_dir)

        # Verify custom_scripts was not created
        assert not (staging_dir / "custom_scripts").exists()

    def test_all_entries_have_checksums(self, sample_slicer_info, tmp_path):
        """Test that all file entries have valid checksums."""
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        entries = create_backup_staging(sample_slicer_info, staging_dir)

        for entry in entries:
            assert len(entry.sha256) == 64  # SHA256 is 64 hex chars
            assert entry.size > 0  # Files should have content

    def test_relative_paths(self, sample_slicer_info, tmp_path):
        """Test that all paths are relative."""
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        entries = create_backup_staging(sample_slicer_info, staging_dir)

        for entry in entries:
            # Paths should not start with /
            assert not entry.path.startswith("/")
            # Paths should not be absolute
            assert not Path(entry.path).is_absolute()


class TestCreateManifest:
    """Tests for create_manifest function."""

    def test_create_manifest_basic(self, sample_slicer_info, sample_file_entries):
        """Test creating basic manifest."""
        manifest = create_manifest(sample_slicer_info, sample_file_entries, compressed=True)

        assert manifest.version == "1.0"
        assert manifest.slicer == "orcaslicer"
        assert manifest.slicer_version == "2.1.0-beta"
        assert manifest.platform == platform.system().lower()
        assert manifest.files == sample_file_entries
        assert manifest.total_files == 3
        assert manifest.compressed is True

    def test_create_manifest_total_size(self, sample_slicer_info, sample_file_entries):
        """Test total size calculation."""
        manifest = create_manifest(sample_slicer_info, sample_file_entries, compressed=True)

        expected_size = sum(e.size for e in sample_file_entries)
        assert manifest.total_size == expected_size

    def test_create_manifest_uncompressed(self, sample_slicer_info, sample_file_entries):
        """Test creating manifest for uncompressed backup."""
        manifest = create_manifest(sample_slicer_info, sample_file_entries, compressed=False)

        assert manifest.compressed is False

    def test_create_manifest_timestamp(self, sample_slicer_info, sample_file_entries):
        """Test that manifest has timestamp."""
        before = datetime.now()
        manifest = create_manifest(sample_slicer_info, sample_file_entries, compressed=True)
        after = datetime.now()

        assert before <= manifest.created_at <= after

    def test_create_manifest_no_version(self, sample_slicer_info, sample_file_entries):
        """Test creating manifest when slicer version is None."""
        sample_slicer_info.version = None

        manifest = create_manifest(sample_slicer_info, sample_file_entries, compressed=True)

        assert manifest.slicer_version is None


class TestCreateBackup:
    """Tests for create_backup function."""

    def test_create_compressed_backup(self, sample_slicer_info, tmp_path, monkeypatch):
        """Test creating compressed backup."""
        output_dir = tmp_path / "backups"

        # Mock verify_backup to avoid verification
        monkeypatch.setattr("orca_backup.core.verify.verify_backup", lambda p: True)

        backup_path = create_backup(
            sample_slicer_info, output_dir, compress=True, verify=False
        )

        assert backup_path.exists()
        assert backup_path.suffix == ".zip"
        assert "Orcaslicer_backup_" in backup_path.name

    def test_create_uncompressed_backup(self, sample_slicer_info, tmp_path, monkeypatch):
        """Test creating uncompressed backup."""
        output_dir = tmp_path / "backups"

        monkeypatch.setattr("orca_backup.core.verify.verify_backup", lambda p: True)

        backup_path = create_backup(
            sample_slicer_info, output_dir, compress=False, verify=False
        )

        assert backup_path.exists()
        assert backup_path.is_dir()
        assert not backup_path.suffix == ".zip"

    def test_create_backup_creates_output_dir(self, sample_slicer_info, tmp_path, monkeypatch):
        """Test that output directory is created if it doesn't exist."""
        output_dir = tmp_path / "new" / "nested" / "dir"
        assert not output_dir.exists()

        monkeypatch.setattr("orca_backup.core.verify.verify_backup", lambda p: True)

        create_backup(sample_slicer_info, output_dir, compress=True, verify=False)

        assert output_dir.exists()

    def test_create_backup_with_verify(self, sample_slicer_info, tmp_path, monkeypatch):
        """Test creating backup with verification."""
        output_dir = tmp_path / "backups"
        verify_called = []

        def mock_verify(path):
            verify_called.append(path)
            return True

        monkeypatch.setattr("orca_backup.core.verify.verify_backup", mock_verify)

        backup_path = create_backup(
            sample_slicer_info, output_dir, compress=True, verify=True
        )

        # Verify should have been called
        assert len(verify_called) == 1
        assert verify_called[0] == backup_path

    def test_create_backup_verify_failure(self, sample_slicer_info, tmp_path, monkeypatch):
        """Test that verification failure raises error."""
        output_dir = tmp_path / "backups"

        monkeypatch.setattr("orca_backup.core.verify.verify_backup", lambda p: False)

        with pytest.raises(RuntimeError, match="Backup verification failed"):
            create_backup(sample_slicer_info, output_dir, compress=True, verify=True)

    def test_create_backup_invalid_slicer(self, tmp_path):
        """Test that invalid slicer raises ValueError."""
        invalid_slicer = SlicerInfo(
            name=SlicerType.ORCASLICER,
            display_name="OrcaSlicer",
            config_path=tmp_path / "nonexistent",
            exists=False,
        )

        output_dir = tmp_path / "backups"

        with pytest.raises(ValueError, match="Invalid slicer"):
            create_backup(invalid_slicer, output_dir)

    def test_create_backup_manifest_included(self, sample_slicer_info, tmp_path, monkeypatch):
        """Test that backup includes manifest file."""
        output_dir = tmp_path / "backups"

        monkeypatch.setattr("orca_backup.core.verify.verify_backup", lambda p: True)

        backup_path = create_backup(
            sample_slicer_info, output_dir, compress=False, verify=False
        )

        manifest_file = backup_path / "backup_manifest.json"
        assert manifest_file.exists()

        # Verify manifest is valid JSON
        with open(manifest_file, "r") as f:
            manifest_data = json.load(f)
            assert "version" in manifest_data
            assert "slicer" in manifest_data

    def test_create_backup_contains_conf_file(self, sample_slicer_info, tmp_path, monkeypatch):
        """Test that backup contains conf file."""
        output_dir = tmp_path / "backups"

        monkeypatch.setattr("orca_backup.core.verify.verify_backup", lambda p: True)

        backup_path = create_backup(
            sample_slicer_info, output_dir, compress=False, verify=False
        )

        assert (backup_path / "OrcaSlicer.conf").exists()

    def test_create_backup_contains_user_dir(self, sample_slicer_info, tmp_path, monkeypatch):
        """Test that backup contains user directory."""
        output_dir = tmp_path / "backups"

        monkeypatch.setattr("orca_backup.core.verify.verify_backup", lambda p: True)

        backup_path = create_backup(
            sample_slicer_info, output_dir, compress=False, verify=False
        )

        assert (backup_path / "user").exists()

    def test_create_backup_flashforge_with_scripts(
        self, sample_flashforge_info, tmp_path, monkeypatch
    ):
        """Test backup of Orca-Flashforge includes custom_scripts."""
        output_dir = tmp_path / "backups"

        monkeypatch.setattr("orca_backup.core.verify.verify_backup", lambda p: True)

        backup_path = create_backup(
            sample_flashforge_info, output_dir, compress=False, verify=False
        )

        assert (backup_path / "custom_scripts").exists()
