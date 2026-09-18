"""Tests for get_pt_gen_info in src.core.rename."""

import pytest
from src.core.rename import get_pt_gen_info


# Sample formatted description text (◎ prefix format)
SAMPLE_DESCRIPTION = """◎译　　名　加勒比海盗3：世界的尽头 / 加勒比海盗：魔盗王终极之战 / 神鬼奇航3：世界的尽头
◎片　　名　Pirates of the Caribbean: At World's End
◎年　　代　2007
◎类　　别　动作 / 奇幻 / 冒险
◎主　　演　约翰尼·德普 Johnny Depp
　　　　　　奥兰多·布鲁姆 Orlando Bloom
　　　　　　凯拉·奈特莉 Keira Knightley
　　　　　　杰弗里·拉什 Geoffrey Rush
　　　　　　比尔·奈伊 Bill Nighy
　　　　　　杰克·达文波特 Jack Davenport

◎简　　介
"""


# Sample raw API response dict
SAMPLE_RAW_DATA = {
    "chinese_title": "加勒比海盗3：世界的尽头",
    "foreign_title": "Pirates of the Caribbean: At World's End",
    "year": 2007,
    "aka": [
        "加勒比海盗：魔盗王终极之战",
        "神鬼奇航3：世界的尽头",
        "Pirates of the Caribbean 3",
    ],
    "genre": ["动作", "奇幻", "冒险"],
    "cast": [
        "约翰尼·德普 Johnny Depp",
        "奥兰多·布鲁姆 Orlando Bloom",
        "凯拉·奈特莉 Keira Knightley",
        "杰弗里·拉什 Geoffrey Rush",
        "比尔·奈伊 Bill Nighy",
        "杰克·达文波特 Jack Davenport",
    ],
    "episodes": None,
    "region": ["美国"],
}


class TestGetPtGenInfoWithRawData:
    """Test get_pt_gen_info when raw_data dict is provided."""

    def test_titles_from_raw_data(self):
        original, english, *_ = get_pt_gen_info(SAMPLE_DESCRIPTION, raw_data=SAMPLE_RAW_DATA)
        assert original == "加勒比海盗3：世界的尽头"
        assert english == "Pirates of the Caribbean: At World's End"

    def test_year_from_raw_data(self):
        _, _, year, *_ = get_pt_gen_info(SAMPLE_DESCRIPTION, raw_data=SAMPLE_RAW_DATA)
        assert year == "2007"

    def test_other_titles_from_raw_data(self):
        _, _, _, other_titles, *_ = get_pt_gen_info(SAMPLE_DESCRIPTION, raw_data=SAMPLE_RAW_DATA)
        assert isinstance(other_titles, list)
        assert "加勒比海盗：魔盗王终极之战" in other_titles
        assert "神鬼奇航3：世界的尽头" in other_titles
        # Main titles should be filtered out
        assert "加勒比海盗3：世界的尽头" not in other_titles
        assert "Pirates of the Caribbean: At World's End" not in other_titles

    def test_categories_from_raw_data(self):
        _, _, _, _, categories, *_ = get_pt_gen_info(SAMPLE_DESCRIPTION, raw_data=SAMPLE_RAW_DATA)
        assert categories == "动作 / 奇幻 / 冒险"

    def test_actors_from_raw_data(self):
        _, _, _, _, _, actors, *_ = get_pt_gen_info(SAMPLE_DESCRIPTION, raw_data=SAMPLE_RAW_DATA)
        assert isinstance(actors, list)
        assert len(actors) == 5  # capped at 5
        assert "约翰尼·德普" in actors[0]

    def test_episodes_none_for_movie(self):
        _, _, _, _, _, _, episodes, season = get_pt_gen_info(SAMPLE_DESCRIPTION, raw_data=SAMPLE_RAW_DATA)
        assert episodes is None
        assert season is None

    def test_returns_8_tuple(self):
        result = get_pt_gen_info(SAMPLE_DESCRIPTION, raw_data=SAMPLE_RAW_DATA)
        assert len(result) == 8


class TestGetPtGenInfoRegexFallback:
    """Test get_pt_gen_info with no raw_data (regex-only)."""

    def test_titles_from_regex(self):
        original, english, *_ = get_pt_gen_info(SAMPLE_DESCRIPTION)
        assert "Pirates of the Caribbean" in english
        assert "加勒比海盗" in original

    def test_year_from_regex(self):
        _, _, year, *_ = get_pt_gen_info(SAMPLE_DESCRIPTION)
        assert year == "2007"

    def test_categories_from_regex(self):
        _, _, _, _, categories, *_ = get_pt_gen_info(SAMPLE_DESCRIPTION)
        assert "动作" in categories

    def test_actors_from_regex(self):
        _, _, _, _, _, actors, *_ = get_pt_gen_info(SAMPLE_DESCRIPTION)
        assert len(actors) >= 1
        assert "约翰尼·德普" in actors[0]


class TestGetPtGenInfoPartialRawData:
    """Test per-field fallback when raw_data is partial."""

    def test_missing_chinese_title_falls_back(self):
        partial_data = {
            "foreign_title": "Some Foreign Title",
            "year": 2020,
        }
        original, english, year, *_ = get_pt_gen_info(SAMPLE_DESCRIPTION, raw_data=partial_data)
        # chinese_title missing → falls back to regex
        assert "加勒比海盗" in original
        # foreign_title present → uses raw_data
        assert english == "Some Foreign Title"
        assert year == "2020"

    def test_missing_year_falls_back(self):
        partial_data = {
            "chinese_title": "测试标题",
        }
        original, _, year, *_ = get_pt_gen_info(SAMPLE_DESCRIPTION, raw_data=partial_data)
        assert original == "测试标题"
        assert year == "2007"  # falls back to regex

    def test_empty_genre_falls_back(self):
        partial_data = {
            "genre": [],  # empty list
        }
        _, _, _, _, categories, *_ = get_pt_gen_info(SAMPLE_DESCRIPTION, raw_data=partial_data)
        # Falls back to regex
        assert "动作" in categories

    def test_empty_dict_uses_regex(self):
        result_with_empty = get_pt_gen_info(SAMPLE_DESCRIPTION, raw_data={})
        result_without = get_pt_gen_info(SAMPLE_DESCRIPTION, raw_data=None)
        # Both should produce identical results
        assert result_with_empty == result_without


class TestGetPtGenInfoTVSeason:
    """Test season parsing from raw_data chinese_title."""

    def test_season_from_chinese_title_digit(self):
        raw_data = {"chinese_title": "双面女间谍 第5季"}
        _, _, _, _, _, _, _, season = get_pt_gen_info("minimal description", raw_data=raw_data)
        assert season == 5

    def test_season_from_chinese_title_chinese_numeral(self):
        raw_data = {"chinese_title": "双面女间谍 第五季"}
        _, _, _, _, _, _, _, season = get_pt_gen_info("minimal description", raw_data=raw_data)
        assert season == 5

    def test_episodes_from_raw_data(self):
        raw_data = {"episodes": 22}
        _, _, _, _, _, _, episodes, _ = get_pt_gen_info("minimal description", raw_data=raw_data)
        assert episodes == 22
