"""Tests for src.core.picturebed: 6 providers, type detection, filename generation.

mock requests.post（返回可配置 FakeResponse），cwd 隔离防止写真实 static/。
"""

import json
import random

import pytest

from src.core.picturebed import (
    bohe_picture_bed,
    chevereto_picture_bed,
    find_picture_bed_type,
    freeimage_picture_bed,
    generate_image_filename,
    get_picture_bed_type,
    imgbb_picture_bed,
    lsky_pro_picture_bed,
    pixhost_picture_bed,
    upload_picture,
)
from tests.conftest import FakeResponse


@pytest.fixture
def post_fake(monkeypatch):
    """Monkeypatch requests.post with a configurable fake response."""
    captured = {}

    def _set(**kwargs):
        captured["resp"] = kwargs

    monkeypatch.setattr("requests.post", lambda *a, **kw: captured["resp"])
    return captured


@pytest.fixture
def img_file(tmp_path):
    p = tmp_path / "pic.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n fake image")
    return str(p)


class TestFindPictureBedType:
    def test_http_to_https(self):
        ok, t = find_picture_bed_type(
            "http://freeimage.host/api/1/upload/",
            {"freeimage": ["https://freeimage.host/api/1/upload"]},
        )
        assert ok is True
        assert t == "freeimage"

    def test_trailing_slash_stripped(self):
        ok, t = find_picture_bed_type(
            "https://freeimage.host/api/1/upload/",
            {"freeimage": ["https://freeimage.host/api/1/upload"]},
        )
        assert ok is True

    def test_not_found_message(self):
        ok, msg = find_picture_bed_type(
            "https://unknown.example/api",
            {"freeimage": ["https://freeimage.host/api/1/upload"]},
        )
        assert ok is False
        assert "暂未配置" in msg


class TestGetPictureBedType:
    def test_from_json_data(self, tmp_path, chdir_to_tmp):
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "picture-bed-data.json").write_text(
            json.dumps({"freeimage": ["https://freeimage.host/api/1/upload"]}),
            encoding="utf-8",
        )
        ok, t = get_picture_bed_type("https://freeimage.host/api/1/upload")
        assert ok is True
        assert t == "freeimage"

    def test_unknown_url_message(self, tmp_path, chdir_to_tmp):
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "picture-bed-data.json").write_text(
            json.dumps({"freeimage": ["https://freeimage.host/api/1/upload"]}),
            encoding="utf-8",
        )
        ok, msg = get_picture_bed_type("https://nope.example/api")
        assert ok is False
        assert "暂未配置" in msg


class TestGenerateImageFilename:
    def test_fixed_random_digits(self, tmp_path, monkeypatch):
        import re
        # mock random.sample 返回固定 6 位数字
        monkeypatch.setattr(random, "sample", lambda seq, k: ["0", "1", "2", "3", "4", "5"])
        path = generate_image_filename(str(tmp_path))
        assert path.startswith(str(tmp_path) + "/")
        fname = path.rsplit("/", 1)[1]
        # 格式 %Y%m%d-%H%M%S-<6位随机数>.png
        assert re.fullmatch(r"\d{8}-\d{6}-012345\.png", fname)

    def test_real_sample_has_six_distinct_digits(self, tmp_path):
        """不 mock：断言真实 random.sample 的语义——6 位数字互不相同。

        原先的用例 mock 成 ["0","0","1","2","3","4"]，恰好断言了一个
        random.sample（无放回）永远不可能产生的值，把这条活契约擦掉了。
        """
        import re
        from collections import Counter
        path = generate_image_filename(str(tmp_path))
        fname = path.rsplit("/", 1)[1]
        m = re.fullmatch(r"\d{8}-\d{6}-(\d{6})\.png", fname)
        assert m, f"文件名格式不符: {fname}"
        digits = m.group(1)
        assert not [d for d, n in Counter(digits).items() if n > 1], (
            f"6 位随机数出现重复位（random.sample 无放回，不应重复）: {digits}"
        )


