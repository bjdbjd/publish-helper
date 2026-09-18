"""Tests for the hardened /api/getFile endpoint (src.api.startapi.api_get_file).

覆盖本次「文件鉴权加固」的路径边界检查：
- temp 目录内的有效文件可下载（200）；
- 前缀 lookalike 目录（temp_evil/...）、../ 穿越、绝对越权指向 temp 外 → 401；
- temp 根目录本身（非文件）→ 401；
- 缺失文件 → 404；缺少 filePath 参数 → 422。
"""

import os
from pathlib import Path

import pytest

# import 会加载 Flask app 与全局 config 单例
from src.api.startapi import api, config


@pytest.fixture
def client(tmp_path, monkeypatch):
    """把 api_get_file 的边界基准 config.TEMP_DIR 指向 tmp_path，避免触碰真实 temp/。"""
    monkeypatch.setattr(config, "TEMP_DIR", tmp_path)
    return api.test_client()


def _make_temp_file(tmp_path, name="movie.txt", content="hello"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_download_file_inside_temp(tmp_path, client):
    f = _make_temp_file(tmp_path)
    resp = client.get(f"/api/getFile?filePath={f}")
    assert resp.status_code == 200
    assert resp.data == b"hello"


def test_prefix_lookalike_directory_denied(client, tmp_path):
    # 构造一个与 temp 同前缀的兄弟目录，验证字符串前缀绕过被拒绝
    sibling = tmp_path.with_name(tmp_path.name + "_evil")
    sibling.mkdir(exist_ok=True)
    (sibling / "movie.txt").write_text("x", encoding="utf-8")
    resp = client.get(f"/api/getFile?filePath={sibling / 'movie.txt'}")
    assert resp.status_code == 401


def test_traversal_to_parent_denied(client, tmp_path):
    # ../ 穿越到 temp 的父目录
    parent_file = tmp_path.parent / "outside.txt"
    parent_file.write_text("secret", encoding="utf-8")
    traversed = os.path.normpath(str(tmp_path / ".." / "outside.txt"))
    resp = client.get(f"/api/getFile?filePath={traversed}")
    assert resp.status_code == 401
    parent_file.unlink()


def test_absolute_path_outside_temp_denied(client, tmp_path):
    outside = tmp_path.parent / "abs_outside.txt"
    outside.write_text("secret", encoding="utf-8")
    resp = client.get(f"/api/getFile?filePath={outside}")
    assert resp.status_code == 401
    outside.unlink()


def test_temp_root_itself_denied(client, tmp_path):
    # temp 根是目录非文件，边界检查应 401（strictly below）
    resp = client.get(f"/api/getFile?filePath={tmp_path}")
    assert resp.status_code == 401


def test_missing_file_inside_temp_404(client, tmp_path):
    resp = client.get(f"/api/getFile?filePath={tmp_path / 'nope.txt'}")
    assert resp.status_code == 404


def test_missing_filepath_param_422(client):
    resp = client.get("/api/getFile")
    assert resp.status_code == 422


def test_symlink_escape_denied(tmp_path, client):
    # temp 内一个指向 temp 外文件的软链，resolve 后应被拒
    if not hasattr(os, "symlink"):
        pytest.skip("platform without symlink support")
    tmp_path_str = str(tmp_path)
    outside = tmp_path.parent / "real_secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        os.symlink(str(outside), str(link))
    except OSError:
        pytest.skip("cannot create symlink")
    resp = client.get(f"/api/getFile?filePath={link}")
    assert resp.status_code == 401
    outside.unlink()
    if link.exists():
        link.unlink()
