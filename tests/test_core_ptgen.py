"""Tests for src.core.ptgen: PT-Gen API call, playlet description, data extraction."""

import json
import time

import pytest

from src.core.ptgen import (
    _auth_signature,
    _is_new_pt_gen_api,
    _norm_ptgen_url,
    get_data_from_pt_gen_description,
    get_playlet_description,
    get_pt_gen_description,
)
from tests.conftest import FakeResponse


@pytest.fixture
def get_fake(monkeypatch):
    """Monkeypatch requests.get with a configurable fake response."""
    captured = {}

    def _set(resp):
        captured["resp"] = resp

    monkeypatch.setattr("requests.get", lambda *a, **kw: captured["resp"])
    return captured


class TestIsNewPtGenApi:
    def test_new_api_path(self):
        assert _is_new_pt_gen_api("https://pt-gen.hares.dpdns.org/api/getData") is True

    def test_new_api_host_only(self):
        assert _is_new_pt_gen_api("https://pt-gen.hares.dpdns.org") is True

    def test_old_api(self):
        assert _is_new_pt_gen_api("https://ptgen.agsvpt.work/") is False


class TestNormPtgenUrl:
    def test_new_api_normalized(self):
        assert _norm_ptgen_url("https://pt-gen.hares.dpdns.org/") == "https://pt-gen.hares.dpdns.org/api/getData"
        assert _norm_ptgen_url("https://pt-gen.hares.dpdns.org/api") == "https://pt-gen.hares.dpdns.org/api/getData"

    def test_old_api_kept(self):
        assert _norm_ptgen_url("https://ptgen.agsvpt.work/") == "https://ptgen.agsvpt.work"


class TestAuthSignature:
    def test_base64url_no_padding(self, monkeypatch):
        monkeypatch.setattr(time, "time", lambda: 1700000000.123)
        ts, sig = _auth_signature("secret")
        assert ts == str(int(1700000000.123 * 1000))
        # base64url：无 + / 和 = 填充
        assert "+" not in sig
        assert "/" not in sig
        assert "=" not in sig
        assert len(sig) > 0

    def test_signature_is_sha256_hmac(self, monkeypatch):
        import base64
        import hashlib
        import hmac
        monkeypatch.setattr(time, "time", lambda: 1700000000.123)
        ts, sig = _auth_signature("secret")
        expected_raw = base64.b64encode(
            hmac.new(b"secret", ts.encode(), hashlib.sha256).digest()
        ).decode()
        expected = expected_raw.replace("+", "-").replace("/", "_").rstrip("=")
        assert sig == expected


class TestGetPtGenDescription:
    def test_tt_url_rewrite(self, get_fake):
        get_fake["resp"] = FakeResponse(200, json_data={"format": "x", "chinese_title": ""})
        ok, payload = get_pt_gen_description("https://ptgen.agsvpt.work/", "tt1234567")
        assert ok is True
        # 末尾会被追加 '\n'
        assert payload[0] == "x\n"

    def test_douban_id_rewrite(self, get_fake):
        get_fake["resp"] = FakeResponse(200, json_data={"format": "x", "chinese_title": ""})
        ok, _ = get_pt_gen_description("https://ptgen.agsvpt.work/", "1234567")
        assert ok is True

    def test_non_200_error(self, get_fake):
        get_fake["resp"] = FakeResponse(500, text="server err")
        ok, msg = get_pt_gen_description("https://ptgen.agsvpt.work/", "url")
        assert ok is False
        assert "PT-Gen接口请求失败，状态码：500" in msg

    def test_invalid_json_error(self, get_fake):
        class _BadJson(FakeResponse):
            def json(self):
                raise ValueError("no")
        get_fake["resp"] = _BadJson(200, text="not json")
        ok, msg = get_pt_gen_description("https://ptgen.agsvpt.work/", "url")
        assert ok is False
        assert "不是有效的JSON格式" in msg

    def test_empty_format_error(self, get_fake):
        get_fake["resp"] = FakeResponse(200, json_data={"format": "", "chinese_title": ""})
        ok, msg = get_pt_gen_description("https://ptgen.agsvpt.work/", "url")
        assert ok is False
        assert "获取到的PT-Gen简介为空" in msg

    def test_timeout_error(self, get_fake, monkeypatch):
        import requests
        def _raise(*a, **kw):
            raise requests.Timeout()
        monkeypatch.setattr("requests.get", _raise)
        ok, msg = get_pt_gen_description("https://ptgen.agsvpt.work/", "url")
        assert ok is False
        assert msg == "PT-Gen接口请求超时"

    def test_new_api_sends_signature_headers(self, get_fake, monkeypatch):
        import requests
        captured = {}
        def _capture(url, params=None, headers=None, timeout=None):
            captured["headers"] = headers
            captured["params"] = params
            return FakeResponse(200, json_data={"format": "x", "chinese_title": ""})
        monkeypatch.setattr("requests.get", _capture)
        ok, _ = get_pt_gen_description("https://pt-gen.hares.dpdns.org", "tt123")
        assert ok is True
        assert "X-Timestamp" in captured["headers"]
        assert "X-Signature" in captured["headers"]
        assert captured["params"]["requestId"].startswith("req_publish_helper_")

    def test_success_nested_tuple_and_postprocess(self, get_fake):
        fmt = (
            "◎译　　名　Old Name\n"
            "◎片　　名　New Title\n"
            "◎年　　代　2020\n"
            "<img1>link</img1>&#39;"
        )
        get_fake["resp"] = FakeResponse(
            200,
            json_data={
                "format": fmt,
                "chinese_title": "新译名",
                "aka": ["别名A"],
            },
        )
        ok, (format_data, data) = get_pt_gen_description("https://ptgen.agsvpt.work/", "tt1")
        assert ok is True
        # 译名行被重构为 chinese_title（新译名），原译名内容移到别名行
        assert "新译名" in format_data
        assert "Old Name" in format_data
        assert "&#39;" not in format_data
        assert "'" in format_data
        assert "img2" in format_data
        assert "img1" not in format_data
        assert data["chinese_title"] == "新译名"


