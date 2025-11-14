"""Integration tests for CLI commands."""

import pytest

from orca_backup.cli import app
from orca_backup.models.slicer import SlicerType


class TestListCommand:
    """Tests for 'list' CLI command."""

    def test_list_no_slicers(self, cli_runner, tmp_path, monkeypatch):
        """Test list command when no slicers are found."""

        def mock_paths():
            return {
                "orcaslicer": tmp_path / "NonExistent1",
                "orca-flashforge": tmp_path / "NonExistent2",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        result = cli_runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "0/2" in result.stdout

    def test_list_with_slicers(self, cli_runner, temp_slicer_config, monkeypatch):
        """Test list command with installed slicers."""
        config_path, _, _ = temp_slicer_config

        def mock_paths():
            return {
                "orcaslicer": config_path,
                "orca-flashforge": config_path.parent / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        result = cli_runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "OrcaSlicer" in result.stdout
        assert "1/2" in result.stdout


class TestBackupCommand:
    """Tests for 'backup' CLI command."""

    def test_backup_single_slicer(
        self, cli_runner, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test backing up a single slicer."""
        config_path, _, _ = temp_slicer_config
        output_dir = tmp_path / "backups"

        def mock_paths():
            return {
                "orcaslicer": config_path,
                "orca-flashforge": config_path.parent / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        result = cli_runner.invoke(
            app, ["backup", "--slicer", "orcaslicer", "--output", str(output_dir)]
        )

        assert result.exit_code == 0
        assert "Backup created successfully" in result.stdout
        assert output_dir.exists()

    def test_backup_all_slicers(
        self,
        cli_runner,
        temp_slicer_config,
        temp_flashforge_config,
        tmp_path,
        monkeypatch,
    ):
        """Test backing up all installed slicers."""
        orca_path, _, _ = temp_slicer_config
        flash_path, _, _ = temp_flashforge_config
        output_dir = tmp_path / "backups"

        def mock_paths():
            return {
                "orcaslicer": orca_path,
                "orca-flashforge": flash_path,
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        result = cli_runner.invoke(
            app, ["backup", "--slicer", "all", "--output", str(output_dir)]
        )

        assert result.exit_code == 0
        assert "OrcaSlicer" in result.stdout
        assert "Orca-Flashforge" in result.stdout

    def test_backup_no_compress(
        self, cli_runner, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test creating uncompressed backup."""
        config_path, _, _ = temp_slicer_config
        output_dir = tmp_path / "backups"

        def mock_paths():
            return {
                "orcaslicer": config_path,
                "orca-flashforge": config_path.parent / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        result = cli_runner.invoke(
            app,
            [
                "backup",
                "--slicer",
                "orcaslicer",
                "--output",
                str(output_dir),
                "--no-compress",
            ],
        )

        assert result.exit_code == 0
        # Should create directory, not ZIP
        backups = list(output_dir.iterdir())
        assert len(backups) > 0
        assert backups[0].is_dir()

    def test_backup_no_verify(
        self, cli_runner, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test backup without verification."""
        config_path, _, _ = temp_slicer_config
        output_dir = tmp_path / "backups"

        def mock_paths():
            return {
                "orcaslicer": config_path,
                "orca-flashforge": config_path.parent / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        result = cli_runner.invoke(
            app,
            [
                "backup",
                "--slicer",
                "orcaslicer",
                "--output",
                str(output_dir),
                "--no-verify",
            ],
        )

        assert result.exit_code == 0

    def test_backup_invalid_slicer(self, cli_runner, tmp_path):
        """Test backup with invalid slicer name."""
        result = cli_runner.invoke(
            app, ["backup", "--slicer", "invalid-slicer", "--output", str(tmp_path)]
        )

        assert result.exit_code == 1
        assert "ERROR" in result.stdout

    def test_backup_slicer_not_found(self, cli_runner, tmp_path, monkeypatch):
        """Test backup when slicer is not found."""

        def mock_paths():
            return {
                "orcaslicer": tmp_path / "NonExistent",
                "orca-flashforge": tmp_path / "NonExistent2",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        result = cli_runner.invoke(
            app, ["backup", "--slicer", "orcaslicer", "--output", str(tmp_path)]
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_backup_all_no_slicers(self, cli_runner, tmp_path, monkeypatch):
        """Test backup all when no slicers are installed."""

        def mock_paths():
            return {
                "orcaslicer": tmp_path / "NonExistent",
                "orca-flashforge": tmp_path / "NonExistent2",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        result = cli_runner.invoke(
            app, ["backup", "--slicer", "all", "--output", str(tmp_path)]
        )

        assert result.exit_code == 1
        assert "No installed slicers found" in result.stdout

    def test_backup_verbose(
        self, cli_runner, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test backup with verbose output."""
        config_path, _, _ = temp_slicer_config
        output_dir = tmp_path / "backups"

        def mock_paths():
            return {
                "orcaslicer": config_path,
                "orca-flashforge": config_path.parent / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        result = cli_runner.invoke(
            app,
            [
                "backup",
                "--slicer",
                "orcaslicer",
                "--output",
                str(output_dir),
                "--verbose",
            ],
        )

        assert result.exit_code == 0
        assert "Location:" in result.stdout
        assert "Version:" in result.stdout


class TestRestoreCommand:
    """Tests for 'restore' CLI command."""

    def test_restore_from_backup(
        self, cli_runner, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test restoring from a backup."""
        source_path, _, _ = temp_slicer_config

        # Create backup first
        def mock_paths_backup():
            return {
                "orcaslicer": source_path,
                "orca-flashforge": source_path.parent / "Orca-Flashforge",
            }

        monkeypatch.setattr(
            "orca_backup.core.detector.get_slicer_paths", mock_paths_backup
        )

        from orca_backup.core.backup import create_backup
        from orca_backup.core.detector import get_slicer_info

        slicer = get_slicer_info(SlicerType.ORCASLICER)
        backup_path = create_backup(
            slicer, tmp_path / "backups", compress=True, verify=True
        )

        # Create target for restore
        target_path = tmp_path / "restored" / "OrcaSlicer"
        target_path.mkdir(parents=True)

        def mock_paths_restore():
            return {
                "orcaslicer": target_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr(
            "orca_backup.core.detector.get_slicer_paths", mock_paths_restore
        )

        result = cli_runner.invoke(
            app, ["restore", str(backup_path), "--no-backup"]
        )

        assert result.exit_code == 0
        assert "Restore completed successfully" in result.stdout

    def test_restore_dry_run(
        self, cli_runner, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test restore with dry-run flag."""
        source_path, _, _ = temp_slicer_config

        def mock_paths():
            return {
                "orcaslicer": source_path,
                "orca-flashforge": source_path.parent / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        from orca_backup.core.backup import create_backup
        from orca_backup.core.detector import get_slicer_info

        slicer = get_slicer_info(SlicerType.ORCASLICER)
        backup_path = create_backup(
            slicer, tmp_path / "backups", compress=True, verify=True
        )

        result = cli_runner.invoke(
            app, ["restore", str(backup_path), "--dry-run"]
        )

        assert result.exit_code == 0
        assert "dry run" in result.stdout.lower()

    def test_restore_nonexistent_backup(self, cli_runner, tmp_path):
        """Test restore with non-existent backup."""
        nonexistent = tmp_path / "nonexistent.zip"

        result = cli_runner.invoke(app, ["restore", str(nonexistent)])

        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestVerifyCommand:
    """Tests for 'verify' CLI command."""

    def test_verify_valid_backup(
        self, cli_runner, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test verifying a valid backup."""
        config_path, _, _ = temp_slicer_config

        def mock_paths():
            return {
                "orcaslicer": config_path,
                "orca-flashforge": config_path.parent / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        from orca_backup.core.backup import create_backup
        from orca_backup.core.detector import get_slicer_info

        slicer = get_slicer_info(SlicerType.ORCASLICER)
        backup_path = create_backup(
            slicer, tmp_path / "backups", compress=True, verify=True
        )

        result = cli_runner.invoke(app, ["verify", str(backup_path)])

        assert result.exit_code == 0
        assert "verification passed" in result.stdout.lower()

    def test_verify_invalid_backup(self, cli_runner, tmp_path):
        """Test verifying an invalid backup."""
        invalid_backup = tmp_path / "invalid.zip"
        invalid_backup.write_bytes(b"Not a valid backup")

        result = cli_runner.invoke(app, ["verify", str(invalid_backup)])

        assert result.exit_code == 1

    def test_verify_nonexistent_backup(self, cli_runner, tmp_path):
        """Test verifying non-existent backup."""
        nonexistent = tmp_path / "nonexistent.zip"

        result = cli_runner.invoke(app, ["verify", str(nonexistent)])

        assert result.exit_code == 1


class TestInfoCommand:
    """Tests for 'info' CLI command."""

    def test_info_valid_backup(
        self, cli_runner, temp_slicer_config, tmp_path, monkeypatch
    ):
        """Test displaying info for valid backup."""
        config_path, _, _ = temp_slicer_config

        def mock_paths():
            return {
                "orcaslicer": config_path,
                "orca-flashforge": config_path.parent / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        from orca_backup.core.backup import create_backup
        from orca_backup.core.detector import get_slicer_info

        slicer = get_slicer_info(SlicerType.ORCASLICER)
        backup_path = create_backup(
            slicer, tmp_path / "backups", compress=True, verify=True
        )

        result = cli_runner.invoke(app, ["info", str(backup_path)])

        assert result.exit_code == 0
        assert "Backup Information" in result.stdout
        assert "Slicer" in result.stdout
        assert "Total Files" in result.stdout

    def test_info_invalid_backup(self, cli_runner, tmp_path):
        """Test info command with invalid backup."""
        invalid_backup = tmp_path / "invalid"
        invalid_backup.mkdir()

        result = cli_runner.invoke(app, ["info", str(invalid_backup)])

        assert result.exit_code == 1

    def test_info_nonexistent_backup(self, cli_runner, tmp_path):
        """Test info command with non-existent backup."""
        nonexistent = tmp_path / "nonexistent.zip"

        result = cli_runner.invoke(app, ["info", str(nonexistent)])

        assert result.exit_code == 1


class TestVersionCommand:
    """Tests for 'version' CLI command."""

    def test_version_output(self, cli_runner):
        """Test version command output."""
        result = cli_runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "orca-backup" in result.stdout
        assert "version" in result.stdout.lower()
