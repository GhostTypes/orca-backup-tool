"""Unit tests for compression utilities."""

import zipfile
from pathlib import Path

import pytest

from orca_backup.utils.compression import compress_directory, extract_archive, is_valid_zip


class TestCompressDirectory:
    """Tests for compress_directory function."""

    def test_compress_simple_directory(self, tmp_path):
        """Test compressing a simple directory."""
        # Create source directory with files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "file1.txt").write_text("content1")
        (source_dir / "file2.txt").write_text("content2")

        # Compress
        output_file = tmp_path / "output.zip"
        result = compress_directory(source_dir, output_file)

        assert result == output_file
        assert output_file.exists()
        assert zipfile.is_zipfile(output_file)

        # Verify contents
        with zipfile.ZipFile(output_file, "r") as zipf:
            namelist = zipf.namelist()
            assert "file1.txt" in namelist
            assert "file2.txt" in namelist
            assert zipf.read("file1.txt").decode() == "content1"
            assert zipf.read("file2.txt").decode() == "content2"

    def test_compress_nested_directories(self, tmp_path):
        """Test compressing nested directories."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "file1.txt").write_text("root")

        subdir = source_dir / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").write_text("nested")

        deep_dir = subdir / "deep"
        deep_dir.mkdir()
        (deep_dir / "file3.txt").write_text("deep")

        output_file = tmp_path / "output.zip"
        compress_directory(source_dir, output_file)

        with zipfile.ZipFile(output_file, "r") as zipf:
            namelist = zipf.namelist()
            assert "file1.txt" in namelist
            assert "subdir/file2.txt" in namelist
            assert "subdir/deep/file3.txt" in namelist

    def test_compress_preserves_relative_paths(self, tmp_path):
        """Test that relative paths are preserved."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        nested = source_dir / "a" / "b" / "c"
        nested.mkdir(parents=True)
        (nested / "deep_file.txt").write_text("deep")

        output_file = tmp_path / "output.zip"
        compress_directory(source_dir, output_file)

        with zipfile.ZipFile(output_file, "r") as zipf:
            namelist = zipf.namelist()
            assert "a/b/c/deep_file.txt" in namelist

    def test_compress_empty_directory(self, tmp_path):
        """Test compressing an empty directory."""
        source_dir = tmp_path / "empty"
        source_dir.mkdir()

        output_file = tmp_path / "output.zip"
        compress_directory(source_dir, output_file)

        assert output_file.exists()
        with zipfile.ZipFile(output_file, "r") as zipf:
            assert len(zipf.namelist()) == 0

    def test_compress_with_binary_files(self, tmp_path):
        """Test compressing binary files."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        binary_data = b"\x00\x01\x02\x03\x04\x05"
        (source_dir / "binary.bin").write_bytes(binary_data)

        output_file = tmp_path / "output.zip"
        compress_directory(source_dir, output_file)

        with zipfile.ZipFile(output_file, "r") as zipf:
            assert zipf.read("binary.bin") == binary_data

    def test_compress_creates_deflated_zip(self, tmp_path):
        """Test that compression uses ZIP_DEFLATED."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "file.txt").write_text("x" * 1000)  # Compressible content

        output_file = tmp_path / "output.zip"
        compress_directory(source_dir, output_file)

        with zipfile.ZipFile(output_file, "r") as zipf:
            info = zipf.getinfo("file.txt")
            assert info.compress_type == zipfile.ZIP_DEFLATED
            # Compressed size should be smaller
            assert info.compress_size < info.file_size