# ------------------------------------------------------------------ providers


class TestLskyPro:
    def test_success(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(
            200, text=json.dumps({"data": {"links": {"bbcode": "[img]u[/img]"}}})
        )
        ok, url = lsky_pro_picture_bed("https://lsky/api", "tok", img_file)
        assert ok is True
        assert url == "[img]u[/img]"

    def test_non_200(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(500, text="boom")
        ok, msg = lsky_pro_picture_bed("https://lsky/api", "tok", img_file)
        assert ok is False
        assert "错误状态码" in msg

    def test_missing_data(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(200, text=json.dumps({"status": False, "message": "e"}))
        ok, msg = lsky_pro_picture_bed("https://lsky/api", "tok", img_file)
        assert ok is False
        assert "错误" in msg


class TestBohe:
    def test_success(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(
            200, text=json.dumps({"statusCode": "200", "bbsurl": "http://img/b.jpg"})
        )
        ok, url = bohe_picture_bed("https://bohe/api", "tok", img_file)
        assert ok is True
        assert url == "http://img/b.jpg"

    def test_empty_status(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(200, text=json.dumps({"statusCode": "", "resultData": ""}))
        ok, msg = bohe_picture_bed("https://bohe/api", "tok", img_file)
        assert ok is False
        assert msg == "未接受到响应"

    def test_error_code(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(200, text=json.dumps({"statusCode": "500", "resultData": "x"}))
        ok, msg = bohe_picture_bed("https://bohe/api", "tok", img_file)
        assert ok is False
        assert "API响应出错了" in msg


class TestChevereto:
    def test_success(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(200, text=json.dumps({"image": {"url": "http://i/u.jpg"}}))
        ok, url = chevereto_picture_bed("https://ch/api", "tok", img_file)
        assert ok is True
        assert url == "[img]http://i/u.jpg[/img]"


class TestFreeimage:
    def test_success_http(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(200, text="https://freeimage.host/i/abc.jpg")
        ok, url = freeimage_picture_bed("https://freeimage/api", "tok", img_file)
        assert ok is True
        assert url == "[img]https://freeimage.host/i/abc.jpg[/img]"

    def test_error_text(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(200, text="error: something went wrong")
        ok, msg = freeimage_picture_bed("https://freeimage/api", "tok", img_file)
        assert ok is False
        assert msg == "error: something went wrong"


class TestImgbb:
    def test_success(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(
            200, text=json.dumps({"data": {"image": {"url": "http://i/u.jpg"}}})
        )
        ok, url = imgbb_picture_bed("https://imgbb/api", "tok", img_file)
        assert ok is True
        assert url == "[img]http://i/u.jpg[/img]"


class TestPixhost:
    def test_success_url_transform(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(
            200,
            text=json.dumps({"th_url": "https://t.imgix.net/thumbs/x.jpg"}),
        )
        ok, url = pixhost_picture_bed("https://api.pixhost.to/images", img_file)
        assert ok is True
        # //t → //img, /thumbs/ → /images/
        assert url == "[img]https://img.imgix.net/images/x.jpg[/img]"


class TestProviderErrorBranches:
    """各 provider 的异常分支（网络/解析失败需逐家 mock requests.post 抛异常）。

    用 monkeypatch 让 requests.post 抛 requests.RequestException，验证返回
    (False, 中文错误)。另测 JSON 解析失败（KeyError/JSONDecodeError）。
    """

    @pytest.fixture
    def raise_post(self, monkeypatch):
        import requests

        def _make(exc):
            def _raise(*a, **k):
                raise exc
            monkeypatch.setattr("requests.post", _raise)
        return _make

    def test_lsky_request_exception(self, img_file, raise_post):
        import requests
        raise_post(requests.RequestException("net down"))
        ok, msg = lsky_pro_picture_bed("https://lsky/api", "tok", img_file)
        assert ok is False
        assert "请求过程中出现错误" in msg

    def test_lsky_key_error(self, post_fake, img_file):
        # 缺 links.bbcode → KeyError 分支
        post_fake["resp"] = FakeResponse(200, text=json.dumps({"data": {}}))
        ok, msg = lsky_pro_picture_bed("https://lsky/api", "tok", img_file)
        assert ok is False
        assert "缺少所需的值" in msg or "缺少data" in msg or "缺少links" in msg

    def test_bohe_request_exception(self, img_file, raise_post):
        import requests
        raise_post(requests.RequestException("down"))
        ok, msg = bohe_picture_bed("https://bohe/api", "tok", img_file)
        assert ok is False
        assert "请求过程中出现错误" in msg

    def test_bohe_invalid_json(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(200, text="not json at all")
        ok, msg = bohe_picture_bed("https://bohe/api", "tok", img_file)
        assert ok is False
        assert msg == "响应不是有效的JSON格式"

    def test_chevereto_request_exception(self, img_file, raise_post):
        import requests
        raise_post(requests.RequestException("down"))
        ok, msg = chevereto_picture_bed("https://ch/api", "tok", img_file)
        assert ok is False
        assert "请求过程中出现错误" in msg

    def test_chevereto_key_error(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(200, text=json.dumps({"other": "x"}))
        ok, msg = chevereto_picture_bed("https://ch/api", "tok", img_file)
        assert ok is False
        assert "缺少所需的值" in msg

    def test_freeimage_request_exception(self, img_file, raise_post):
        import requests
        raise_post(requests.RequestException("down"))
        ok, msg = freeimage_picture_bed("https://free/api", "tok", img_file)
        assert ok is False
        assert "请求过程中出现错误" in msg

    def test_imgbb_request_exception(self, img_file, raise_post):
        import requests
        raise_post(requests.RequestException("down"))
        ok, msg = imgbb_picture_bed("https://imgbb/api", "tok", img_file)
        assert ok is False
        assert "请求过程中出现错误" in msg

    def test_pixhost_request_exception(self, img_file, raise_post):
        import requests
        raise_post(requests.RequestException("down"))
        ok, msg = pixhost_picture_bed("https://api.pixhost.to/images", img_file)
        assert ok is False
        assert "请求过程中出现错误" in msg

    def test_pixhost_key_error(self, post_fake, img_file):
        post_fake["resp"] = FakeResponse(200, text=json.dumps({"foo": "x"}))
        ok, msg = pixhost_picture_bed("https://api.pixhost.to/images", img_file)
        assert ok is False
        assert "缺少所需的值" in msg

    def test_upload_unknown_type(self, tmp_path, chdir_to_tmp, img_file):
        # 类型未识别（图床 JSON 全空）→ 防御消息
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "picture-bed-data.json").write_text("{}", encoding="utf-8")
        ok, msg = upload_picture("https://unknown.example/api", "tok", img_file)
        assert ok is False
        assert "暂未配置" in msg


class TestUploadPicture:
    def test_missing_file(self, chdir_to_tmp):
        ok, msg = upload_picture("https://freeimage.host/api/1/upload", "tok", "/ghost.png")
        assert ok is False
        assert msg == "图片文件路径不存在"

    def test_dispatch_lsky(self, tmp_path, chdir_to_tmp, post_fake, img_file, monkeypatch):
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "picture-bed-data.json").write_text(
            json.dumps({"lsky-pro": ["https://picture.agsv.top/api/v1/upload"]}),
            encoding="utf-8",
        )
        post_fake["resp"] = FakeResponse(
            200, text=json.dumps({"data": {"links": {"bbcode": "[img]u[/img]"}}})
        )
        ok, url = upload_picture("https://picture.agsv.top/api/v1/upload", "tok", img_file)
        assert ok is True
        assert url == "[img]u[/img]"
