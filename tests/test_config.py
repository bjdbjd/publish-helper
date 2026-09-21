"""Test configuration module."""

import pytest
from pathlib import Path
from src.config.settings import Config
from src.core.settings_tool import SettingsManager


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary configuration directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def temp_settings_manager(temp_config_dir):
    """Create a settings manager with temporary directory."""
    settings_file = temp_config_dir / "settings.json"
    return SettingsManager(settings_file)


class TestConfig:
    """Test configuration class."""

    def test_config_initialization(self):
        """Test that config initializes properly."""
        config = Config()
        assert config.API_HOST == "0.0.0.0"
        assert config.API_PORT == 15372
        assert isinstance(config.BASE_DIR, Path)

    def test_directory_creation(self, tmp_path, monkeypatch):
        """Test that necessary directories are created."""
        # Mock the base directory
        mock_base = tmp_path / "test_app"

        with monkeypatch.context() as m:
            m.setenv("BASE_DIR", str(mock_base))
            config = Config()

        # Check that directories exist
        assert config.STATIC_DIR.exists()
        assert config.TEMP_DIR.exists()
        assert config.MEDIA_DIR.exists()
        assert config.LOGS_DIR.exists()


class TestSettingsManager:
    """Test settings manager."""

    def test_settings_manager_initialization(self, temp_settings_manager):
        """Test that settings manager initializes correctly."""
        assert temp_settings_manager.settings_file.exists()

    def test_get_setting(self, temp_settings_manager):
        """Test getting a setting value."""
        value = temp_settings_manager.get_setting("api_port", "5000")
        assert value == "15372"  # Default value

    def test_update_setting(self, temp_settings_manager):
        """Test updating a setting value."""
        temp_settings_manager.update_setting("test_key", "test_value")
        assert temp_settings_manager.get_setting("test_key") == "test_value"

    def test_environment_variable_override(self, temp_settings_manager, monkeypatch):
        """Test that environment variables override settings."""
        monkeypatch.setenv("API_PORT", "9999")
        value = temp_settings_manager.get_setting("api_port")
        assert value == "9999"

    def test_legacy_key_handling(self, temp_settings_manager):
        """Test legacy key compatibility."""
        temp_settings_manager.update_setting(
            "test_template", "Template with {category}"
        )
        value = temp_settings_manager.get_setting("test_template")
        assert "{categories}" in value
        assert "{category}" not in value


