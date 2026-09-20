"""Tests for src.core.data: combo-box data, abbreviations, load_names.

cwd 隔离（chdir_to_tmp）防止写回真实 static/。
"""

import json

from src.core.data import (
    get_abbreviation,
    get_combo_box_data,
    load_names,
    update_combo_box_data,
)


class TestGetComboBoxData:
    def test_team_whitelist(self, tmp_path, chdir_to_tmp):
        ok, data = get_combo_box_data("team")
        assert ok is True
        assert isinstance(data, list)
        assert "AGSVWEB" in data

    def test_source(self, tmp_path, chdir_to_tmp):
        ok, data = get_combo_box_data("source")
        assert ok is True
        assert "WEB-DL" in data

    def test_playlet_source(self, tmp_path, chdir_to_tmp):
        ok, data = get_combo_box_data("playlet-source")
        assert ok is True
        assert "网络收费短剧" in data

    def test_creates_and_backfills_file(self, tmp_path, chdir_to_tmp):
        # 首次调用创建 static/combo-box-data.json；每个 key 是独立 default 子集
        get_combo_box_data("team")
        path = tmp_path / "static" / "combo-box-data.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "team" in data
        # 再请求 source 会把 source key 补进同一文件
        get_combo_box_data("source")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "source" in data


class TestUpdateComboBoxData:
    def test_newline_split_and_write(self, tmp_path, chdir_to_tmp):
        # update_combo_box_data 的 FileNotFoundError 分支 open-for-write 不建目录，需先建 static/
        (tmp_path / "static").mkdir(parents=True, exist_ok=True)
        ok, msg = update_combo_box_data("A\\nB\\nC", "team")
        assert ok is True
        path = tmp_path / "static" / "combo-box-data.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["team"] == ["A", "B", "C"]

    def test_file_missing_creates(self, tmp_path, chdir_to_tmp):
        (tmp_path / "static").mkdir(parents=True, exist_ok=True)
        ok, msg = update_combo_box_data("X", "team")
        assert ok is True
        assert "文件不存在，已创建新文件并更新" in msg


class TestGetAbbreviation:
    def test_hit_returns_abbreviation(self, tmp_path, chdir_to_tmp):
        assert get_abbreviation("3 840 pixels") == "2160p"

    def test_miss_returns_original(self, tmp_path, chdir_to_tmp):
        assert get_abbreviation("unknown string") == "unknown string"

    def test_min_widths_backfilled(self, tmp_path, chdir_to_tmp):
        get_abbreviation("3 840 pixels")
        path = tmp_path / "static" / "abbreviation.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "min_widths" in data


class TestLoadNames:
    def test_loads_named_list(self, tmp_path):
        f = tmp_path / "names.json"
        f.write_text(json.dumps({"a": ["x", "y"]}), encoding="utf-8")
        assert load_names(str(f), "a") == ["x", "y"]
