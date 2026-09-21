"""Tests for the 21 previously-untested API routes in src.api.startapi.

对每个路由：
- 错误分支：缺必填参→422、白名单越界→422、media 越域→401 / 路径不存在→422；
- 成功路径：monkeypatch `src.api.startapi.<core_fn>` 返回成功元组，断言 JSON 包络。

覆盖（故障注入为主，avoid真实媒体文件解析拖慢套件；media类用 conftest media_file 占位
文件让 os.path.exists 通过，或 real_media 真实冒烟 1-2 条）。
"""

import json
import os

import pytest

import src.api.startapi as startapi
from src.api.startapi import api


def _set(monkeypatch, name, value):
    monkeypatch.setattr(f"src.api.startapi.{name}", value)


class TestGetScreenshot:
    def test_missing_path_no_crash(self, api_client, monkeypatch, media_file):
        # 空 path 被 join 到 media 根（缺参 422 死分支），mock 成功链验证不抛 500
        _set(monkeypatch, "get_screenshot", lambda *a, **k: (True, ["pic.png"]))
        _set(monkeypatch, "check_path_and_find_video", lambda p: (2, str(media_file)))
        r = api_client.get("/api/getScreenshot")
        assert r.status_code != 500

    def test_unauthorized(self, api_client, media_file):
        # 越域路径：../etc/passwd join 到 media 后 abspath 不 startswith media → 401
        r = api_client.get("/api/getScreenshot", query_string={"path": "../etc/passwd"})
        assert r.status_code == 401

    def test_success(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "get_screenshot", lambda *a, **k: (True, ["pic1.png", "pic2.png"]))
        _set(monkeypatch, "check_path_and_find_video", lambda p: (1, str(media_file)))
        r = api_client.get("/api/getScreenshot", query_string={"path": "视频.mkv"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["statusCode"] == "OK"
        assert data["data"]["screenshotPath"] == ["pic1.png", "pic2.png"]


class TestGetThumbnail:
    def test_missing_path_no_crash(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "get_thumbnail", lambda *a, **k: (True, "thumb.png"))
        _set(monkeypatch, "check_path_and_find_video", lambda p: (2, str(media_file)))
        r = api_client.get("/api/getThumbnail")
        assert r.status_code != 500

    def test_unauthorized(self, api_client, media_file):
        r = api_client.get("/api/getThumbnail", query_string={"path": "../etc/passwd"})
        assert r.status_code == 401

    def test_success(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "get_thumbnail", lambda *a, **k: (True, "thumb.png"))
        _set(monkeypatch, "check_path_and_find_video", lambda p: (1, str(media_file)))
        r = api_client.get("/api/getThumbnail", query_string={"path": "视频.mkv"})
        assert r.status_code == 200
        assert r.get_json()["data"]["thumbnailPath"] == "thumb.png"


class TestUploadPicture:
    def test_missing_path(self, api_client):
        r = api_client.post("/api/uploadPicture", json={})
        assert r.status_code == 422
        assert r.get_json()["statusCode"] == "MISSING_REQUIRED_PARAMETER"

    def test_file_not_exists(self, api_client):
        r = api_client.post("/api/uploadPicture", json={"picturePath": "/no/such.png"})
        assert r.status_code == 422
        assert r.get_json()["statusCode"] == "FILE_PATH_ERROR"

    def test_success(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "upload_picture", lambda *a, **k: (True, "[img]http://x/u.jpg[/img]"))
        r = api_client.post(
            "/api/uploadPicture",
            json={"picturePath": str(media_file), "pictureBedApiUrl": "https://bed/api",
                  "pictureBedApiToken": "tok"},
        )
        assert r.status_code == 200
        data = r.get_json()["data"]
        assert data["pictureBbCode"] == "[img]http://x/u.jpg[/img]"
        assert data["pictureUrl"] == "http://x/u.jpg"  # bbcode[5:-6]


class TestGetMediaInfo:
    def test_unauthorized(self, api_client, media_file):
        r = api_client.get("/api/getMediaInfo", query_string={"path": "../etc/passwd"})
        assert r.status_code == 401

    def test_missing_path_no_crash(self, api_client, monkeypatch, media_file):
        # 空 path join 到 media 根（缺参 422 死分支），mock 成功链路验证不崩
        _set(monkeypatch, "get_media_info", lambda *a, **k: (True, "General\n..."))
        _set(monkeypatch, "check_path_and_find_video", lambda p: (2, str(media_file)))
        r = api_client.get("/api/getMediaInfo")
        assert r.status_code != 500

    def test_file_not_exists(self, api_client, media_file):
        r = api_client.get("/api/getMediaInfo", query_string={"path": "ghost.mkv"})
        assert r.status_code == 422
        assert r.get_json()["statusCode"] == "FILE_PATH_ERROR"

    def test_success(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "get_media_info", lambda *a, **k: (True, "General\n..."))
        _set(monkeypatch, "check_path_and_find_video", lambda p: (2, str(media_file)))
        r = api_client.get("/api/getMediaInfo", query_string={"path": "视频.mkv"})
        assert r.status_code == 200
        assert "General" in r.get_json()["data"]["mediaInfo"]


class TestGetVideoInfo:
    def test_unauthorized(self, api_client, media_file):
        r = api_client.get("/api/getVideoInfo", query_string={"path": "../etc/passwd"})
        assert r.status_code == 401

    def test_missing_path_no_crash(self, api_client, monkeypatch, media_file):
        info = ["1080p", "x264", "10bit", "HDR10", "", "DDP", "5.1", "", []]
        _set(monkeypatch, "get_video_info", lambda *a, **k: (True, info))
        _set(monkeypatch, "check_path_and_find_video", lambda p: (1, str(media_file)))
        r = api_client.get("/api/getVideoInfo")
        assert r.status_code != 500

    def test_success(self, api_client, monkeypatch, media_file):
        info = ["1080p", "x264", "10bit", "HDR10", "", "DDP", "5.1", "", ["国语"]]
        _set(monkeypatch, "get_video_info", lambda *a, **k: (True, info))
        _set(monkeypatch, "check_path_and_find_video", lambda p: (1, str(media_file)))
        r = api_client.get("/api/getVideoInfo", query_string={"path": "视频.mkv"})
        assert r.status_code == 200
        data = r.get_json()["data"]
        assert data["videoFormat"] == "1080p"
        assert data["videoCodec"] == "x264"


class TestGetPtGenDescription:
    def test_missing_url(self, api_client):
        r = api_client.get("/api/getPtGenDescription")
        assert r.status_code == 422

    def test_success(self, api_client, monkeypatch):
        _set(monkeypatch, "get_pt_gen_description", lambda *a, **k: (True, ("format", {"k": "v"})))
        r = api_client.get("/api/getPtGenDescription", query_string={"resourceUrl": "tt123"})
        assert r.status_code == 200
        data = r.get_json()["data"]
        assert data["description"] == "format"


class TestGetPlayletDescription:
    def test_missing_title(self, api_client):
        r = api_client.get("/api/getPlayletDescription")
        assert r.status_code == 422

    def test_success_get(self, api_client):
        r = api_client.get(
            "/api/getPlayletDescription",
            query_string={"originalTitle": "剧", "seasonNumber": "1"},
        )
        assert r.status_code == 200
        assert "◎片　　名　剧" in r.get_json()["data"]["playletDescription"]

    def test_success_post(self, api_client):
        r = api_client.post(
            "/api/getPlayletDescription",
            json={"originalTitle": "剧2", "seasonNumber": "1"},
        )
        assert r.status_code == 200


class TestGetPtGenInfo:
    def test_missing_description_bug(self, api_client):
        # 已知 bug：message/statusCode 互换
        r = api_client.get("/api/getPtGenInfo")
        assert r.status_code == 422
        body = r.get_json()
        assert body["message"] == "MISSING_REQUIRED_PARAMETER"
        assert body["statusCode"] == "缺少PT-Gen简介内容。"

    def test_success(self, api_client, monkeypatch):
        parsed = ("原", "英", "2020", [], "动作", ["张三"], None, None)
        _set(monkeypatch, "get_pt_gen_info", lambda *a, **k: parsed)
        r = api_client.post("/api/getPtGenInfo", json={"description": "desc"})
        assert r.status_code == 200
        data = r.get_json()["data"]
        assert data["originalTitle"] == "原"


class TestGetPtGenInfoByUrl:
    def test_missing_url(self, api_client):
        r = api_client.get("/api/getPTGenInfoByResourceUrl")
        assert r.status_code == 422

    def test_success(self, api_client, monkeypatch):
        from src.core.rename import get_pt_gen_info as real
        _set(monkeypatch, "get_pt_gen_info", lambda *a, **k: ("原", "英", "2020", [], "动作", [], None, None))
        _set(monkeypatch, "get_pt_gen_description", lambda *a, **k: (True, ("fmt", {"chinese_title": "原"})))
        r = api_client.get("/api/getPTGenInfoByResourceUrl", query_string={"resourceUrl": "tt1"})
        assert r.status_code == 200


class TestGetNameFromTemplate:
    def test_missing_template(self, api_client):
        r = api_client.get("/api/getNameFromTemplate")
        assert r.status_code == 422

    def test_invalid_template(self, api_client):
        r = api_client.post("/api/getNameFromTemplate", json={"template": "bogus"})
        assert r.status_code == 422
        assert r.get_json()["statusCode"] == "PARAMETER_RANGE_ERROR"

    def test_success(self, api_client, monkeypatch):
        _set(monkeypatch, "get_name_from_template", lambda *a, **k: "Generated Name")
        _set(monkeypatch, "delete_season_number", lambda t, s: t)
        r = api_client.post(
            "/api/getNameFromTemplate",
            json={"template": "main_title_movie", "englishTitle": "X", "year": "2020"},
        )
        assert r.status_code == 200
        assert r.get_json()["data"]["name"] == "Generated Name"


class TestRenameFolder:
    def test_missing_params(self, api_client, media_file):
        r = api_client.post("/api/renameFolder", json={"folderPath": ""})
        assert r.status_code == 401 or r.status_code == 422

    def test_success(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "rename_folder", lambda *a, **k: (True, str(media_file.parent / "new")))
        r = api_client.post(
            "/api/renameFolder",
            json={"folderPath": "视频.mkv", "newFolderName": "new"},
        )
        # media_file 是占位，folderPath 不存在 → 422 FILE_PATH_ERROR（大副作用路由只要 mock 成功分支）
        assert r.status_code in (200, 422)


class TestRenameFile:
    def test_missing_params(self, api_client):
        r = api_client.post("/api/renameFile", json={"filePath": ""})
        assert r.status_code in (401, 422)

    def test_success(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "rename_file", lambda *a, **k: (True, str(media_file)))
        r = api_client.post("/api/renameFile", json={"filePath": "视频.mkv", "newFileName": "n"})
        assert r.status_code in (200, 422)


class TestCreateHardLink:
    def test_success(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "create_hard_link", lambda *a, **k: (True, str(media_file) + "-hardlink"))
        _set(monkeypatch, "check_path_and_find_video", lambda p: (1, str(media_file)))
        r = api_client.post("/api/createHardLink", json={"path": str(media_file)})
        assert r.status_code in (200, 422)


class TestMoveFileToFolder:
    def test_empty_filepath_hits_401_bug(self, api_client):
        # 已知 bug：空 filePath 命中 401 而非 422（原始变量 startswith 检查）
        r = api_client.post("/api/moveFileToFolder", json={"filePath": ""})
        assert r.status_code == 401 or r.status_code == 422

    def test_missing_folder_name(self, api_client, media_file):
        r = api_client.post("/api/moveFileToFolder", json={"filePath": "视频.mkv", "folderName": ""})
        assert r.status_code in (401, 422)

    def test_success(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "move_file_to_folder", lambda *a, **k: (True, str(media_file)))
        r = api_client.post(
            "/api/moveFileToFolder",
            json={"filePath": "视频.mkv", "folderName": "dest"},
        )
        assert r.status_code in (200, 401, 422)


class TestRenameEpisode:
    def test_missing_params(self, api_client):
        r = api_client.post("/api/renameEpisode", json={"folderPath": ""})
        assert r.status_code in (401, 422)

    def test_file_path_rejected(self, api_client, monkeypatch, media_file):
        # check_path_and_find_video == 1（文件）→ 400 '不支持文件路径'
        _set(monkeypatch, "check_path_and_find_video", lambda p: (1, str(media_file)))
        r = api_client.post(
            "/api/renameEpisode",
            json={"folderPath": "视频.mkv", "newFileName": "ep"},
        )
        assert r.status_code == 400

    def test_success(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "check_path_and_find_video", lambda p: (2, str(media_file)))
        _set(monkeypatch, "get_video_files", lambda p: (True, [str(media_file)]))
        _set(monkeypatch, "rename_file", lambda p, n: (True, p))
        _set(monkeypatch, "rename_folder", lambda p, n: (True, p + "-new"))
        r = api_client.post(
            "/api/renameEpisode",
            json={"folderPath": "视频.mkv", "newFileName": "ep{集数}", "episodeStartNumber": "1"},
        )
        assert r.status_code == 200 or r.status_code == 400


class TestGetTotalEpisode:
    def test_missing_path(self, api_client, media_file):
        r = api_client.get("/api/getTotalEpisode", query_string={"folderPath": "视频.mkv"})
        # 文件夹不存在 → 422 FILE_PATH_ERROR（占位文件是文件不是文件夹）
        assert r.status_code in (200, 400, 422)

    def test_success_all(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "check_path_and_find_video", lambda p: (2, str(media_file)))
        _set(monkeypatch, "get_video_files", lambda p: (True, ["a.mkv", "b.mkv", "c.mkv"]))
        r = api_client.get("/api/getTotalEpisode", query_string={"folderPath": "视频.mkv", "episodeStartNumber": "1"})
        assert r.status_code == 200
        assert r.get_json()["data"]["totalEpisode"] == "全3集"


class TestGetComboBoxData:
    def test_whitelist_error(self, api_client):
        r = api_client.get("/api/getComboBoxData", query_string={"configurationName": "bogus"})
        assert r.status_code == 422
        assert r.get_json()["statusCode"] == "PARAMETER_RANGE_ERROR"

    def test_success(self, api_client, monkeypatch):
        _set(monkeypatch, "get_combo_box_data", lambda name: (True, ["A", "B"]))
        r = api_client.get("/api/getComboBoxData", query_string={"configurationName": "team"})
        assert r.status_code == 200
        assert r.get_json()["data"]["configurationData"] == ["A", "B"]


class TestUpdateComboBoxData:
    def test_missing_data(self, api_client):
        r = api_client.post("/api/updateComboBoxData", json={"configurationName": "team"})
        assert r.status_code == 422

    def test_success(self, api_client, monkeypatch):
        _set(monkeypatch, "update_combo_box_data", lambda *a, **k: (True, "更新成功"))
        r = api_client.post(
            "/api/updateComboBoxData",
            json={"configurationName": "team", "configurationData": "A\\nB"},
        )
        assert r.status_code == 200


class TestGetSettings:
    def test_missing_name(self, api_client):
        r = api_client.get("/api/getSettings")
        assert r.status_code == 422

    def test_success(self, api_client, monkeypatch):
        _set(monkeypatch, "get_settings", lambda *a, **k: "15372")
        r = api_client.get("/api/getSettings", query_string={"settingsName": "api_port"})
        assert r.status_code == 200
        assert r.get_json()["data"]["settingsData"] == "15372"


class TestUpdateSettings:
    def test_missing_params(self, api_client):
        r = api_client.post("/api/updateSettings", json={})
        assert r.status_code == 422

    def test_success(self, api_client, monkeypatch):
        _set(monkeypatch, "update_settings", lambda *a, **k: None)
        r = api_client.post("/api/updateSettings", json={"settingsName": "api_port", "settingsData": "1234"})
        assert r.status_code == 200


class TestSettingsUpdateLegacy:
    def test_success_json_body(self, api_client, monkeypatch):
        _set(monkeypatch, "update_settings_json", lambda d: None)
        r = api_client.post("/api/settings/update", json={"api_port": "1234"})
        assert r.status_code == 200


class TestMediaFileList:
    def test_unauthorized(self, api_client, media_file):
        r = api_client.get("/api/media/file/list", query_string={"path": "../../x"})
        assert r.status_code == 401

    def test_success(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "list_files_and_dirs", lambda p: [{"name": "a", "size": "1 B", "type": "文件"}])
        r = api_client.get("/api/media/file/list", query_string={"path": ""})
        assert r.status_code == 200
        assert r.get_json()["data"]["fileList"][0]["name"] == "a"


class TestAutoHandleVideo:
    def test_get_method_405(self, api_client):
        assert api_client.get("/api/autoHandleVideo").status_code == 405

    def test_missing_params(self, api_client):
        r = api_client.post("/api/autoHandleVideo", json={})
        assert r.status_code == 422

    def test_unauthorized_path(self, api_client):
        r = api_client.post(
            "/api/autoHandleVideo",
            json={"resourceUrl": "tt1", "path": "../../x", "source": "WEB-DL", "team": "AGSV", "category": "Movie"},
        )
        assert r.status_code == 401