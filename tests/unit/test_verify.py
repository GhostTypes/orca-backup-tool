"""Unit tests for backup verification."""

import json
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from orca_backup.core.verify import (
    calculate_sha256,
    get_backup_info,
    load_manifest,
    verify_backup,
)
from orca_backup.models.backup import BackupManifest, FileEntry


class TestCalculateSha256:
    """Tests for calculate_sha256 function."""

    def test_calculate_checksum_text_file(self, tmp_path):
        """Test calculating SHA256 for text file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        checksum = calculate_sha256(test_file)

        # Known SHA256 for "Hello, World!"
        expected = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        assert checksum == expected

    def test_calculate_checksum_binary_file(self, tmp_path):
        """Test calculating SHA256 for binary file."""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"\x00\x01\x02\x03\x04")

        checksum = calculate_sha256(test_file)

        assert len(checksum) == 64  # SHA256 is 64 hex characters
        assert all(c in "0123456789abcdef" for c in checksum)

    def test_calculate_checksum_empty_file(self, tmp_path):
        """Test calculating SHA256 for empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        checksum = calculate_sha256(test_file)

        # Known SHA256 for empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert checksum == expected

    def test_calculate_checksum_large_file(self, tmp_path):
        """Test calculating SHA256 for large file."""
        test_file = tmp_path / "large.txt"
        # Create a large file (> 4096 bytes to test chunking)
        test_file.write_text("x" * 10000)

        checksum = calculate_sha256(test_file)

        assert len(checksum) == 64

    def test_consistent_checksums(self, tmp_path):
        """Test that checksums are consistent across calls."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Consistent content")

        checksum1 = calculate_sha256(test_file)
        checksum2 = calculate_sha256(test_file)

        assert checksum1 == checksum2


class TestLoadManifest:
    """Tests for load_manifest function."""

    def test_load_from_directory(self, tmp_path, sample_backup_manifest):
        """Test loading manifest from directory."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        manifest_file = backup_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(sample_backup_manifest.model_dump(mode="json"), default=str)
        )

        loaded = load_manifest(backup_dir)

        assert loaded is not None
        assert loaded.slicer == sample_backup_manifest.slicer
        assert loaded.total_files == sample_backup_manifest.total_files

    def test_load_from_zip(self, tmp_path, sample_backup_manifest):
        """Test loading manifest from ZIP archive."""
        zip_path = tmp_path / "backup.zip"

        with zipfile.ZipFile(zip_path, "w") as zipf:
            manifest_data = json.dumps(
                sample_backup_manifest.model_dump(mode="json"), default=str
            )
            zipf.writestr("backup_manifest.json", manifest_data)

        loaded = load_manifest(zip_path)

        assert loaded is not None
        assert loaded.slicer == sample_backup_manifest.slicer
        assert loaded.total_files == sample_backup_manifest.total_files

    def test_load_missing_manifest_in_directory(self, tmp_path):
        """Test loading from directory without manifest."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()
        # No manifest file

        loaded = load_manifest(backup_dir)

        assert loaded is None

    def test_load_missing_manifest_in_zip(self, tmp_path):
        """Test loading from ZIP without manifest."""
        zip_path = tmp_path / "backup.zip"

        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr("some_file.txt", "content")
            # No manifest

        loaded = load_manifest(zip_path)

        assert loaded is None

    def test_load_invalid_json(self, tmp_path):
        """Test loading manifest with invalid JSON."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        manifest_file = backup_dir / "backup_manifest.json"
        manifest_file.write_text("This is not valid JSON {{{")

        loaded = load_manifest(backup_dir)

        assert loaded is None

    def test_load_nonexistent_path(self, tmp_path):
        """Test loading from non-existent path."""
        nonexistent = tmp_path / "nonexistent"

        loaded = load_manifest(nonexistent)

        assert loaded is None


