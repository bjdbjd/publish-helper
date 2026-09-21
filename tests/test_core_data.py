"""Tests for src.core.data: combo-box data, abbreviations, load_names.

cwd 隔离（chdir_to_tmp）防止写回真实 static/。
"""

import json

import pytest

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
    def test_real_newline_is_split(self, tmp_path, chdir_to_tmp):
        """真换行符按行切分（`data.py:68` 的 `split('\\\\n')` 字面量 bug 已修）。

        修复前实现是 `split('\\\\n')`（反斜杠+n 两个字符），GUI/API 多行文本
        只能写入一整条字符串，下拉框永远只有一项。
        """
        (tmp_path / "static").mkdir(parents=True, exist_ok=True)
        ok, msg = update_combo_box_data("A\nB\nC", "team")
        assert ok is True
        path = tmp_path / "static" / "combo-box-data.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["team"] == ["A", "B", "C"]

    def test_literal_backslash_n_is_not_split(self, tmp_path, chdir_to_tmp):
        """字面量反斜杠+n **不再**被切分（修复后的反向锁定）。"""
        (tmp_path / "static").mkdir(parents=True, exist_ok=True)
        ok, msg = update_combo_box_data("A\\nB\\nC", "team")
        assert ok is True
        data = json.loads((tmp_path / "static" / "combo-box-data.json").read_text(encoding="utf-8"))
        assert data["team"] == ["A\\nB\\nC"]

    def test_file_missing_creates(self, tmp_path, chdir_to_tmp):
        # 无需预建 static/ 目录——update_combo_box_data 会自动创建
        ok, msg = update_combo_box_data("X", "team")
        assert ok is True
        assert "文件不存在，已创建新文件并更新" in msg
        assert (tmp_path / "static" / "combo-box-data.json").exists()


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

    def test_second_arg_is_ignored(self, tmp_path, chdir_to_tmp):
        """第二个参数 `json_file_path` 是**死参数**——函数体第一行就覆盖了它。

        `data.py:109` 立刻 `json_file_path = combine_directories('static/abbreviation.json')`，
        所以传任意路径仍读 cwd 下的 static。按现状断言：传一个不存在的路径
        不会报错，且结果与不传时一致（沿用上一条已创建的 cwd 下 static 文件）。
        """
        assert get_abbreviation("3 840 pixels", "/no/such/dir/x.json") == "2160p"

    def test_corrupted_file_raises_valueerror_not_returned(self, tmp_path, chdir_to_tmp):
        """损坏 JSON → **抛 `ValueError`**，不是「原样返回」。

        `load_or_initialize_json` 对损坏文件抛 `ValueError`（`file_utils.py:282`），
        而 `data.py` 只 catch `FileNotFoundError` / `JSONDecodeError` —— `ValueError`
        不是 `JSONDecodeError` 的子类，两个 except 都是死代码。
        """
        static = tmp_path / "static"
        static.mkdir(parents=True, exist_ok=True)
        (static / "abbreviation.json").write_text("{corrupt", encoding="utf-8")
        with pytest.raises(ValueError, match="JSON 解析失败"):
            get_abbreviation("3 840 pixels")


class TestComboBoxListLengths:
    """列表长度按 **6 / 9 / 7**（含末尾空串），不是 5/8/6。"""

    def test_lengths_and_trailing_empty(self, tmp_path, chdir_to_tmp):
        for name, expected_len in [("playlet-source", 6), ("source", 9), ("team", 7)]:
            ok, data = get_combo_box_data(name)
            assert ok is True, f"{name} 读取失败"
            assert len(data) == expected_len, f"{name} 长度应为 {expected_len}"
            assert data[-1] == "", f"{name} 末项应为空串"

    def test_unknown_name_returns_repr_of_keyerror(self, tmp_path, chdir_to_tmp):
        """未知 data_name → `(False, ["'bogus'"])`，且会**创建**空 JSON 文件。"""
        ok, msg = get_combo_box_data("bogus")
        assert ok is False
        assert msg == ["'bogus'"], "带单引号，是 str(KeyError) 的 repr 形态"
        # 副作用：创建了空的 combo-box-data.json
        assert (tmp_path / "static" / "combo-box-data.json").exists()


class TestLoadNames:
    def test_loads_named_list(self, tmp_path):
        f = tmp_path / "names.json"
        f.write_text(json.dumps({"a": ["x", "y"]}), encoding="utf-8")
        assert load_names(str(f), "a") == ["x", "y"]
