"""S1/S3/S4/S5/S7/S8/S10/S11/S15/S16/S17 等待补缺陷的锁定用例。

每一条都对应 docs/BUSINESS_LOGIC.md §5.3 的一个 S 编号，断言的是**代码当前的
真实行为**（含缺陷），不是期望行为。用例里都标注了 S 编号与源码行号，修 bug 时
请连同注释一起更新。

本文件只做「现状锁定」，不主张这些行为是正确的。
"""

import json
import os

import pytest

import src.api.startapi as sa


def _set(monkeypatch, name, value):
    monkeypatch.setattr(f"src.api.startapi.{name}", value)


# ---------------------------------------------------------------- S4 事实必填

class TestS4PlayletSeasonNumberDefault:
    """S4（已修）：省略 `seasonNumber` 时按第 1 季处理，不再 500。"""

    def test_omitting_season_number_is_200(self, api_client):
        r = api_client.get("/api/getPlayletDescription?originalTitle=X&year=2020")
        assert r.status_code == 200
        assert r.get_json()["statusCode"] == "OK"
        # 第 1 季不追加「第N季」后缀
        assert "第" not in r.get_json()["data"]["playletDescription"].split("◎片")[0]
        assert "片　　名" in r.get_json()["data"]["playletDescription"]

    def test_with_season_number_is_200(self, api_client):
        r = api_client.get(
            "/api/getPlayletDescription?originalTitle=X&year=2020&seasonNumber=1"
        )
        assert r.status_code == 200
        assert "片　　名" in r.get_json()["data"]["playletDescription"]

    def test_non_numeric_season_number_is_500(self, api_client):
        """非数字仍会抛（`int('abc')`），该路径未做校验，属既有行为。"""
        r = api_client.get(
            "/api/getPlayletDescription?originalTitle=X&year=2020&seasonNumber=abc"
        )
        assert r.status_code == 500
        assert r.get_json()["statusCode"] == "GENERAL_ERROR"


# ------------------------------------------------------- S17 405/404 不套包络

class TestS17MethodErrorsAreJson:
    """S17（已修）：注册了 404/405 处理器，错方法与未知路径也走统一包络。"""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("delete", "/api/getMediaInfo"),   # 只注册了 GET
            ("get", "/api/uploadPicture"),     # 只注册了 POST
        ],
    )
    def test_wrong_method_returns_json_405(self, api_client, method, path):
        r = getattr(api_client, method)(path)
        assert r.status_code == 405
        assert "application/json" in r.headers["Content-Type"]
        body = r.get_json()
        assert body["statusCode"] == "METHOD_NOT_ALLOWED"
        assert "message" in body and "data" in body

    def test_unregistered_path_returns_json_404(self, api_client):
        r = api_client.get("/api/no-such-route-exists")
        assert r.status_code == 404
        assert "application/json" in r.headers["Content-Type"]
        assert r.get_json()["statusCode"] == "NOT_FOUND"


# ------------------------------------------------- S7 media/file/list 失败键名

class TestS7MediaFileListErrorKey:
    """S7（已修）：失败分支的数据键改为 `fileList`，与成功分支一致。"""

    def test_error_branch_uses_file_list_key(self, api_client, monkeypatch, media_file):
        def _boom(_path):
            raise RuntimeError("boom")

        _set(monkeypatch, "list_files_and_dirs", _boom)
        r = api_client.get("/api/media/file/list?path=.")
        assert r.status_code == 500
        assert r.get_json()["statusCode"] == "GENERAL_ERROR"
        data = r.get_json()["data"]
        assert data["fileList"] == []
        assert "description" not in data


# ------------------------------------------------------- S8 description 是元组

class TestS8DescriptionIsString:
    """S8（已修）：`description` 返回格式化后的字符串，不再是未解包的元组。"""

    def test_description_is_string(self, api_client, monkeypatch, media_file):
        _set(
            monkeypatch,
            "get_pt_gen_description",
            lambda *a, **k: (True, ("FMT", {"raw": 1})),
        )
        r = api_client.get("/api/getPTGenInfoByResourceUrl?resourceUrl=tt1234567")
        assert r.status_code == 200
        desc = r.get_json()["data"]["description"]
        assert desc == "FMT", "应是 format_data 字符串，而不是 (format, data) 元组"


# ------------------------------------------------- S1 越域检查退化（兄弟目录）