class TestVerifyBackup:
    """Tests for verify_backup function."""

    def test_verify_valid_directory_backup(self, tmp_path):
        """Test verifying valid directory backup."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        # Create files
        file1 = backup_dir / "file1.txt"
        file1.write_text("content1")
        file2 = backup_dir / "file2.txt"
        file2.write_text("content2")

        # Create manifest
        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            files=[
                FileEntry(
                    path="file1.txt",
                    size=file1.stat().st_size,
                    sha256=calculate_sha256(file1),
                ),
                FileEntry(
                    path="file2.txt",
                    size=file2.stat().st_size,
                    sha256=calculate_sha256(file2),
                ),
            ],
            total_files=2,
            total_size=file1.stat().st_size + file2.stat().st_size,
        )

        manifest_file = backup_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        is_valid = verify_backup(backup_dir, verbose=False)

        assert is_valid is True

    def test_verify_valid_zip_backup(self, tmp_path):
        """Test verifying valid ZIP backup."""
        # Create backup directory first
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        file1 = staging_dir / "file1.txt"
        file1.write_text("content1")

        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            files=[
                FileEntry(
                    path="file1.txt",
                    size=file1.stat().st_size,
                    sha256=calculate_sha256(file1),
                )
            ],
            total_files=1,
            total_size=file1.stat().st_size,
        )

        manifest_file = staging_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        # Create ZIP
        zip_path = tmp_path / "backup.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.write(file1, "file1.txt")
            zipf.write(manifest_file, "backup_manifest.json")

        is_valid = verify_backup(zip_path, verbose=False)

        assert is_valid is True

    def test_verify_nonexistent_backup(self, tmp_path):
        """Test verifying non-existent backup."""
        nonexistent = tmp_path / "nonexistent.zip"

        is_valid = verify_backup(nonexistent, verbose=False)

        assert is_valid is False

    def test_verify_corrupted_zip(self, tmp_path):
        """Test verifying corrupted ZIP."""
        zip_path = tmp_path / "corrupted.zip"
        zip_path.write_bytes(b"Not a valid ZIP file")

        is_valid = verify_backup(zip_path, verbose=False)

        assert is_valid is False

    def test_verify_missing_manifest(self, tmp_path):
        """Test verifying backup without manifest."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()
        (backup_dir / "file.txt").write_text("content")
        # No manifest

        is_valid = verify_backup(backup_dir, verbose=False)

        assert is_valid is False

    def test_verify_missing_files(self, tmp_path):
        """Test verifying backup with missing files."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        # Create manifest referencing files that don't exist
        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            files=[
                FileEntry(path="missing.txt", size=100, sha256="a" * 64),
            ],
            total_files=1,
            total_size=100,
        )

        manifest_file = backup_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        is_valid = verify_backup(backup_dir, verbose=False)

        assert is_valid is False

    def test_verify_checksum_mismatch(self, tmp_path):
        """Test verifying backup with checksum mismatch."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        file1 = backup_dir / "file1.txt"
        file1.write_text("original content")

        # Create manifest with wrong checksum
        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            files=[
                FileEntry(
                    path="file1.txt",
                    size=file1.stat().st_size,
                    sha256="wrongchecksumwrongchecksumwrongchecksumwrongchecksum12345678",
                )
            ],
            total_files=1,
            total_size=file1.stat().st_size,
        )

        manifest_file = backup_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        is_valid = verify_backup(backup_dir, verbose=False)

        assert is_valid is False

    def test_verify_verbose_output(self, tmp_path, capsys):
        """Test verbose output during verification."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        file1 = backup_dir / "file1.txt"
        file1.write_text("content")

        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            files=[
                FileEntry(
                    path="file1.txt",
                    size=file1.stat().st_size,
                    sha256=calculate_sha256(file1),
                )
            ],
            total_files=1,
            total_size=file1.stat().st_size,
        )

        manifest_file = backup_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        verify_backup(backup_dir, verbose=True)

        captured = capsys.readouterr()
        assert "Manifest file found and valid" in captured.out
        assert "All checksums verified" in captured.out


class TestGetBackupInfo:
    """Tests for get_backup_info function."""

    def test_get_info_valid_backup(self, tmp_path):
        """Test getting info for valid backup."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        file1 = backup_dir / "file1.txt"
        file1.write_text("content")

        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            files=[
                FileEntry(
                    path="file1.txt",
                    size=file1.stat().st_size,
                    sha256=calculate_sha256(file1),
                )
            ],
            total_files=1,
            total_size=file1.stat().st_size,
        )

        manifest_file = backup_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        info = get_backup_info(backup_dir)

        assert info is not None
        assert info.backup_path == backup_dir
        assert info.manifest.slicer == "orcaslicer"
        assert info.is_valid is True
        assert info.size_mb > 0

    def test_get_info_zip_backup(self, tmp_path):
        """Test getting info for ZIP backup."""
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        file1 = staging_dir / "file1.txt"
        file1.write_text("x" * 1024)  # 1KB

        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            files=[
                FileEntry(
                    path="file1.txt",
                    size=file1.stat().st_size,
                    sha256=calculate_sha256(file1),
                )
            ],
            total_files=1,
            total_size=file1.stat().st_size,
        )

        manifest_file = staging_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        # Create ZIP
        zip_path = tmp_path / "backup.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.write(file1, "file1.txt")
            zipf.write(manifest_file, "backup_manifest.json")

        info = get_backup_info(zip_path)

        assert info is not None
        assert info.backup_path == zip_path
        # ZIP size should be calculated from file size
        assert info.size_mb > 0

    def test_get_info_invalid_backup(self, tmp_path):
        """Test getting info for invalid backup."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()
        # No manifest

        info = get_backup_info(backup_dir)

        assert info is None

    def test_get_info_size_calculation_directory(self, tmp_path):
        """Test size calculation for directory backup."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        # Create multiple files
        file1 = backup_dir / "file1.txt"
        file1.write_text("x" * 1024)  # 1KB
        file2 = backup_dir / "file2.txt"
        file2.write_text("y" * 2048)  # 2KB

        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            files=[
                FileEntry(
                    path="file1.txt",
                    size=file1.stat().st_size,
                    sha256=calculate_sha256(file1),
                ),
                FileEntry(
                    path="file2.txt",
                    size=file2.stat().st_size,
                    sha256=calculate_sha256(file2),
                ),
            ],
            total_files=2,
            total_size=3072,
        )

        manifest_file = backup_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        info = get_backup_info(backup_dir)

        # Size should include all files
        assert info.size_mb > 0
