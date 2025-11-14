"""Integration tests for full backup workflow."""

import json
import zipfile
from pathlib import Path

import pytest

from orca_backup.core.backup import create_backup
from orca_backup.core.detector import get_installed_slicers
from orca_backup.core.verify import verify_backup
from orca_backup.models.slicer import SlicerType


class TestBackupWorkflow:
    """Integration tests for complete backup workflow."""

    def test_full_backup_creation_compressed(self, sample_slicer_info, tmp_path):
        """Test complete backup creation workflow with compression."""
        output_dir = tmp_path / "backups"

        # Create backup
        backup_path = create_backup(
            sample_slicer_info, output_dir, compress=True, verify=True
        )

        # Verify backup was created
        assert backup_path.exists()
        assert backup_path.is_file()
        assert backup_path.suffix == ".zip"

        # Verify it's a valid ZIP
        assert zipfile.is_zipfile(backup_path)

        # Verify backup passes verification
        assert verify_backup(backup_path, verbose=False) is True

        # Verify manifest is in ZIP
        with zipfile.ZipFile(backup_path, "r") as zipf:
            assert "backup_manifest.json" in zipf.namelist()
            assert "OrcaSlicer.conf" in zipf.namelist()

            # Check manifest content
            with zipf.open("backup_manifest.json") as f:
                manifest_data = json.load(f)
                assert manifest_data["slicer"] == "orcaslicer"
                assert manifest_data["version"] == "1.0"
                assert "files" in manifest_data

    def test_full_backup_creation_uncompressed(self, sample_slicer_info, tmp_path):
        """Test complete backup creation workflow without compression."""
        output_dir = tmp_path / "backups"

        backup_path = create_backup(
            sample_slicer_info, output_dir, compress=False, verify=True
        )

        # Verify backup was created as directory
        assert backup_path.exists()
        assert backup_path.is_dir()

        # Verify manifest exists
        manifest_file = backup_path / "backup_manifest.json"
        assert manifest_file.exists()

        # Verify verification passes
        assert verify_backup(backup_path, verbose=False) is True

        # Verify files were copied
        assert (backup_path / "OrcaSlicer.conf").exists()
        assert (backup_path / "user").exists()

    def test_backup_manifest_integrity(self, sample_slicer_info, tmp_path):
        """Test that manifest accurately reflects backup contents."""
        output_dir = tmp_path / "backups"

        backup_path = create_backup(
            sample_slicer_info, output_dir, compress=False, verify=False
        )

        # Load manifest
        manifest_file = backup_path / "backup_manifest.json"
        with open(manifest_file, "r") as f:
            manifest_data = json.load(f)

        # Verify all files in manifest exist
        for file_entry in manifest_data["files"]:
            file_path = backup_path / file_entry["path"]
            assert file_path.exists()

            # Verify size matches
            actual_size = file_path.stat().st_size
            assert actual_size == file_entry["size"]

    def test_backup_flashforge_with_custom_scripts(
        self, sample_flashforge_info, tmp_path
    ):
        """Test backing up Orca-Flashforge includes custom scripts."""
        output_dir = tmp_path / "backups"

        backup_path = create_backup(
            sample_flashforge_info, output_dir, compress=False, verify=True
        )

        # Verify custom_scripts were included
        assert (backup_path / "custom_scripts").exists()

        # Verify in manifest
        manifest_file = backup_path / "backup_manifest.json"
        with open(manifest_file, "r") as f:
            manifest_data = json.load(f)

        script_files = [
            f for f in manifest_data["files"] if f["path"].startswith("custom_scripts/")
        ]
        assert len(script_files) > 0

    def test_backup_all_installed_slicers(
        self, temp_slicer_config, temp_flashforge_config, tmp_path, monkeypatch
    ):
        """Test backing up all installed slicers."""
        orca_path, _, _ = temp_slicer_config
        flash_path, _, _ = temp_flashforge_config

        # Mock get_slicer_paths to return our test paths
        def mock_paths():
            return {
                "orcaslicer": orca_path,
                "orca-flashforge": flash_path,
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        output_dir = tmp_path / "backups"

        # Get all installed slicers
        slicers = get_installed_slicers()
        assert len(slicers) == 2

        # Create backups for all
        backup_paths = []
        for slicer in slicers:
            backup_path = create_backup(slicer, output_dir, compress=True, verify=True)
            backup_paths.append(backup_path)

        # Verify both backups were created
        assert len(backup_paths) == 2
        for backup_path in backup_paths:
            assert backup_path.exists()
            assert verify_backup(backup_path, verbose=False) is True

    def test_backup_output_directory_creation(self, sample_slicer_info, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        # Use nested non-existent directory
        output_dir = tmp_path / "level1" / "level2" / "backups"
        assert not output_dir.exists()

        backup_path = create_backup(
            sample_slicer_info, output_dir, compress=True, verify=False
        )

        # Verify directory was created
        assert output_dir.exists()
        assert backup_path.parent == output_dir

    def test_backup_preserves_file_structure(self, sample_slicer_info, tmp_path):
        """Test that backup preserves original file structure."""
        output_dir = tmp_path / "backups"

        backup_path = create_backup(
            sample_slicer_info, output_dir, compress=False, verify=False
        )

        # Verify directory structure matches original
        original_user_dir = sample_slicer_info.user_dir
        backup_user_dir = backup_path / "user"

        # Check that subdirectories exist
        for subdir in original_user_dir.rglob("*"):
            if subdir.is_dir():
                relative_path = subdir.relative_to(original_user_dir)
                backup_subdir = backup_user_dir / relative_path
                assert backup_subdir.exists()

    def test_backup_naming_convention(self, sample_slicer_info, tmp_path):
        """Test that backup follows naming convention."""
        output_dir = tmp_path / "backups"

        backup_path = create_backup(
            sample_slicer_info, output_dir, compress=True, verify=False
        )

        # Check naming pattern: {Slicer}_backup_{timestamp}.zip
        assert backup_path.name.startswith("Orcaslicer_backup_")
        assert backup_path.suffix == ".zip"

        # Should have timestamp in format YYYY-MM-DD_HH-MM-SS
        name_parts = backup_path.stem.split("_backup_")
        assert len(name_parts) == 2
        timestamp_part = name_parts[1]
        assert len(timestamp_part) == 19  # YYYY-MM-DD_HH-MM-SS

    def test_multiple_backups_different_names(self, sample_slicer_info, tmp_path):
        """Test that multiple backups get different names."""
        output_dir = tmp_path / "backups"

        # Create two backups (small delay to ensure different timestamps)
        backup1 = create_backup(
            sample_slicer_info, output_dir, compress=True, verify=False
        )

        import time

        time.sleep(1.1)  # Wait to ensure different timestamp

        backup2 = create_backup(
            sample_slicer_info, output_dir, compress=True, verify=False
        )

        # Verify different names
        assert backup1 != backup2
        assert backup1.exists()
        assert backup2.exists()
