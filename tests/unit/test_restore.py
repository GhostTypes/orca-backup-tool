"""Unit tests for backup restore."""

import json
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from orca_backup.core.restore import get_restore_file_list, restore_backup
from orca_backup.core.verify import calculate_sha256
from orca_backup.models.backup import BackupManifest, FileEntry
from orca_backup.models.slicer import SlicerType


class TestGetRestoreFileList:
    """Tests for get_restore_file_list function."""

    def test_get_file_list_from_directory(self, tmp_path, monkeypatch):
        """Test getting restore file list from directory backup."""
        # Create backup directory with manifest
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            files=[
                FileEntry(path="OrcaSlicer.conf", size=100, sha256="a" * 64),
                FileEntry(path="user/filament/custom.json", size=50, sha256="b" * 64),
            ],
            total_files=2,
            total_size=150,
        )

        manifest_file = backup_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        # Mock slicer config path
        config_path = tmp_path / "OrcaSlicer"
        config_path.mkdir()

        def mock_get_slicer_info(slicer_type):
            from orca_backup.models.slicer import SlicerInfo

            return SlicerInfo(
                name=slicer_type,
                display_name="OrcaSlicer",
                config_path=config_path,
                exists=True,
            )

        monkeypatch.setattr(
            "orca_backup.core.restore.get_slicer_info", mock_get_slicer_info
        )

        file_list = get_restore_file_list(backup_dir)

        assert len(file_list) == 2
        # Check source and destination paths
        src1, dst1 = file_list[0]
        assert src1 == Path("OrcaSlicer.conf")
        assert dst1 == config_path / "OrcaSlicer.conf"

        src2, dst2 = file_list[1]
        assert src2 == Path("user/filament/custom.json")
        assert dst2 == config_path / "user/filament/custom.json"

    def test_get_file_list_invalid_manifest(self, tmp_path):
        """Test that invalid manifest raises ValueError."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()
        # No manifest

        with pytest.raises(ValueError, match="Could not load backup manifest"):
            get_restore_file_list(backup_dir)


class TestRestoreBackup:
    """Tests for restore_backup function."""

    def test_restore_from_directory(self, tmp_path, monkeypatch):
        """Test restoring from directory backup."""
        # Create backup
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        # Create files in backup
        conf_file = backup_dir / "OrcaSlicer.conf"
        conf_file.write_text('{"test": "data"}')

        user_dir = backup_dir / "user"
        user_dir.mkdir()
        (user_dir / "custom.json").write_text('{"custom": true}')

        # Create manifest
        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            files=[
                FileEntry(
                    path="OrcaSlicer.conf",
                    size=conf_file.stat().st_size,
                    sha256=calculate_sha256(conf_file),
                ),
                FileEntry(
                    path="user/custom.json",
                    size=(user_dir / "custom.json").stat().st_size,
                    sha256=calculate_sha256(user_dir / "custom.json"),
                ),
            ],
            total_files=2,
            total_size=100,
        )

        manifest_file = backup_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        # Create target slicer directory
        target_dir = tmp_path / "target" / "OrcaSlicer"
        target_dir.mkdir(parents=True)

        def mock_get_slicer_info(slicer_type):
            from orca_backup.models.slicer import SlicerInfo

            return SlicerInfo(
                name=slicer_type,
                display_name="OrcaSlicer",
                config_path=target_dir,
                exists=True,
                conf_file=target_dir / "OrcaSlicer.conf",
                user_dir=target_dir / "user",
            )

        monkeypatch.setattr(
            "orca_backup.core.restore.get_slicer_info", mock_get_slicer_info
        )
        monkeypatch.setattr("orca_backup.core.restore.verify_backup", lambda p, verbose=False: True)

        success = restore_backup(backup_dir, backup_existing=False)

        assert success is True
        assert (target_dir / "OrcaSlicer.conf").exists()
        assert (target_dir / "user" / "custom.json").exists()

    def test_restore_from_zip(self, tmp_path, monkeypatch):
        """Test restoring from ZIP backup."""
        # Create staging for ZIP
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        conf_file = staging_dir / "OrcaSlicer.conf"
        conf_file.write_text('{"test": "data"}')

        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
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

        manifest_file = staging_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        # Create ZIP
        zip_path = tmp_path / "backup.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.write(conf_file, "OrcaSlicer.conf")
            zipf.write(manifest_file, "backup_manifest.json")

        # Target directory
        target_dir = tmp_path / "target" / "OrcaSlicer"
        target_dir.mkdir(parents=True)

        def mock_get_slicer_info(slicer_type):
            from orca_backup.models.slicer import SlicerInfo

            return SlicerInfo(
                name=slicer_type,
                display_name="OrcaSlicer",
                config_path=target_dir,
                exists=True,
                conf_file=target_dir / "OrcaSlicer.conf",
                user_dir=target_dir / "user",
            )

        monkeypatch.setattr(
            "orca_backup.core.restore.get_slicer_info", mock_get_slicer_info
        )
        monkeypatch.setattr("orca_backup.core.restore.verify_backup", lambda p, verbose=False: True)

        success = restore_backup(zip_path, backup_existing=False)

        assert success is True
        assert (target_dir / "OrcaSlicer.conf").exists()

    def test_restore_dry_run(self, tmp_path, monkeypatch, capsys):
        """Test dry-run mode doesn't modify files."""
        # Create backup
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        conf_file = backup_dir / "OrcaSlicer.conf"
        conf_file.write_text('{"test": "data"}')

        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
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
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        target_dir = tmp_path / "target" / "OrcaSlicer"
        target_dir.mkdir(parents=True)

        def mock_get_slicer_info(slicer_type):
            from orca_backup.models.slicer import SlicerInfo

            return SlicerInfo(
                name=slicer_type,
                display_name="OrcaSlicer",
                config_path=target_dir,
                exists=True,
            )

        monkeypatch.setattr(
            "orca_backup.core.restore.get_slicer_info", mock_get_slicer_info
        )
        monkeypatch.setattr("orca_backup.core.restore.verify_backup", lambda p, verbose=False: True)

        success = restore_backup(backup_dir, dry_run=True, backup_existing=False)

        assert success is True
        # File should NOT have been restored
        assert not (target_dir / "OrcaSlicer.conf").exists()

        # Should have printed dry-run info
        captured = capsys.readouterr()
        assert "Would restore" in captured.out

    def test_restore_verification_failure(self, tmp_path, monkeypatch):
        """Test that verification failure raises ValueError."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        monkeypatch.setattr("orca_backup.core.restore.verify_backup", lambda p, verbose=False: False)

        with pytest.raises(ValueError, match="Backup verification failed"):
            restore_backup(backup_dir)

    def test_restore_slicer_not_found(self, tmp_path, monkeypatch):
        """Test that non-existent target slicer raises ValueError."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
            files=[],
            total_files=0,
            total_size=0,
        )

        manifest_file = backup_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        def mock_get_slicer_info(slicer_type):
            from orca_backup.models.slicer import SlicerInfo

            return SlicerInfo(
                name=slicer_type,
                display_name="OrcaSlicer",
                config_path=tmp_path / "nonexistent",
                exists=False,
            )

        monkeypatch.setattr(
            "orca_backup.core.restore.get_slicer_info", mock_get_slicer_info
        )
        monkeypatch.setattr("orca_backup.core.restore.verify_backup", lambda p, verbose=False: True)

        with pytest.raises(ValueError, match="not found"):
            restore_backup(backup_dir)

    def test_restore_with_backup_existing(self, tmp_path, monkeypatch, capsys):
        """Test that existing config is backed up before restore."""
        # Create backup to restore from
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        conf_file = backup_dir / "OrcaSlicer.conf"
        conf_file.write_text('{"test": "data"}')

        user_dir = backup_dir / "user"
        user_dir.mkdir()

        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orcaslicer",
            platform="linux",
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
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        # Create existing slicer config
        target_dir = tmp_path / "target" / "OrcaSlicer"
        target_dir.mkdir(parents=True)
        existing_conf = target_dir / "OrcaSlicer.conf"
        existing_conf.write_text('{"existing": true}')
        existing_user = target_dir / "user"
        existing_user.mkdir()

        def mock_get_slicer_info(slicer_type):
            from orca_backup.models.slicer import SlicerInfo

            return SlicerInfo(
                name=slicer_type,
                display_name="OrcaSlicer",
                config_path=target_dir,
                exists=True,
                conf_file=existing_conf,
                user_dir=existing_user,
            )

        # Mock create_backup to avoid actual backup
        backup_created = []

        def mock_create_backup(slicer, output_dir, compress, verify):
            backup_path = output_dir / "backup.zip"
            backup_path.write_text("mock backup")
            backup_created.append(backup_path)
            return backup_path

        monkeypatch.setattr(
            "orca_backup.core.restore.get_slicer_info", mock_get_slicer_info
        )
        monkeypatch.setattr("orca_backup.core.restore.verify_backup", lambda p, verbose=False: True)
        monkeypatch.setattr("orca_backup.core.restore.create_backup", mock_create_backup)

        restore_backup(backup_dir, backup_existing=True)

        # Verify backup was created
        assert len(backup_created) == 1
        captured = capsys.readouterr()
        assert "Creating backup of existing configuration" in captured.out

    def test_restore_missing_file_warning(self, tmp_path, monkeypatch, capsys):
        """Test warning when backup file is missing."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        # Manifest references file that doesn't exist
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

        target_dir = tmp_path / "target" / "OrcaSlicer"
        target_dir.mkdir(parents=True)

        def mock_get_slicer_info(slicer_type):
            from orca_backup.models.slicer import SlicerInfo

            return SlicerInfo(
                name=slicer_type,
                display_name="OrcaSlicer",
                config_path=target_dir,
                exists=True,
            )

        monkeypatch.setattr(
            "orca_backup.core.restore.get_slicer_info", mock_get_slicer_info
        )
        monkeypatch.setattr("orca_backup.core.restore.verify_backup", lambda p, verbose=False: True)

        success = restore_backup(backup_dir, backup_existing=False)

        # Should return False (not all files restored)
        assert success is False

        captured = capsys.readouterr()
        assert "WARNING: File not found in backup" in captured.out

    def test_restore_auto_detect_slicer(self, tmp_path, monkeypatch):
        """Test auto-detecting slicer type from manifest."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        conf_file = backup_dir / "OrcaSlicer.conf"
        conf_file.write_text('{"test": "data"}')

        manifest = BackupManifest(
            created_at=datetime.now(),
            slicer="orca-flashforge",  # Different slicer
            platform="linux",
            files=[
                FileEntry(
                    path="Orca-Flashforge.conf",
                    size=conf_file.stat().st_size,
                    sha256=calculate_sha256(conf_file),
                )
            ],
            total_files=1,
            total_size=conf_file.stat().st_size,
        )

        manifest_file = backup_dir / "backup_manifest.json"
        manifest_file.write_text(
            json.dumps(manifest.model_dump(mode="json"), default=str)
        )

        target_dir = tmp_path / "target" / "Orca-Flashforge"
        target_dir.mkdir(parents=True)

        called_with = []

        def mock_get_slicer_info(slicer_type):
            from orca_backup.models.slicer import SlicerInfo

            called_with.append(slicer_type)
            return SlicerInfo(
                name=slicer_type,
                display_name="Orca-Flashforge",
                config_path=target_dir,
                exists=True,
            )

        # Rename conf file to match manifest
        conf_file = conf_file.rename(backup_dir / "Orca-Flashforge.conf")

        monkeypatch.setattr(
            "orca_backup.core.restore.get_slicer_info", mock_get_slicer_info
        )
        monkeypatch.setattr("orca_backup.core.restore.verify_backup", lambda p, verbose=False: True)

        restore_backup(backup_dir, slicer_type=None, backup_existing=False)

        # Should have auto-detected orca-flashforge
        assert SlicerType.ORCA_FLASHFORGE in called_with