class TestExtractArchive:
    """Tests for extract_archive function."""

    def test_extract_simple_archive(self, tmp_path):
        """Test extracting a simple archive."""
        # Create archive
        archive_path = tmp_path / "test.zip"
        with zipfile.ZipFile(archive_path, "w") as zipf:
            zipf.writestr("file1.txt", "content1")
            zipf.writestr("file2.txt", "content2")

        # Extract
        output_dir = tmp_path / "extracted"
        result = extract_archive(archive_path, output_dir)

        assert result == output_dir
        assert output_dir.exists()
        assert (output_dir / "file1.txt").read_text() == "content1"
        assert (output_dir / "file2.txt").read_text() == "content2"

    def test_extract_creates_output_directory(self, tmp_path):
        """Test that extract creates output directory if it doesn't exist."""
        archive_path = tmp_path / "test.zip"
        with zipfile.ZipFile(archive_path, "w") as zipf:
            zipf.writestr("file.txt", "content")

        output_dir = tmp_path / "new" / "nested" / "dir"
        assert not output_dir.exists()

        extract_archive(archive_path, output_dir)

        assert output_dir.exists()
        assert (output_dir / "file.txt").exists()

    def test_extract_nested_structure(self, tmp_path):
        """Test extracting nested directory structure."""
        archive_path = tmp_path / "test.zip"
        with zipfile.ZipFile(archive_path, "w") as zipf:
            zipf.writestr("a/b/c/deep.txt", "deep content")
            zipf.writestr("a/file.txt", "root content")

        output_dir = tmp_path / "extracted"
        extract_archive(archive_path, output_dir)

        assert (output_dir / "a" / "b" / "c" / "deep.txt").read_text() == "deep content"
        assert (output_dir / "a" / "file.txt").read_text() == "root content"

    def test_extract_to_existing_directory(self, tmp_path):
        """Test extracting to an existing directory."""
        archive_path = tmp_path / "test.zip"
        with zipfile.ZipFile(archive_path, "w") as zipf:
            zipf.writestr("new_file.txt", "new content")

        output_dir = tmp_path / "existing"
        output_dir.mkdir()
        (output_dir / "existing_file.txt").write_text("existing")

        extract_archive(archive_path, output_dir)

        # Both files should exist
        assert (output_dir / "existing_file.txt").read_text() == "existing"
        assert (output_dir / "new_file.txt").read_text() == "new content"

    def test_extract_binary_files(self, tmp_path):
        """Test extracting binary files."""
        binary_data = b"\x00\x01\x02\x03\x04\x05"
        archive_path = tmp_path / "test.zip"
        with zipfile.ZipFile(archive_path, "w") as zipf:
            zipf.writestr("binary.bin", binary_data)

        output_dir = tmp_path / "extracted"
        extract_archive(archive_path, output_dir)

        assert (output_dir / "binary.bin").read_bytes() == binary_data


class TestIsValidZip:
    """Tests for is_valid_zip function."""

    def test_valid_zip_returns_true(self, tmp_path):
        """Test that valid ZIP returns True."""
        zip_path = tmp_path / "valid.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr("file.txt", "content")

        assert is_valid_zip(zip_path) is True

    def test_empty_zip_is_valid(self, tmp_path):
        """Test that empty ZIP is valid."""
        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            pass  # Create empty ZIP

        assert is_valid_zip(zip_path) is True

    def test_corrupted_zip_returns_false(self, tmp_path):
        """Test that corrupted ZIP returns False."""
        zip_path = tmp_path / "corrupted.zip"
        zip_path.write_bytes(b"This is not a valid ZIP file")

        assert is_valid_zip(zip_path) is False

    def test_nonexistent_file_returns_false(self, tmp_path):
        """Test that non-existent file returns False."""
        zip_path = tmp_path / "nonexistent.zip"

        assert is_valid_zip(zip_path) is False

    def test_non_zip_file_returns_false(self, tmp_path):
        """Test that non-ZIP file returns False."""
        text_file = tmp_path / "text.txt"
        text_file.write_text("Just a text file")

        assert is_valid_zip(text_file) is False

    def test_partially_corrupted_zip_returns_false(self, tmp_path):
        """Test that partially corrupted ZIP returns False."""
        # Create a valid ZIP
        zip_path = tmp_path / "partial.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr("file.txt", "content")

        # Corrupt it by truncating
        data = zip_path.read_bytes()
        zip_path.write_bytes(data[:len(data)//2])

        assert is_valid_zip(zip_path) is False

    def test_zip_with_crc_error(self, tmp_path):
        """Test that ZIP with CRC errors is detected."""
        # Create a valid ZIP
        zip_path = tmp_path / "crc_error.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr("file.txt", "original content")

        # Manually corrupt the file data (not the directory)
        with open(zip_path, "r+b") as f:
            f.seek(30)  # Skip header, write to content area
            f.write(b"CORRUPTED")

        # testzip() should detect CRC mismatch
        assert is_valid_zip(zip_path) is False
