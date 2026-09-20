"""Tests for src.core.poster: poster URL extraction, download, process, orchestration."""

from src.core import poster
from src.core.poster import (
    download_poster,
    get_poster_from_pt_gen_response,
    get_poster_url_from_data,
    process_poster,
)
from tests.conftest import FakeResponse


class TestGetPosterUrlFromData:
    def test_top_level_field(self):
        assert get_poster_url_from_data({"poster": "http://p/1.jpg"}) == "http://p/1.jpg"

    def test_field_precedence(self):
        assert get_poster_url_from_data({"img": "http://p/img.jpg", "poster": "http://p/post.jpg"}) == "http://p/post.jpg"

    def test_nested_data(self):
        assert get_poster_url_from_data({"data": {"cover": "http://p/c.jpg"}}) == "http://p/c.jpg"

    def test_not_found_empty(self):
        assert get_poster_url_from_data({"foo": "bar"}) == ""


class TestDownloadPoster:
    def test_empty_url(self, tmp_path):
        ok, msg = download_poster("", str(tmp_path / "p.jpg"))
        assert ok is False
        assert msg == "Poster URL is empty"

    def test_success_writes_file(self, tmp_path, monkeypatch):
        captured = {}
        def _get(url, headers=None, timeout=None, stream=None):
            captured["headers"] = headers
            captured["timeout"] = timeout
            return FakeResponse(200, content=b"IMAGEDATA")
        monkeypatch.setattr("requests.get", _get)
        save = tmp_path / "p.jpg"
        ok, path = download_poster("http://img/1.jpg", str(save))
        assert ok is True
        assert path == str(save)
        assert save.read_bytes() == b"IMAGEDATA"
        # 防豆瓣反爬：Chrome UA + Douban Referer
        assert "Mozilla/5.0" in captured["headers"]["User-Agent"]
        assert captured["headers"]["Referer"] == "https://movie.douban.com/"
        assert captured["timeout"] == 30

    def test_non_200(self, tmp_path, monkeypatch):
        monkeypatch.setattr("requests.get", lambda *a, **kw: FakeResponse(404, content=b""))
        ok, msg = download_poster("http://img/1.jpg", str(tmp_path / "p.jpg"))
        assert ok is False
        assert "status code: 404" in msg

    def test_timeout(self, tmp_path, monkeypatch):
        import requests
        def _raise(*a, **kw):
            raise requests.Timeout()
        monkeypatch.setattr("requests.get", _raise)
        ok, msg = download_poster("http://img/1.jpg", str(tmp_path / "p.jpg"))
        assert ok is False
        assert msg == "Poster download timeout (30s)"


class TestProcessPoster:
    def test_upload_success_strips_bbcode_and_cleans(self, tmp_path, monkeypatch):
        # mock download_poster：实际创建临时文件（process_poster 会用 getsize）
        def _dl(url, save):
            with open(save, "wb") as f:
                f.write(b"IMG")
            return True, save
        monkeypatch.setattr(poster, "download_poster", _dl)
        monkeypatch.setattr(
            poster, "upload_picture",
            lambda api, tok, path: (True, "[img]http://img/u.jpg[/img]"),
        )
        ok, url = process_poster(
            "http://img/1.jpg", "http://bed/api", "tok", temp_dir=str(tmp_path)
        )
        assert ok is True
        assert url == "http://img/u.jpg"  # [img] 剥成裸 URL
        # 上传成功后临时文件被删除
        assert not list(tmp_path.glob("poster_*.jpg"))

    def test_upload_failure_keeps_temp(self, tmp_path, monkeypatch):
        def _dl(url, save):
            with open(save, "wb") as f:
                f.write(b"IMG")
            return True, save
        monkeypatch.setattr(poster, "download_poster", _dl)
        monkeypatch.setattr(poster, "upload_picture", lambda api, tok, path: (False, "upload failed"))
        ok, msg = process_poster(
            "http://img/1.jpg", "http://bed/api", "tok", temp_dir=str(tmp_path)
        )
        assert ok is False
        assert "upload failed" in msg
        # 上传失败保留临时文件供调试
        assert list(tmp_path.glob("poster_*.jpg"))

    def test_download_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(poster, "download_poster", lambda url, save: (False, "dl err"))
        ok, msg = process_poster(
            "http://img/1.jpg", "http://bed/api", "tok", temp_dir=str(tmp_path)
        )
        assert ok is False
        assert "Failed to download poster" in msg


class TestGetPosterFromPtGenResponse:
    def test_no_poster(self, tmp_path):
        ok, msg = get_poster_from_pt_gen_response(
            {"foo": "x"}, "http://bed/api", "tok", temp_dir=str(tmp_path)
        )
        assert ok is False
        assert msg == "No poster URL found in PT-Gen response"

    def test_with_poster_forwards_to_process(self, tmp_path, monkeypatch):
        monkeypatch.setattr(poster, "process_poster", lambda url, api, tok, temp_dir: (True, "http://u"))
        ok, url = get_poster_from_pt_gen_response(
            {"poster": "http://img/1.jpg"}, "http://bed/api", "tok", temp_dir=str(tmp_path)
        )
        assert ok is True
        assert url == "http://u"