class TestS1SiblingDirectoryEscape:
    """S1（已修）：media 边界改为按路径分隔符判断，`../` 兄弟目录不再可越权访问。"""

    def test_file_list_cannot_read_sibling_directory(self, api_client, media_file, tmp_path):
        evil = tmp_path / "media_evil"
        evil.mkdir()
        (evil / "secret.txt").write_text("x", encoding="utf-8")

        r = api_client.get("/api/media/file/list?path=../media_evil")
        assert r.status_code == 401, "`../` 兄弟目录应被拦住"
        assert r.get_json()["statusCode"] == "UNAUTHORIZED"

    def test_create_hard_link_empty_path_rejected(self, api_client, media_file):
        """空 path 不再落到 media 根并创建兄弟目录（原先是 200 + 真实建目录）。"""
        r = api_client.post("/api/createHardLink", json={"path": ""})
        assert r.status_code == 422
        assert r.get_json()["statusCode"] == "MISSING_REQUIRED_PARAMETER"
        sibling = os.path.join(os.getcwd(), "media-hardlink")
        assert not os.path.isdir(sibling), "不应再创建兄弟目录"

    def test_prefix_lookalike_directory_rejected(self, api_client, media_file, tmp_path):
        """`media_evil` 前缀 lookalike 不再通过字符串 startsWith 检查。"""
        evil = tmp_path / "media_evil"
        evil.mkdir()
        r = api_client.get("/api/media/file/list?path=../media_evil")
        assert r.status_code == 401


class TestS2MoveFileToFolderBoundary:
    """S2（已修）：越域检查改用 join 后的绝对路径，相对路径不再被误判 401。"""

    def test_relative_path_works(self, api_client, monkeypatch, media_file):
        """相对路径现在是正常用法（修复前一律 401）。"""
        _set(monkeypatch, "move_file_to_folder", lambda *a, **k: (True, str(media_file)))
        r = api_client.post(
            "/api/moveFileToFolder", json={"filePath": "视频.mkv", "folderName": "dest"}
        )
        assert r.status_code == 200
        assert r.get_json()["statusCode"] == "OK"

    def test_absolute_path_works(self, api_client, monkeypatch, media_file):
        _set(monkeypatch, "move_file_to_folder", lambda *a, **k: (True, str(media_file)))
        r = api_client.post(
            "/api/moveFileToFolder",
            json={"filePath": os.path.abspath(str(media_file)), "folderName": "dest"},
        )
        assert r.status_code == 200
        assert r.get_json()["statusCode"] == "OK"

    def test_escape_still_rejected(self, api_client, media_file):
        r = api_client.post(
            "/api/moveFileToFolder", json={"filePath": "../../etc/passwd", "folderName": "d"}
        )
        assert r.status_code == 401
        assert r.get_json()["statusCode"] == "UNAUTHORIZED"

    def test_empty_path_is_422(self, api_client, media_file):
        """空路径不再落 401，而是命中原本就是死代码的 422 分支。"""
        r = api_client.post("/api/moveFileToFolder", json={"filePath": "", "folderName": "d"})
        assert r.status_code == 422
        assert r.get_json()["statusCode"] == "MISSING_REQUIRED_PARAMETER"


# ------------------------------------------------------- S9 响应形状零断言

class TestS9ResponseShapes:
    """S9/S9b：成功响应体的路径字段形状此前完全没有断言。"""

    def test_create_hard_link_returns_absolute_path(self, api_client, monkeypatch, media_file):
        link = str(media_file.parent / "视频-hardlink.mkv")
        _set(monkeypatch, "create_hard_link", lambda *a, **k: (True, link))
        r = api_client.post("/api/createHardLink", json={"path": str(media_file)})
        assert r.status_code == 200
        got = r.get_json()["data"]["hardLinkPath"]
        # S9：replace(media_path + '/') 不命中 → 返回未裁剪的绝对路径
        assert os.path.isabs(got)
        assert got == link

    def test_rename_file_does_not_duplicate_extension(self, api_client, monkeypatch, media_file):
        """S9c（已修）：newFileName 自带扩展名时不再重复追加。"""
        _set(monkeypatch, "rename_file", lambda *a, **k: (True, "z.mkv"))
        r = api_client.post(
            "/api/renameFile", json={"filePath": "视频.mkv", "newFileName": "z.mkv"}
        )
        assert r.status_code == 200
        assert r.get_json()["data"]["newFilePath"] == "z.mkv"


# --------------------------------------------------------------- S13 三态分支

class TestS13TotalEpisodeBranches:
    """S13（已更正为「不是 bug」）：三个分支都可达，逐分支锁定。"""

    def _set_folder(self, monkeypatch, media_file, files):
        _set(monkeypatch, "check_path_and_find_video", lambda p: (2, str(media_file.parent)))
        _set(monkeypatch, "get_video_files", lambda p: (True, files))

    def test_start_one_gives_all(self, api_client, monkeypatch, media_file):
        self._set_folder(monkeypatch, media_file, ["a.mkv", "b.mkv", "c.mkv"])
        r = api_client.get("/api/getTotalEpisode?folderPath=视频.mkv&episodeStartNumber=1")
        assert r.status_code == 200
        assert r.get_json()["data"]["totalEpisode"] == "全3集"

    def test_multi_episode_gives_range(self, api_client, monkeypatch, media_file):
        self._set_folder(monkeypatch, media_file, ["a.mkv", "b.mkv", "c.mkv"])
        r = api_client.get("/api/getTotalEpisode?folderPath=视频.mkv&episodeStartNumber=5")
        assert r.status_code == 200
        assert r.get_json()["data"]["totalEpisode"] == "第5-7集"

    def test_single_episode_gives_single(self, api_client, monkeypatch, media_file):
        """num==1 且 start!=1 → 走 :1501 的 `第N集` 分支（该分支可达）。"""
        self._set_folder(monkeypatch, media_file, ["a.mkv"])
        r = api_client.get("/api/getTotalEpisode?folderPath=视频.mkv&episodeStartNumber=5")
        assert r.status_code == 200
        assert r.get_json()["data"]["totalEpisode"] == "第5集"


