"""Tests for the unified settings system (src.core.settings_tool).

覆盖本次重构引入的行为：
- 双套 settings 合并后，SettingsManager 是唯一实现；
- 布尔型设置从字符串 'True'/'False'/'' 归一为真 bool；
- _get_default_settings 里的布尔键已经是真 bool。
"""

import json

import pytest

from src.core.settings_tool import SettingsManager


@pytest.fixture
def settings_file(tmp_path):
    """Create a temporary settings file path (uninitialized)."""
    return tmp_path / "sub" / "settings.json"


@pytest.fixture
def manager(settings_file):
    """A SettingsManager pointed at a temp file."""
    return SettingsManager(settings_file)


def _write(settings_file, data):
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class TestBooleanNormalization:
    """布尔型设置读取归一为真 bool。"""

    def test_legacy_string_true_normalized_to_bool(self, settings_file, monkeypatch):
        _write(
            settings_file,
            {
                "auto_upload_screenshot": "True",
                "rename_file": "True",
                "make_dir": "False",
            },
        )
        m = SettingsManager(settings_file)
        # 旧格式字符串 'True'/'False' → 真 bool
        assert m.get_setting("auto_upload_screenshot") is True
        assert m.get_setting("rename_file") is True
        assert m.get_setting("make_dir") is False

    def test_empty_string_means_false(self, settings_file):
        # GUI 保存未勾选状态时写入空串 ''，应归一为 False
        _write(settings_file, {"enable_api": "", "delete_screenshot": ""})
        m = SettingsManager(settings_file)
        assert m.get_setting("enable_api") is False
        assert m.get_setting("delete_screenshot") is False

    def test_real_bool_passthrough(self, settings_file):
        # 新格式已是真 bool，原样返回
        _write(settings_file, {"open_auto_feed_link": True, "create_hard_link": False})
        m = SettingsManager(settings_file)
        assert m.get_setting("open_auto_feed_link") is True
        assert m.get_setting("create_hard_link") is False

    def test_non_bool_key_stays_string(self, settings_file):
        # 非布尔键（如 URL、数值字符串）不做 bool 归一
        _write(settings_file, {"pt_gen_api_url": "https://ptgen.agsvpt.work/"})
        m = SettingsManager(settings_file)
        assert m.get_setting("pt_gen_api_url") == "https://ptgen.agsvpt.work/"


class TestDefaultSettings:
    """_get_default_settings 的布尔键应为真 bool。"""

    def test_boolean_defaults_are_real_bools(self, settings_file):
        m = SettingsManager(settings_file)
        defaults = m._get_default_settings()
        bool_keys = [
            "enable_api",
            "auto_upload_screenshot",
            "paste_screenshot_url",
            "delete_screenshot",
            "auto_download_upload_poster",
            "do_get_thumbnail",
            "media_info_suffix",
            "make_dir",
            "rename_file",
            "create_hard_link",
            "second_confirm_file_name",
            "open_auto_feed_link",
        ]
        for key in bool_keys:
            assert isinstance(defaults[key], bool), f"{key} 应为 bool，实为 {type(defaults[key])}"

    def test_pt_gen_default_points_to_new_service(self, settings_file):
        m = SettingsManager(settings_file)
        defaults = m._get_default_settings()
        assert defaults["pt_gen_api_url"] == "https://pt-gen.hares.dpdns.org/api/getData"
        assert defaults["pt_gen_auth_secret"] == "hares.23663"


class TestSettingsMergedBehavior:
    """合并后 SettingsManager 仍是唯一实现（通过 tool.py 的 re-export 使用之间接）。"""

    def test_get_setting_default_fallback(self, manager):
        # 文件被创建（含默认值）
        assert manager.get_setting("api_port", "5000") == "15372"

    def test_update_setting_roundtrip(self, manager):
        manager.update_setting("test_key", "v1")
        assert manager.get_setting("test_key") == "v1"

    def test_legacy_template_key_migration(self, manager):
        manager.update_setting("test_tpl", "Template with {category}")
        assert "{categories}" in manager.get_setting("test_tpl")
        assert "{category}" not in manager.get_setting("test_tpl")

    def test_environment_variable_override(self, manager, monkeypatch):
        monkeypatch.setenv("API_PORT", "9999")
        assert manager.get_setting("api_port") == "9999"