class TestConfigHelperMethods:
    """Test Config helper methods (get_temp_pic_dir/torrent_dir/is_development)."""

    def test_get_temp_pic_dir(self):
        from src.config import settings
        # BASE_DIR 硬编码为项目根（不读 env），改用现有配置单例
        assert settings.config.get_temp_pic_dir() == settings.config.TEMP_DIR / "pic"
        assert settings.config.get_temp_pic_dir().exists()

    def test_get_temp_torrent_dir(self):
        from src.config import settings
        assert settings.config.get_temp_torrent_dir() == settings.config.TEMP_DIR / "torrent"
        assert settings.config.get_temp_torrent_dir().exists()

    def test_is_development_default_false(self, monkeypatch):
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        from src.config import settings
        assert settings.config.is_development() is False

    def test_is_development_env(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        from src.config import settings
        assert settings.config.is_development() is True


class TestFrozenPackagingPaths:
    """打包（PyInstaller frozen）态的路径与首次运行播种。

    这套逻辑是 Windows/macOS 安装包能否正常工作的关键：
    onefile 模式下 __file__ 落在每次启动新建、退出即删的 _MEIPASS，
    若 BASE_DIR 指向它，用户设置与 media/logs 每次启动都会丢。
    """

    def test_dev_mode_base_is_project_root(self):
        """开发态 BASE_DIR 是项目根，且与 BUNDLE_DIR 相同。"""
        from src.config import settings
        assert settings.is_frozen() is False
        assert settings.config.BASE_DIR == settings.config.BUNDLE_DIR
        assert (settings.config.BASE_DIR / "src").is_dir()

    def test_get_writable_base_dir_dev(self):
        from src.config.settings import get_writable_base_dir
        base = get_writable_base_dir()
        assert base.name == "publish-helper"

    def test_frozen_uses_executable_dir_not_meipass(self, monkeypatch, tmp_path):
        """frozen 时 BASE_DIR 必须取 sys.executable 所在目录，而不是 _MEIPASS。"""
        from src.config import settings as settings_mod

        fake_exe_dir = tmp_path / "app"
        fake_exe_dir.mkdir()
        fake_meipass = tmp_path / "_mei12345"
        fake_meipass.mkdir()

        monkeypatch.setattr(settings_mod.sys, "frozen", True, raising=False)
        monkeypatch.setattr(settings_mod.sys, "executable", str(fake_exe_dir / "App.exe"))
        monkeypatch.setattr(settings_mod.sys, "_MEIPASS", str(fake_meipass), raising=False)

        assert settings_mod.is_frozen() is True
        assert settings_mod.get_writable_base_dir() == fake_exe_dir
        assert settings_mod.get_bundle_dir() == fake_meipass
        # 核心断言：可写根绝不等于临时解包目录
        assert settings_mod.get_writable_base_dir() != settings_mod.get_bundle_dir()

    def test_frozen_seeds_static_but_never_overwrites_settings(
        self, monkeypatch, tmp_path
    ):
        """首次运行播种 static/*；已存在的 settings.json 绝不被覆盖。"""
        from src.config import settings as settings_mod

        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        mei = tmp_path / "_mei"
        bundled_static = mei / "static"
        bundled_static.mkdir(parents=True)
        (bundled_static / "abbreviation.json").write_text("{}", encoding="utf-8")
        (bundled_static / "settings.json").write_text(
            '{"api_port": "15372"}', encoding="utf-8"
        )

        monkeypatch.setattr(settings_mod.sys, "frozen", True, raising=False)
        monkeypatch.setattr(settings_mod.sys, "executable", str(exe_dir / "App.exe"))
        monkeypatch.setattr(settings_mod.sys, "_MEIPASS", str(mei), raising=False)
        # 关键：Config() 在 frozen 态会 os.chdir(BASE_DIR)。必须交给 monkeypatch
        # 记录当前 cwd，否则 chdir 会泄漏到后续测试（曾导致 test_core_rename 里
        # abbreviation.json 按 cwd 找不到、bit_depth 未归一而失败）。
        monkeypatch.chdir(tmp_path)

        # 预置用户已改过的 settings.json
        target_static = exe_dir / "static"
        target_static.mkdir()
        (target_static / "settings.json").write_text(
            '{"api_port": "19999"}', encoding="utf-8"
        )

        cfg = settings_mod.Config()

        # 缺的补上
        assert (target_static / "abbreviation.json").exists()
        # 有的保留用户版本（升级不抹配置）
        assert "19999" in (target_static / "settings.json").read_text(encoding="utf-8")
        assert cfg.STATIC_DIR == target_static
        assert cfg.BASE_DIR == exe_dir

    def test_frozen_chdir_to_base_dir_only_when_frozen(self, monkeypatch, tmp_path):
        """frozen 时把 cwd 归一到 BASE_DIR（core 层多处按 cwd 读 static/）。"""
        from src.config import settings as settings_mod

        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        mei = tmp_path / "_mei"
        (mei / "static").mkdir(parents=True)

        monkeypatch.setattr(settings_mod.sys, "frozen", True, raising=False)
        monkeypatch.setattr(settings_mod.sys, "executable", str(exe_dir / "App.exe"))
        monkeypatch.setattr(settings_mod.sys, "_MEIPASS", str(mei), raising=False)
        monkeypatch.chdir(tmp_path.parent)

        settings_mod.Config()
        assert Path.cwd() == exe_dir

    def test_dev_mode_does_not_chdir(self, monkeypatch, tmp_path):
        """开发态不得改 cwd（会破坏依赖相对 cwd 的既有行为与测试夹具）。"""
        from src.config import settings as settings_mod

        monkeypatch.chdir(tmp_path)
        before = Path.cwd()
        settings_mod.Config()
        assert Path.cwd() == before


class TestVersionConsistency:
    """v2.0.0 发布前把三处版本号统一，防止再出现 2.0.0 / 1.4.5 并存。"""

    def test_all_three_version_sources_agree(self):
        import re
        from pathlib import Path

        import src.config as pkg
        from src.config.settings import Config

        root = Path(__file__).resolve().parents[1]
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
        assert m is not None, "pyproject.toml 缺 version"

        assert m.group(1) == pkg.__version__, "pyproject 与 config.__version__ 不一致"
        assert Config().GUI_VERSION == pkg.__version__, "GUI_VERSION 与 __version__ 不一致"


class TestImageHostConfig:
    def test_get_host_config(self):
        from src.config.settings import ImageHostConfig
        cfg = ImageHostConfig.get_host_config("freeimage")
        assert cfg["api_url"] == "https://freeimage.host/api/1/upload"

    def test_get_supported_hosts(self):
        from src.config.settings import ImageHostConfig
        hosts = ImageHostConfig.get_supported_hosts()
        assert "freeimage" in hosts
        assert "imgbb" in hosts
