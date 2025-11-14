"""Unit tests for slicer detection."""

import json
from pathlib import Path

import pytest

from orca_backup.core.detector import (
    detect_slicers,
    extract_version,
    get_installed_slicers,
    get_slicer_info,
    get_slicer_paths,
)
from orca_backup.models.slicer import SlicerType


class TestGetSlicerPaths:
    """Tests for get_slicer_paths function."""

    @pytest.mark.parametrize("mock_platform", ["windows"], indirect=True)
    def test_windows_paths(self, mock_platform):
        """Test Windows slicer paths."""
        paths = get_slicer_paths()

        expected_base = Path.home() / "AppData" / "Roaming"
        assert paths["orcaslicer"] == expected_base / "OrcaSlicer"
        assert paths["orca-flashforge"] == expected_base / "Orca-Flashforge"

    @pytest.mark.parametrize("mock_platform", ["darwin"], indirect=True)
    def test_macos_paths(self, mock_platform):
        """Test macOS slicer paths."""
        paths = get_slicer_paths()

        expected_base = Path.home() / "Library" / "Application Support"
        assert paths["orcaslicer"] == expected_base / "OrcaSlicer"
        assert paths["orca-flashforge"] == expected_base / "Orca-Flashforge"

    @pytest.mark.parametrize("mock_platform", ["linux"], indirect=True)
    def test_linux_paths(self, mock_platform, monkeypatch):
        """Test Linux standard paths (no Flatpak)."""
        # Mock Flatpak path to not exist
        def mock_exists(self):
            return False

        monkeypatch.setattr(Path, "exists", mock_exists)

        paths = get_slicer_paths()

        expected_base = Path.home() / ".config"
        assert paths["orcaslicer"] == expected_base / "OrcaSlicer"
        assert paths["orca-flashforge"] == expected_base / "Orca-Flashforge"

    @pytest.mark.parametrize("mock_platform", ["linux"], indirect=True)
    def test_linux_flatpak_paths(self, mock_platform, monkeypatch, tmp_path):
        """Test Linux Flatpak detection."""
        # Create Flatpak directory structure
        flatpak_path = (
            tmp_path
            / ".var"
            / "app"
            / "io.github.softfever.OrcaSlicer"
            / "config"
            / "OrcaSlicer"
        )
        flatpak_path.mkdir(parents=True)

        # Mock Path.home() to return tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        paths = get_slicer_paths()

        assert paths["orcaslicer"] == flatpak_path
        assert paths["orca-flashforge"] == tmp_path / ".config" / "Orca-Flashforge"

    def test_unsupported_platform(self, monkeypatch):
        """Test that unsupported platform raises RuntimeError."""
        monkeypatch.setattr("platform.system", lambda: "FreeBSD")

        with pytest.raises(RuntimeError, match="Unsupported platform"):
            get_slicer_paths()


class TestExtractVersion:
    """Tests for extract_version function."""

    def test_extract_from_header(self, tmp_path, sample_conf_content):
        """Test extracting version from header field."""
        conf_file = tmp_path / "test.conf"
        conf_file.write_text(json.dumps(sample_conf_content))

        version = extract_version(conf_file)

        assert version == "2.1.0-beta"

    def test_extract_from_app_version(self, tmp_path):
        """Test extracting version from app.version field."""
        conf_content = {
            "app": {"version": "1.9.0", "name": "OrcaSlicer"},
            "settings": {},
        }
        conf_file = tmp_path / "test.conf"
        conf_file.write_text(json.dumps(conf_content))

        version = extract_version(conf_file)

        assert version == "1.9.0"

    def test_extract_version_with_beta(self, tmp_path):
        """Test extracting version with beta suffix."""
        conf_content = {"header": "OrcaSlicer 2.3.1-beta", "app": {}}
        conf_file = tmp_path / "test.conf"
        conf_file.write_text(json.dumps(conf_content))

        version = extract_version(conf_file)

        assert version == "2.3.1-beta"

    def test_extract_version_with_alpha(self, tmp_path):
        """Test extracting version with alpha suffix."""
        conf_content = {"header": "OrcaSlicer 3.0.0-alpha", "app": {}}
        conf_file = tmp_path / "test.conf"
        conf_file.write_text(json.dumps(conf_content))

        version = extract_version(conf_file)

        assert version == "3.0.0-alpha"

    def test_missing_version_returns_none(self, tmp_path):
        """Test that missing version returns None."""
        conf_content = {"settings": {}, "presets": {}}
        conf_file = tmp_path / "test.conf"
        conf_file.write_text(json.dumps(conf_content))

        version = extract_version(conf_file)

        assert version is None

    def test_invalid_json_returns_none(self, tmp_path):
        """Test that invalid JSON returns None."""
        conf_file = tmp_path / "test.conf"
        conf_file.write_text("This is not valid JSON {{{")

        version = extract_version(conf_file)

        assert version is None

    def test_nonexistent_file_returns_none(self, tmp_path):
        """Test that non-existent file returns None."""
        conf_file = tmp_path / "nonexistent.conf"

        version = extract_version(conf_file)

        assert version is None

    def test_non_json_content_returns_none(self, tmp_path):
        """Test that non-JSON content returns None."""
        conf_file = tmp_path / "test.conf"
        conf_file.write_text("Just plain text, not JSON")

        version = extract_version(conf_file)

        assert version is None

    def test_json_with_md5_checksum(self, tmp_path):
        """Test parsing JSON with MD5 checksum line."""
        conf_content = {
            "header": "OrcaSlicer 2.1.0",
            "app": {"version": "2.1.0"},
        }
        # Add MD5 checksum line (common in actual config files)
        conf_text = json.dumps(conf_content) + "\n# MD5:abc123def456"
        conf_file = tmp_path / "test.conf"
        conf_file.write_text(conf_text)

        version = extract_version(conf_file)

        assert version == "2.1.0"


