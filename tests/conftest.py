"""Shared fixtures for core-module tests.

为 src/core/* 全面测试提供隔离基础设施：
- settings 隔离：把目标模块里的 get_settings 重定向到临时 settings 文件，不污染真实 static/settings.json；
- cwd 隔离：combine_directories 基于 os.getcwd()，chdir 到 tmp 防止写回真实 static/；
- MediaInfo：伪 track 对象，避免依赖真实 pymediainfo 解析文件；
- requests：伪 Response 对象，供 ptgen/picturebed/poster 网络 mock。
"""

import json
from types import SimpleNamespace

import pytest

from src.core.settings_tool import SettingsManager


@pytest.fixture
def settings_file(tmp_path):
    """A temporary settings file path (uninitialized)."""
    return tmp_path / "settings.json"


@pytest.fixture
def manager(settings_file):
    """A SettingsManager pointed at a temp settings file."""
    return SettingsManager(settings_file)


@pytest.fixture
def mock_settings(monkeypatch, tmp_path):
    """Redirect src.core.<mod>.get_settings to a temp-backed SettingsManager。

    用法: 需在函数签名里声明 mock_settings，然后调用
          mock_settings.patch("src.core.rename")    # 注入 rename 命名空间
    之后 rename.get_settings(key) 读临时文件/默认值，不碰真实 settings.json。

    返回对象带两个方法:
        patch(module_path): 把该模块的 get_settings 换成临时版
        set(key, value): 更新临时 settings 里某个键
        get_defaults(): 临时 manager 的默认配置字典
    """
    m = SettingsManager(tmp_path / "unused.json")
    defaults = m._get_default_settings()

    class _MockSettings:
        def patch(self, module_path):
            mod = __import__(module_path, fromlist=["get_settings"])
            monkeypatch.setattr(mod, "get_settings", m.get_setting)

        def set(self, key, value):
            m.update_setting(key, value)

        def get_defaults(self):
            return dict(defaults)

    return _MockSettings()


@pytest.fixture
def chdir_to_tmp(tmp_path, monkeypatch):
    """Change cwd to tmp so combine_directories() lands in tmp, not real static/."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def write_static(tmp_path, chdir_to_tmp):
    """Write a JSON file under tmp_path/static/<name> (cwd-relative, isolated)."""
    def _write(name, data):
        static_dir = tmp_path / "static"
        static_dir.mkdir(parents=True, exist_ok=True)
        path = static_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(path)
    return _write


def make_track(track_type, **attrs):
    """Build a fake MediaInfo track object (SimpleNamespace) for unit tests.

    Attributes seen by get_video_info / get_media_info can be passed as kwargs,
    including list-valued ones like other_width, writing_library (plain str), etc.
    """
    return SimpleNamespace(track_type=track_type, **attrs)


@pytest.fixture
def fake_mediainfo(monkeypatch):
    """Monkeypatch src.core.rename.MediaInfo.parse to return a fake object.

    fake tracks are supplied via the fixture's `tracks` attribute:
        fake_mediainfo.tracks = [make_track('Video', other_width=['1920'], ...), ...]
    Also the fake object exposes .to_json() as used by get_media_info.
    """
    import src.core.rename as rename_mod
    import src.core.mediainfo as mediainfo_mod

    class _FakeMediaInfo:
        def __init__(self):
            self.tracks = []
            self._json = None

        def to_json(self):
            return json.dumps({'tracks': [t.__dict__ for t in self.tracks]})

        def parse(self, path):
            return self

    fake = _FakeMediaInfo()

    def _fake_parse(*args, **kwargs):
        return fake

    monkeypatch.setattr(rename_mod.MediaInfo, "parse", staticmethod(_fake_parse))
    monkeypatch.setattr(mediainfo_mod.MediaInfo, "parse", staticmethod(_fake_parse))
    return fake


class FakeResponse:
    """A requests-like response for mocking network calls."""
    def __init__(self, status_code=200, text="", json_data=None, content=b""):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data
        self.content = content
        self.headers = {}
        self.url = ""

    def json(self):
        if self._json_data is not None:
            return self._json_data
        raise ValueError("no json body set")

    def iter_content(self, chunk_size=8192):
        # chunk the content bytes
        data = self.content
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")