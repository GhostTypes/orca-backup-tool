"""Integration tests for full restore workflow."""

import json
from pathlib import Path

import pytest

from orca_backup.core.backup import create_backup
from orca_backup.core.restore import restore_backup
from orca_backup.core.verify import calculate_sha256
from orca_backup.models.slicer import SlicerType


class TestRestoreWorkflow:
    """Integration tests for complete restore workflow."""

    def test_full_backup_restore_cycle(
        self, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test complete backup and restore cycle."""
        source_config_path, source_conf, source_user = temp_slicer_config

        # Mock slicer paths
        def mock_paths():
            return {
                "orcaslicer": source_config_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        # Create backup
        output_dir = tmp_path / "backups"
        from orca_backup.core.detector import get_slicer_info

        source_slicer = get_slicer_info(SlicerType.ORCASLICER)
        backup_path = create_backup(
            source_slicer, output_dir, compress=True, verify=True
        )

        # Create new target directory (simulate different machine)
        target_config_path = tmp_path / "restored" / "OrcaSlicer"
        target_config_path.mkdir(parents=True)

        # Mock paths for restore
        def mock_paths_restore():
            return {
                "orcaslicer": target_config_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr(
            "orca_backup.core.detector.get_slicer_paths", mock_paths_restore
        )

        # Restore backup
        success = restore_backup(backup_path, backup_existing=False)

        assert success is True

        # Verify files were restored
        assert (target_config_path / "OrcaSlicer.conf").exists()
        assert (target_config_path / "user").exists()

        # Verify content matches original
        original_conf_content = source_conf.read_text()
        restored_conf_content = (target_config_path / "OrcaSlicer.conf").read_text()
        assert restored_conf_content == original_conf_content

    def test_restore_preserves_checksums(
        self, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test that restored files have same checksums as originals."""
        source_config_path, source_conf, source_user = temp_slicer_config

        def mock_paths():
            return {
                "orcaslicer": source_config_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        # Calculate original checksums
        original_checksums = {}
        for file_path in source_config_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(source_config_path)
                original_checksums[str(relative_path)] = calculate_sha256(file_path)

        # Create backup
        output_dir = tmp_path / "backups"
        from orca_backup.core.detector import get_slicer_info

        source_slicer = get_slicer_info(SlicerType.ORCASLICER)
        backup_path = create_backup(
            source_slicer, output_dir, compress=True, verify=True
        )

        # Restore to new location
        target_config_path = tmp_path / "restored" / "OrcaSlicer"
        target_config_path.mkdir(parents=True)

        def mock_paths_restore():
            return {
                "orcaslicer": target_config_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr(
            "orca_backup.core.detector.get_slicer_paths", mock_paths_restore
        )

        restore_backup(backup_path, backup_existing=False)

        # Calculate restored checksums
        restored_checksums = {}
        for file_path in target_config_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(target_config_path)
                restored_checksums[str(relative_path)] = calculate_sha256(file_path)

        # Verify checksums match
        assert original_checksums == restored_checksums

    def test_restore_with_existing_backup(
        self, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test that existing config is backed up before restore."""
        source_config_path, _, _ = temp_slicer_config

        def mock_paths():
            return {
                "orcaslicer": source_config_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        # Create backup
        output_dir = tmp_path / "backups"
        from orca_backup.core.detector import get_slicer_info

        source_slicer = get_slicer_info(SlicerType.ORCASLICER)
        backup_path = create_backup(
            source_slicer, output_dir, compress=True, verify=True
        )

        # Create target with existing config
        target_config_path = tmp_path / "target" / "OrcaSlicer"
        target_config_path.mkdir(parents=True)

        existing_conf = target_config_path / "OrcaSlicer.conf"
        existing_conf.write_text('{"existing": "config"}')

        existing_user = target_config_path / "user"
        existing_user.mkdir()
        (existing_user / "existing_file.txt").write_text("existing")

        def mock_paths_restore():
            return {
                "orcaslicer": target_config_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr(
            "orca_backup.core.detector.get_slicer_paths", mock_paths_restore
        )

        # Restore with backup_existing=True
        restore_backup(backup_path, backup_existing=True)

        # Verify temp backup was created
        temp_backup_dir = target_config_path.parent / "orca_backups_temp"
        assert temp_backup_dir.exists()

        # Verify temp backup contains files
        backup_files = list(temp_backup_dir.glob("*.zip"))
        assert len(backup_files) >= 1

    def test_restore_dry_run_no_changes(
        self, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test that dry-run doesn't modify any files."""
        source_config_path, _, _ = temp_slicer_config

        def mock_paths():
            return {
                "orcaslicer": source_config_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        # Create backup
        output_dir = tmp_path / "backups"
        from orca_backup.core.detector import get_slicer_info

        source_slicer = get_slicer_info(SlicerType.ORCASLICER)
        backup_path = create_backup(
            source_slicer, output_dir, compress=True, verify=True
        )

        # Create empty target
        target_config_path = tmp_path / "target" / "OrcaSlicer"
        target_config_path.mkdir(parents=True)

        # Record state before dry-run
        files_before = set(target_config_path.rglob("*"))

        def mock_paths_restore():
            return {
                "orcaslicer": target_config_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr(
            "orca_backup.core.detector.get_slicer_paths", mock_paths_restore
        )

        # Dry-run restore
        restore_backup(backup_path, dry_run=True, backup_existing=False)

        # Verify no files were created
        files_after = set(target_config_path.rglob("*"))
        assert files_before == files_after

    def test_restore_uncompressed_backup(
        self, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test restoring from uncompressed backup."""
        source_config_path, source_conf, _ = temp_slicer_config

        def mock_paths():
            return {
                "orcaslicer": source_config_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        # Create uncompressed backup
        output_dir = tmp_path / "backups"
        from orca_backup.core.detector import get_slicer_info

        source_slicer = get_slicer_info(SlicerType.ORCASLICER)
        backup_path = create_backup(
            source_slicer, output_dir, compress=False, verify=True
        )

        assert backup_path.is_dir()

        # Restore from directory
        target_config_path = tmp_path / "restored" / "OrcaSlicer"
        target_config_path.mkdir(parents=True)

        def mock_paths_restore():
            return {
                "orcaslicer": target_config_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr(
            "orca_backup.core.detector.get_slicer_paths", mock_paths_restore
        )

        success = restore_backup(backup_path, backup_existing=False)

        assert success is True
        assert (target_config_path / "OrcaSlicer.conf").exists()

    def test_cross_platform_restore_manifest(self, tmp_path, monkeypatch):
        """Test that backup from one platform can be read on another."""
        # Create a backup manifest as if from different platform
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        # Create files
        conf_file = backup_dir / "OrcaSlicer.conf"
        conf_file.write_text('{"test": "data"}')

        from orca_backup.models.backup import BackupManifest, FileEntry

        # Create manifest with different platform
        manifest = BackupManifest(
            created_at="2025-11-14T12:00:00",
            slicer="orcaslicer",
            slicer_version="2.1.0",
            platform="darwin",  # Different platform
            files=[
                FileEntry(
                    path="OrcaSlicer.conf",
                    size=conf_file.stat().st_size,
                    sha256=calculate_sha256(conf_file),
                )
            ],
            total_files=1,
            total_size=conf_file.stat().st_size,
        )

        manifest_file = backup_dir / "backup_manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest.model_dump(mode="json"), f, default=str)

        # Restore on current platform
        target_config_path = tmp_path / "target" / "OrcaSlicer"
        target_config_path.mkdir(parents=True)

        def mock_paths():
            return {
                "orcaslicer": target_config_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        # Should restore successfully despite platform difference
        success = restore_backup(backup_dir, backup_existing=False)

        assert success is True
        assert (target_config_path / "OrcaSlicer.conf").exists()

    def test_restore_flashforge_with_custom_scripts(
        self, temp_flashforge_config, tmp_path, monkeypatch
    ):
        """Test restoring Orca-Flashforge backup with custom scripts."""
        source_config_path, _, _ = temp_flashforge_config

        def mock_paths():
            return {
                "orcaslicer": tmp_path / "OrcaSlicer",
                "orca-flashforge": source_config_path,
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        # Create backup
        output_dir = tmp_path / "backups"
        from orca_backup.core.detector import get_slicer_info

        source_slicer = get_slicer_info(SlicerType.ORCA_FLASHFORGE)
        backup_path = create_backup(
            source_slicer, output_dir, compress=True, verify=True
        )

        # Restore to new location
        target_config_path = tmp_path / "restored" / "Orca-Flashforge"
        target_config_path.mkdir(parents=True)

        def mock_paths_restore():
            return {
                "orcaslicer": tmp_path / "OrcaSlicer",
                "orca-flashforge": target_config_path,
            }

        monkeypatch.setattr(
            "orca_backup.core.detector.get_slicer_paths", mock_paths_restore
        )

        success = restore_backup(backup_path, backup_existing=False)

        assert success is True
        # Verify custom_scripts were restored
        assert (target_config_path / "custom_scripts").exists()
        assert (target_config_path / "custom_scripts" / "test_script.py").exists()
