"""Tests for src.core.screenshot: screenshot extraction & thumbnail montage.

非确定性（random.sample、generate_image_filename 随机位）→ mock 固定源精确断言。
cv2/Image/np 全部 mock，不依赖真实视频文件。
"""

import random

import numpy as np
import pytest

from src.core import screenshot as scr
from src.core.screenshot import get_screenshot, get_thumbnail


class FakeCap:
    """Fake cv2.VideoCapture."""

    def __init__(self, opened=True, total_frames=1000, fps=25.0, frame_shape=(100, 100, 3)):
        self._opened = opened
        self._total = total_frames
        self._fps = fps
        self._shape = frame_shape
        self._pos = 0

    def isOpened(self):
        return self._opened

    def get(self, prop):
        import cv2 as _cv2
        if prop == _cv2.CAP_PROP_FRAME_COUNT:
            return self._total
        if prop == _cv2.CAP_PROP_FPS:
            return self._fps
        return 0

    def set(self, prop, val):
        self._pos = val
        return True

    def read(self):
        # 返回 (True, 确定性的 HxWxC ndarray)
        return True, np.full(self._shape, 128, dtype=np.uint8)

    def release(self):
        pass


@pytest.fixture
def cap(monkeypatch):
    def _factory(*args, **kwargs):
        return FakeCap(opened=True)
    monkeypatch.setattr("cv2.VideoCapture", _factory)
    return FakeCap


@pytest.fixture(autouse=True)
def quiet_cv2(monkeypatch):
    """Mock cv2.cvtColor + PIL Image.save 避免真实编解码依赖。"""
    monkeypatch.setattr("cv2.cvtColor", lambda img, code: img)
    import PIL.Image as _PILImage
    class _NoopImage:
        def __init__(self, arr):
            pass
        def save(self, path):
            pass
    monkeypatch.setattr(_PILImage, "fromarray", lambda arr: _NoopImage(arr))


@pytest.fixture
def fixed_random(monkeypatch):
    """Mock random.sample to return deterministic sequences."""
    def _set(seq):
        monkeypatch.setattr(random, "sample", lambda range_obj, k: list(seq))
    return _set


@pytest.fixture
def fixed_filename(monkeypatch, tmp_path):
    """Mock generate_image_filename to return deterministic paths under tmp."""
    def _make(base):
        return str(tmp_path / "shot.png")
    monkeypatch.setattr(scr, "generate_image_filename", _make)
    return tmp_path


class TestGetScreenshot:
    def test_success_returns_paths(self, cap, fixed_random, fixed_filename, tmp_path, monkeypatch):
        fixed_random([100, 200, 300])  # 3 timestamps
        ok, paths = get_screenshot(
            "/v.mp4", str(tmp_path), 3, 30.0, 0.1, 0.9,
        )
        assert ok is True
        assert len(paths) == 3
        assert all(p == str(tmp_path / "shot.png") for p in paths)

    def test_low_std_falls_back_to_random(self, cap, fixed_random, fixed_filename, tmp_path, monkeypatch):
        # np.std 极低 → 走随机帧兜底，仍返回 number 张
        monkeypatch.setattr(np, "std", lambda frame: 0.0)
        fixed_random([100, 200, 300])
        ok, paths = get_screenshot("/v.mp4", str(tmp_path), 3, 30.0, 0.1, 0.9)
        assert ok is True
        assert len(paths) == 3

    def test_sample_larger_than_population(self, cap, fixed_filename, tmp_path, monkeypatch):
        # start~end 范围近乎为 0 → random.sample 抛 ValueError → 兜底 '截图出错'
        ok, msg = get_screenshot("/v.mp4", str(tmp_path), 5, 30.0, 0.5, 0.50001)
        assert ok is False
        assert "截图出错" in msg[0]

    def test_cap_not_opened(self, monkeypatch, tmp_path):
        class _Closed(FakeCap):
            def __init__(self, *a, **kw):
                super().__init__(opened=False)
        monkeypatch.setattr("cv2.VideoCapture", lambda *a, **kw: _Closed())
        ok, msg = get_screenshot("/v.mp4", str(tmp_path), 3, 30.0, 0.1, 0.9)
        assert ok is False
        assert msg == ["无法加载视频"]

    def test_keyframe_acceptance(self, cap, fixed_random, fixed_filename, tmp_path, monkeypatch):
        # std 高且时间间隔满足 → 关键帧接受分支（L71-75），全部收集
        monkeypatch.setattr(np, "std", lambda frame: 100.0)  # > threshold 30
        fixed_random([100, 200, 300])  # times 4/8/12s, 间隔 4s > min_interval
        ok, paths = get_screenshot("/v.mp4", str(tmp_path), 3, 30.0, 0.1, 0.9)
        assert ok is True
        assert len(paths) == 3

    def test_interval_not_satisfied_fallback(self, cap, fixed_random, fixed_filename, tmp_path, monkeypatch):
        # 相邻 timestamps 间隔 < min_interval → 间隔不满足兜底（L86-93）
        monkeypatch.setattr(np, "std", lambda frame: 100.0)  # 高 std，但间隔不满足
        fixed_random([100, 101, 102])  # times 4.0/4.04/4.08s, 间隔 0.04s < 0.4s
        ok, paths = get_screenshot("/v.mp4", str(tmp_path), 3, 30.0, 0.1, 0.9)
        assert ok is True
        assert len(paths) == 3

    def test_mkdir_permission_error(self, tmp_path, monkeypatch):
        import os
        # 传入不存在的路径，触发 os.makedirs 分支
        target = str(tmp_path / "does_not_exist" / "sub")
        def _makedirs(*a, **kw):
            raise PermissionError()
        monkeypatch.setattr(os, "makedirs", _makedirs)
        ok, msg = get_screenshot("/v.mp4", target, 3, 30.0, 0.1, 0.9)
        assert ok is False
        assert msg == ["权限不足，无法创建目录"]

    def test_mkdir_file_exists_error(self, tmp_path, monkeypatch):
        import os
        target = str(tmp_path / "does_not_exist" / "sub")
        def _makedirs(*a, **kw):
            raise FileExistsError()
        monkeypatch.setattr(os, "makedirs", _makedirs)
        ok, msg = get_screenshot("/v.mp4", target, 3, 30.0, 0.1, 0.9)
        assert ok is False
        assert msg == ["路径已存在，且不是目录"]


class TestGetThumbnail:
    def test_success(self, cap, fixed_filename, tmp_path, monkeypatch):
        # 默认 3x3 网格，end>=frames 时 interval 为 0 可能导致重复帧 → 全读成功
        ok, path = get_thumbnail("/v.mp4", str(tmp_path), 3, 3, 0.1, 0.9)
        assert ok is True
        assert path == str(tmp_path / "shot.png")

    def test_empty_images_index_error(self, cap, fixed_filename, tmp_path, monkeypatch):
        # start==end → 循环立即 break → images 为空 → resized_images[0] 抛 IndexError，被兜底为 (False, str)
        ok, msg = get_thumbnail("/v.mp4", str(tmp_path), 3, 3, 0.5, 0.5)
        assert ok is False
        assert "list index out of range" in msg

    def test_cap_not_opened(self, monkeypatch, tmp_path):
        class _Closed(FakeCap):
            def __init__(self, *a, **kw):
                super().__init__(opened=False)
        monkeypatch.setattr("cv2.VideoCapture", lambda *a, **kw: _Closed())
        ok, msg = get_thumbnail("/v.mp4", str(tmp_path), 3, 3, 0.1, 0.9)
        assert ok is False
        assert "无法打开视频文件" in msg
