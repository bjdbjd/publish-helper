"""Tests for the load_or_initialize_json helper (src.utils.file_utils).

覆盖本次重构抽取的「不存在则用默认创建 → 读取 →（可选 backfill 补齐）写回」逻辑：
- 文件不存在：以 defaults 创建并返回副本；
- backfill=False（默认）：已存在文件只读，绝不改写；
- backfill=True：补齐缺失默认键并写回，保留原缩进；
- 文件损坏：抛 ValueError。
"""

import json

import pytest

from src.utils.file_utils import load_or_initialize_json


DEFAULTS = {"alpha": "a", "beta": "b"}


def test_creates_file_when_missing(tmp_path):
    path = tmp_path / "new.json"
    result = load_or_initialize_json(path, DEFAULTS)
    assert path.exists()
    assert result == DEFAULTS
    # 返回的是副本，改动不影响 defaults 源
    assert result is not DEFAULTS


def test_returns_copy_when_created(tmp_path):
    path = tmp_path / "x.json"
    out = load_or_initialize_json(path, DEFAULTS)
    out["alpha"] = "changed"
    assert DEFAULTS["alpha"] == "a"  # 源未被污染


def test_backfill_false_never_rewrites_existing(tmp_path):
    path = tmp_path / "existing.json"
    # 已存在且内容完整
    path.write_text(json.dumps(DEFAULTS), encoding="utf-8")
    before = path.read_bytes()
    result = load_or_initialize_json(path, DEFAULTS)  # backfill=False 默认
    assert result == DEFAULTS
    assert path.read_bytes() == before  # 字节级不变


def test_backfill_false_ignores_missing_keys(tmp_path):
    path = tmp_path / "partial.json"
    partial = {"alpha": "a"}
    path.write_text(json.dumps(partial), encoding="utf-8")
    before = path.read_bytes()
    result = load_or_initialize_json(path, DEFAULTS)  # 只读，不补 beta
    assert result == partial
    assert path.read_bytes() == before


def test_backfill_true_adds_missing_keys(tmp_path):
    path = tmp_path / "partial.json"
    path.write_text(json.dumps({"alpha": "a"}), encoding="utf-8")
    result = load_or_initialize_json(path, DEFAULTS, backfill=True)
    assert result == DEFAULTS  # beta 被补入
    assert json.loads(path.read_text(encoding="utf-8")) == DEFAULTS  # 已写回


def test_backfill_preserves_existing_values(tmp_path):
    path = tmp_path / "existing.json"
    # alpha 值已存在但不同于默认，backfill 不应覆盖已有值
    path.write_text(json.dumps({"alpha": "CUSTOM", "beta": "b"}), encoding="utf-8")
    result = load_or_initialize_json(path, DEFAULTS, backfill=True)
    assert result["alpha"] == "CUSTOM"
    assert result["beta"] == "b"


def test_backfill_true_preserves_indent(tmp_path):
    path = tmp_path / "two_space.json"
    path.write_text(json.dumps({"alpha": "a"}, indent=2), encoding="utf-8")
    load_or_initialize_json(path, DEFAULTS, backfill=True)
    # 探测到 2 空格缩进 → 写回后仍为 2 空格
    text = path.read_text(encoding="utf-8")
    assert "\n  " in text  # 2 空格缩进，而非 4
    assert "\n    " not in text


def test_backfill_true_raises_on_corrupt_file(tmp_path):
    path = tmp_path / "corrupt.json"
    path.write_text("{ not valid json !!", encoding="utf-8")
    with pytest.raises(ValueError):
        load_or_initialize_json(path, DEFAULTS, backfill=True)