class TestGetPlayletDescription:
    def test_season_1_no_append(self):
        d = get_playlet_description("我的短剧", "2024", "大陆", "短剧", "国语", "1")
        assert "第二季" not in d
        assert "◎片　　名　我的短剧" in d
        assert "◎年　　代　2024" in d
        assert "◎产　　地　大陆" in d
        assert "◎类　　别　短剧" in d
        assert "◎语　　言　国语" in d

    def test_season_2_appends(self):
        d = get_playlet_description("我的短剧", "2024", "大陆", "短剧", "国语", "2")
        assert "我的短剧 第二季" in d


class TestGetDataFromPtGenDescription:
    SAMPLE = "◎类　　别　动作\n◎产　　地　美国\n"

    def test_imdb_and_douban(self):
        desc = "https://www.imdb.com/title/tt1234567/ https://movie.douban.com/subject/1234567/ " + self.SAMPLE
        imdb, db, *_ = get_data_from_pt_gen_description("", desc, "", "WEB-DL", "电影")
        assert imdb == "https://www.imdb.com/title/tt1234567/"
        assert db == "https://movie.douban.com/subject/1234567/"

    def test_area_usa_to_eu(self):
        desc = "◎产　　地　美国\n"
        _, _, _, area, *_ = get_data_from_pt_gen_description("", desc, "", "WEB-DL", "电影")
        assert area == "欧美"

    def test_area_dalu(self):
        desc = "◎产　　地　中国大陆\n"
        _, _, _, area, *_ = get_data_from_pt_gen_description("", desc, "", "WEB-DL", "电影")
        assert area == "大陆"

    def test_category_override(self):
        desc = "◎类　　别　纪录片\n"
        _, _, category, *_ = get_data_from_pt_gen_description("", desc, "", "WEB-DL", "电影")
        assert category == "纪录"

    def test_resolution_4k(self):
        _, _, _, _, video_format, *_ = get_data_from_pt_gen_description("Title 2160p", "", "", "WEB-DL", "电影")
        assert video_format == "4K"

    def test_medium_webdl(self):
        *_, medium = get_data_from_pt_gen_description("", "", "", "WEB-DL", "电影")
        assert medium == "WEB-DL"

    def test_audio_dts_hdma(self):
        *_, audio_codec, _, _ = get_data_from_pt_gen_description("DTS-HD MA", "", "", "WEB-DL", "电影")
        assert audio_codec == "DTS-HDMA"

    def test_video_codec_hevc(self):
        _, _, _, _, _, _, video_codec, _ = get_data_from_pt_gen_description("HEVC", "", "", "WEB-DL", "电影")
        assert video_codec == "H265"