# ------------------------------------------------------ S15 settings/update 覆写

class TestS15SettingsUpdateMerges:
    """S15（已修）：`settings/update` 改为合并语义，少传键不再丢键。"""

    def test_partial_payload_keeps_other_keys(self, tmp_path, chdir_to_tmp):
        from src.core.settings_tool import SettingsManager

        m = SettingsManager(tmp_path / "settings.json")
        before = m.get_all_settings()
        assert len(before) >= 30, "默认表应有几十个键"

        m.update_all_settings({"api_port": "1"})
        after = m.get_all_settings()

        assert after["api_port"] == "1"
        assert len(after) == len(before), "S15：其余键应保留（合并语义）"
        assert after["screenshot_number"] == before["screenshot_number"]

    def test_explicit_replace_still_available(self, tmp_path, chdir_to_tmp):
        """`merge=False` 保留旧的整表替换语义（reset_to_defaults 等内部用法）。"""
        from src.core.settings_tool import SettingsManager

        m = SettingsManager(tmp_path / "settings.json")
        m.update_all_settings({"api_port": "1"}, merge=False)
        assert m.get_all_settings() == {"api_port": "1"}


# --------------------------------------------------- S16 screenshotPath/Number

class TestS16ScreenshotPathShape:
    """S16：`screenshotPath` 统一为「相对 media 则裁剪、否则原样」且分隔符归一为 `/`。"""

    def test_number_is_string(self, api_client, monkeypatch, media_file):
        """`screenshotNumber` 是 `str(len(实际返回的图))`，不是入参的回显、也不是 int。"""
        _set(monkeypatch, "get_screenshot", lambda *a, **k: (True, ["temp/pic/a.png"]))
        r = api_client.get("/api/getScreenshot?path=视频.mkv&screenshotNumber=2")
        assert r.status_code == 200
        assert r.get_json()["data"]["screenshotNumber"] == "1", "是字符串且等于实际张数"

    def test_path_under_media_is_trimmed_with_forward_slashes(
        self, api_client, monkeypatch, media_file
    ):
        """media 下的绝对路径被裁成相对形式，且分隔符统一为 `/`。"""
        import os

        abs_pic = os.path.join(str(media_file.parent), "shot.png")
        _set(monkeypatch, "get_screenshot", lambda *a, **k: (True, [abs_pic]))
        r = api_client.get("/api/getScreenshot?path=视频.mkv&screenshotNumber=1")
        assert r.status_code == 200
        assert r.get_json()["data"]["screenshotPath"] == ["shot.png"]

    def test_path_outside_media_returned_as_is(self, api_client, monkeypatch, media_file):
        """不在 media 下的相对存储路径原样返回（不臆造前缀）。"""
        _set(monkeypatch, "get_screenshot", lambda *a, **k: (True, ["temp/pic/a.png"]))
        r = api_client.get("/api/getScreenshot?path=视频.mkv&screenshotNumber=1")
        assert r.status_code == 200
        assert r.get_json()["data"]["screenshotPath"] == ["temp/pic/a.png"]


# ----------------------------------------------------------- S10 鉴权 statusCode

class TestS10UnauthorizedStatusCodes:
    """S10（已统一）：鉴权失败与路由级越域现在都用 `UNAUTHORIZED`。"""

    def test_route_level_escape_uses_unauthorized(self, api_client, media_file):
        r = api_client.get("/api/getMediaInfo?path=../etc/passwd")
        assert r.status_code == 401
        assert r.get_json()["statusCode"] == "UNAUTHORIZED"

    def test_auth_failure_uses_same_constant(self, media_file, monkeypatch):
        """设了 API_AUTH_TOKEN 后缺 header → 同一个 `UNAUTHORIZED`。

        AUTH_TOKEN 是模块 import 时固化的常量，这里直接改模块属性来触发。
        """
        monkeypatch.setattr(sa, "AUTH_TOKEN", "secret-token")
        client = sa.api.test_client()
        r = client.get("/api/getMediaInfo?path=视频.mkv")
        assert r.status_code == 401
        assert r.get_json()["statusCode"] == "UNAUTHORIZED"