class TestGetSlicerInfo:
    """Tests for get_slicer_info function."""

    def test_orcaslicer_installed(self, temp_slicer_config, monkeypatch):
        """Test detecting installed OrcaSlicer."""
        config_path, conf_file, user_dir = temp_slicer_config

        # Mock get_slicer_paths to return our test paths
        def mock_paths():
            return {
                "orcaslicer": config_path,
                "orca-flashforge": config_path.parent / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        slicer = get_slicer_info(SlicerType.ORCASLICER)

        assert slicer.name == "orcaslicer"
        assert slicer.display_name == "OrcaSlicer"
        assert slicer.config_path == config_path
        assert slicer.exists is True
        assert slicer.conf_file == conf_file
        assert slicer.user_dir == user_dir
        assert slicer.version == "2.1.0-beta"

    def test_orca_flashforge_with_custom_scripts(
        self, temp_flashforge_config, monkeypatch
    ):
        """Test detecting Orca-Flashforge with custom scripts."""
        config_path, conf_file, user_dir = temp_flashforge_config

        def mock_paths():
            return {
                "orcaslicer": config_path.parent / "OrcaSlicer",
                "orca-flashforge": config_path,
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        slicer = get_slicer_info(SlicerType.ORCA_FLASHFORGE)

        assert slicer.name == "orca-flashforge"
        assert slicer.display_name == "Orca-Flashforge"
        assert slicer.custom_scripts_dir is not None
        assert slicer.custom_scripts_dir.exists()

    def test_slicer_not_installed(self, tmp_path, monkeypatch):
        """Test detecting non-existent slicer."""
        nonexistent_path = tmp_path / "NonExistent"

        def mock_paths():
            return {
                "orcaslicer": nonexistent_path,
                "orca-flashforge": tmp_path / "OrcaFlashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        slicer = get_slicer_info(SlicerType.ORCASLICER)

        assert slicer.exists is False
        assert slicer.conf_file is None
        assert slicer.user_dir is None
        assert slicer.version is None

    def test_custom_scripts_dir_absent(self, temp_slicer_config, monkeypatch):
        """Test that custom_scripts_dir is None if it doesn't exist."""
        config_path, _, _ = temp_slicer_config

        def mock_paths():
            return {
                "orcaslicer": config_path,
                "orca-flashforge": config_path.parent / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        slicer = get_slicer_info(SlicerType.ORCASLICER)

        # OrcaSlicer doesn't have custom_scripts by default
        assert slicer.custom_scripts_dir is None

    def test_missing_conf_file(self, tmp_path, monkeypatch):
        """Test slicer with missing conf file."""
        config_path = tmp_path / "OrcaSlicer"
        config_path.mkdir()
        user_dir = config_path / "user"
        user_dir.mkdir()
        # No conf file created

        def mock_paths():
            return {
                "orcaslicer": config_path,
                "orca-flashforge": tmp_path / "Orca-Flashforge",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        slicer = get_slicer_info(SlicerType.ORCASLICER)

        assert slicer.exists is True
        assert slicer.conf_file is None
        assert slicer.user_dir == user_dir


class TestDetectSlicers:
    """Tests for detect_slicers function."""

    def test_detect_all_slicers(self):
        """Test that detect_slicers returns info for all slicer types."""
        slicers = detect_slicers()

        assert len(slicers) == 2
        slicer_names = [s.name for s in slicers]
        assert "orcaslicer" in slicer_names
        assert "orca-flashforge" in slicer_names

    def test_detect_returns_slicer_info_objects(self):
        """Test that detect_slicers returns SlicerInfo objects."""
        slicers = detect_slicers()

        for slicer in slicers:
            assert hasattr(slicer, "name")
            assert hasattr(slicer, "display_name")
            assert hasattr(slicer, "config_path")
            assert hasattr(slicer, "exists")


class TestGetInstalledSlicers:
    """Tests for get_installed_slicers function."""

    def test_filters_only_valid_slicers(self, temp_slicer_config, monkeypatch):
        """Test that only valid slicers are returned."""
        config_path, _, _ = temp_slicer_config

        def mock_paths():
            return {
                "orcaslicer": config_path,  # Valid
                "orca-flashforge": config_path.parent / "NonExistent",  # Invalid
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        installed = get_installed_slicers()

        assert len(installed) == 1
        assert installed[0].name == "orcaslicer"
        assert installed[0].is_valid() is True

    def test_no_installed_slicers(self, tmp_path, monkeypatch):
        """Test when no slicers are installed."""

        def mock_paths():
            return {
                "orcaslicer": tmp_path / "NonExistent1",
                "orca-flashforge": tmp_path / "NonExistent2",
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        installed = get_installed_slicers()

        assert len(installed) == 0

    def test_all_slicers_installed(
        self, temp_slicer_config, temp_flashforge_config, monkeypatch
    ):
        """Test when all slicers are installed."""
        orca_path, _, _ = temp_slicer_config
        flash_path, _, _ = temp_flashforge_config

        def mock_paths():
            return {
                "orcaslicer": orca_path,
                "orca-flashforge": flash_path,
            }

        monkeypatch.setattr("orca_backup.core.detector.get_slicer_paths", mock_paths)

        installed = get_installed_slicers()

        assert len(installed) == 2
        names = [s.name for s in installed]
        assert "orcaslicer" in names
        assert "orca-flashforge" in names
