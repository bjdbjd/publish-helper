"""Tests for src.core.text text/number/pinyin helpers."""

import pytest

from src.core.text import (
    base64encoding,
    chinese_name_to_pinyin,
    chinese_to_int,
    convert_chinese_punctuation_to_english,
    int_to_chinese,
    int_to_roman,
    int_to_special_roman,
    natural_keys,
    validate_and_convert_to_int,
)


class TestNaturalKeys:
    def test_sorts_numeric_order(self):
        items = ["EP10", "EP1", "EP2"]
        items.sort(key=natural_keys)
        assert items == ["EP1", "EP2", "EP10"]

    def test_case_insensitive(self):
        items = ["Apple", "banana", "Barry"]
        items.sort(key=natural_keys)
        assert items == ["Apple", "banana", "Barry"]

    def test_returns_list_of_int_and_str(self):
        keys = natural_keys("EP10")
        assert 10 in keys


class TestIntToRoman:
    def test_single_digit(self):
        assert int_to_roman(4) == "IV"

    def test_multi_digit(self):
        assert int_to_roman(9) == "IX"
        assert int_to_roman(1990) == "MCMXC"

    def test_zero_returns_empty(self):
        assert int_to_roman(0) == ""


class TestIntToSpecialRoman:
    def test_mapping_1_to_10(self):
        assert int_to_special_roman(2) == "Ⅱ"
        assert int_to_special_roman(5) == "Ⅴ"
        assert int_to_special_roman(10) == "Ⅹ"

    def test_out_of_range_returns_number_str(self):
        assert int_to_special_roman(11) == "11"
        assert int_to_special_roman(0) == "0"


class TestIntToChinese:
    def test_zero(self):
        assert int_to_chinese(0) == "零"

    def test_under_20(self):
        # 标准写法：11→十一、15→十五（省略十位前导一）
        assert int_to_chinese(11) == "十一"
        assert int_to_chinese(15) == "十五"

    def test_multiple_of_ten(self):
        # 10→十、20→二十（无前导一）
        assert int_to_chinese(10) == "十"
        assert int_to_chinese(20) == "二十"

    def test_hundreds_with_zero(self):
        assert int_to_chinese(100) == "一百"
        assert int_to_chinese(101) == "一百零一"
        assert int_to_chinese(110) == "一百一十"

    def test_thousands(self):
        assert int_to_chinese(1000) == "一千"
        assert int_to_chinese(1001) == "一千零一"

    def test_out_of_range(self):
        assert int_to_chinese(-1) == "数字超出范围"
        assert int_to_chinese(10000) == "数字超出范围"


class TestChineseToInt:
    def test_single_digit(self):
        assert chinese_to_int("五") == 5
        assert chinese_to_int("二") == 2
        assert chinese_to_int("零") == 0

    def test_tens(self):
        assert chinese_to_int("十") == 10
        assert chinese_to_int("十一") == 11
        assert chinese_to_int("十五") == 15
        assert chinese_to_int("二十") == 20
        assert chinese_to_int("二十一") == 21

    def test_hundreds_thousands(self):
        assert chinese_to_int("三百") == 300
        assert chinese_to_int("一千零一") == 1001
        assert chinese_to_int("一千一百") == 1100

    def test_invalid_returns_none(self):
        assert chinese_to_int("abc") is None
        assert chinese_to_int("") is None

    def test_wan_unit(self):
        """「万」按节进位。此前 `unit_map` 有「万」但算法不做节分隔，
        `十二万` 会得 20010、`十万` 得 10010（bug，已修）。"""
        assert chinese_to_int("十二万") == 120000
        assert chinese_to_int("十万") == 100000
        assert chinese_to_int("一万") == 10000
        assert chinese_to_int("三万五千") == 35000

    def test_yi_not_supported(self):
        """「亿」未实现 → 非法字符 → None（与「万」不同，见 §2.10 说明）。"""
        assert chinese_to_int("一亿") is None


class TestBase64Encoding:
    def test_roundtrip(self):
        assert base64encoding("中文") == "5Lit5paH"
        assert base64encoding("Publish Helper") == "UHVibGlzaCBIZWxwZXI="


class TestValidateAndConvertToInt:
    def test_valid(self):
        assert validate_and_convert_to_int("42", "num") == 42

    def test_none_raises(self):
        with pytest.raises(ValueError):
            validate_and_convert_to_int(None, "num")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            validate_and_convert_to_int("", "num")

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError):
            validate_and_convert_to_int("abc", "num")


class TestConvertChinesePunctuation:
    def test_comma_and_period(self):
        assert convert_chinese_punctuation_to_english("你好，世界。") == "你好, 世界. "

    def test_ellipsis(self):
        # 单个省略号 … → '...'；两个 … → 六点
        assert convert_chinese_punctuation_to_english("…") == "..."
        assert convert_chinese_punctuation_to_english("……") == "......"

    def test_parens(self):
        assert convert_chinese_punctuation_to_english("（注）") == " (注) "

    def test_single_quote_curly(self):
        """中文单引号映射为半角单引号（与 `“”` 一样不区分开闭）。

        `text.py:44-45` 原写作 `'‘': ''',  # comment`，`''',` 被词法器当成
        三引号字符串的开启标记，导致 `‘` 的值变成注释文本、`’` 根本不是字典键。
        已修复；本用例锁定修复后的行为。
        """
        assert convert_chinese_punctuation_to_english("A’B") == "A'B"
        assert convert_chinese_punctuation_to_english("‘A") == "'A"
        assert convert_chinese_punctuation_to_english("‘引号’") == "'引号'"


class TestChineseNameToPinyin:
    def test_known_name(self):
        # 末尾带一个空格（每个拼音后加空格再 rstrip 前）——按现状断言
        assert chinese_name_to_pinyin("张伟") == "Zhang Wei "