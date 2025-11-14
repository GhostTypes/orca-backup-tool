"""Shared pytest fixtures for orca-backup tests."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Tuple

import pytest
from typer.testing import CliRunner

from orca_backup.models.backup import BackupManifest, FileEntry
from orca_backup.models.slicer import SlicerInfo, SlicerType


@pytest.fixture
def cli_runner():
    """Typer CliRunner for CLI tests."""
    return CliRunner()


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_configs_dir(fixtures_dir):
    """Path to mock config files."""
    return fixtures_dir / "mock_configs"


@pytest.fixture
def temp_slicer_config(tmp_path, mock_configs_dir) -> Tuple[Path, Path, Path]:
    """
    Create a mock OrcaSlicer installation in temp directory.

    Returns:
        Tuple of (config_path, conf_file, user_dir)
    """
    config_path = tmp_path / "OrcaSlicer"
    config_path.mkdir()

    # Copy conf file
    conf_file = config_path / "OrcaSlicer.conf"
    shutil.copy2(mock_configs_dir / "OrcaSlicer.conf", conf_file)

    # Copy user directory
    user_dir = config_path / "user"
    shutil.copytree(mock_configs_dir / "user", user_dir)

    return config_path, conf_file, user_dir


@pytest.fixture
def temp_flashforge_config(tmp_path, mock_configs_dir) -> Tuple[Path, Path, Path]:
    """
    Create a mock Orca-Flashforge installation in temp directory.

    Returns:
        Tuple of (config_path, conf_file, user_dir)
    """
    config_path = tmp_path / "Orca-Flashforge"
    config_path.mkdir()

    # Copy conf file
    conf_file = config_path / "Orca-Flashforge.conf"
    shutil.copy2(mock_configs_dir / "Orca-Flashforge.conf", conf_file)

    # Copy user directory
    user_dir = config_path / "user"
    shutil.copytree(mock_configs_dir / "user", user_dir)

    # Create custom_scripts directory
    custom_scripts_dir = config_path / "custom_scripts"
    custom_scripts_dir.mkdir()
    (custom_scripts_dir / "test_script.py").write_text("print('test')")

    return config_path, conf_file, user_dir


@pytest.fixture
def sample_slicer_info(temp_slicer_config) -> SlicerInfo:
    """Create a sample SlicerInfo object."""
    config_path, conf_file, user_dir = temp_slicer_config

    return SlicerInfo(
        name=SlicerType.ORCASLICER,
        display_name="OrcaSlicer",
        config_path=config_path,
        exists=True,
        version="2.1.0-beta",
        conf_file=conf_file,
        user_dir=user_dir,
        custom_scripts_dir=None,
    )


@pytest.fixture
def sample_flashforge_info(temp_flashforge_config) -> SlicerInfo:
    """Create a sample Orca-Flashforge SlicerInfo object."""
    config_path, conf_file, user_dir = temp_flashforge_config
    custom_scripts_dir = config_path / "custom_scripts"

    return SlicerInfo(
        name=SlicerType.ORCA_FLASHFORGE,
        display_name="Orca-Flashforge",
        config_path=config_path,
        exists=True,
        version="1.9.0",
        conf_file=conf_file,
        user_dir=user_dir,
        custom_scripts_dir=custom_scripts_dir,
    )


@pytest.fixture
def sample_file_entries() -> list:
    """Create sample FileEntry objects."""
    return [
        FileEntry(
            path="OrcaSlicer.conf",
            size=1024,
            sha256="a" * 64,
        ),
        FileEntry(
            path="user/filament/custom_pla.json",
            size=256,
            sha256="b" * 64,
        ),
        FileEntry(
            path="user/process/custom_profile.json",
            size=512,
            sha256="c" * 64,
        ),
    ]


@pytest.fixture
def sample_backup_manifest(sample_file_entries) -> BackupManifest:
    """Create a sample BackupManifest object."""
    return BackupManifest(
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


@pytest.fixture
def sample_conf_content():
    """Sample OrcaSlicer.conf JSON content."""
    return {
        "header": "OrcaSlicer 2.1.0-beta",
        "app": {
            "version": "2.1.0-beta",
            "name": "OrcaSlicer"
        },
        "recent_files": ["/home/user/models/test.3mf"],
        "presets": {
            "filament": "Generic PLA",
            "print": "0.20mm OPTIMAL",
            "printer": "Creality Ender-3"
        }
    }


@pytest.fixture
def mock_platform(monkeypatch, request):
    """
    Mock platform.system() for testing different platforms.

    Usage:
        @pytest.mark.parametrize("mock_platform", ["windows", "darwin", "linux"], indirect=True)
    """
    system = request.param if hasattr(request, "param") else "linux"

    system_map = {
        "windows": "Windows",
        "darwin": "Darwin",
        "linux": "Linux",
    }

    monkeypatch.setattr("platform.system", lambda: system_map[system])
    return system


@pytest.fixture
def create_test_files(tmp_path):
    """
    Factory fixture to create test files with specific content.

    Usage:
        files = create_test_files([
            ("file1.txt", "content1"),
            ("dir/file2.txt", "content2"),
        ])
    """
    def _create_files(file_specs):
        """
        Create test files.

        Args:
            file_specs: List of (path, content) tuples

        Returns:
            List of created file paths
        """
        created_files = []
        for path_str, content in file_specs:
            file_path = tmp_path / path_str
            file_path.parent.mkdir(parents=True, exist_ok=True)

            if isinstance(content, bytes):
                file_path.write_bytes(content)
            else:
                file_path.write_text(content)

            created_files.append(file_path)

        return created_files

    return _create_files
