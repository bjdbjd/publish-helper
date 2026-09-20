"""Tests for src.core.rename: naming engine, PT-Gen parsing, file operations.

依赖 conftest 的隔离 fixture：mock_settings（临时 settings）、fake_mediainfo（伪 track）、
chdir_to_tmp（cwd 隔离，防止写回真实 static/）。
"""

import errno
import os

import pytest

from src.core.rename import (
    approximate_resolution_by_width,
    create_hard_link,
    extract_numbers,
    get_name_from_template,
    get_pt_gen_info,
    get_video_info,
    move_file_to_folder,
    rename_file,
    rename_folder,
)
from tests.conftest import make_track


# ---------------------------------------------------------------- get_video_info


class TestGetVideoInfo:
    def test_missing_file(self):
        ok, payload = get_video_info("/nonexistent/ghost.mkv")
        assert ok is False
        assert payload == ["视频文件路径不存在"]

    def test_returns_9_element_list(self, fake_mediainfo, monkeypatch):
        fake_mediainfo.tracks = [
            make_track("General", other_frame_rate=["23.976 FPS"]),
            make_track(
                "Video",
                other_width=["1 920 pixels"],
                other_height=["1 080 pixels"],
                other_format=["AVC"],
                writing_library="x264 core 155",
                other_hdr_format=["SMPTE ST 2086, HDR10 compatible"],
                other_bit_depth=["10 bits"],
            ),
            make_track(
                "Audio",
                commercial_name="Dolby Digital Plus",
                channel_layout="L R C LFE Ls Rs",
                other_language="Chinese",
            ),
        ]
        tmp = fake_mediainfo  # noqa
        # 让 MediaInfo.parse 返回 fake 本身；fake.to_json 也会被 rename 用到
        import src.core.rename as rename_mod

        class _Fake:
            tracks = fake_mediainfo.tracks
            def to_json(self):
                import json
                return json.dumps({"tracks": [t.__dict__ for t in self.tracks]})
        monkeypatch.setattr(rename_mod.MediaInfo, "parse", staticmethod(lambda path: _Fake()))

        # 用一个存在的占位文件路径（get_video_info 先 os.path.exists 检查）
        import tempfile
        p = tempfile.mktemp(suffix=".mkv")
        open(p, "w").close()
        try:
            ok, info = get_video_info(p)
        finally:
            os.remove(p)
        assert ok is True
        assert len(info) == 9
        video_format, video_codec, bit_depth, hdr, frame_rate, audio_codec, channels, audio_num, tags = info
        assert video_format == "1080p"
        assert video_codec == "x264"
        assert bit_depth == "10bit"
        assert hdr == "HDR10"
        assert audio_codec == "DDP"
        assert channels == "5.1"
        assert audio_num == ""  # 单音轨
        assert "国语" in tags

    def test_dual_audio_num(self, fake_mediainfo, monkeypatch):
        import src.core.rename as rename_mod
        import tempfile
        holder = {}
        holder["tracks"] = [
            make_track("Video", other_width=["1 920 pixels"], other_height=["1 080 pixels"],
                       other_format=["AVC"],
                       other_hdr_format=[""], other_bit_depth=[""], writing_library=""),
            make_track("Audio", commercial_name="AAC", channel_layout="L R", other_language="Chinese"),
            make_track("Audio", commercial_name="AAC", channel_layout="L R", other_language="English"),
        ]
        class _Fake:
            @property
            def tracks(self):
                return holder["tracks"]
            def to_json(self):
                import json
                return json.dumps({"tracks": [t.__dict__ for t in holder["tracks"]]})
        monkeypatch.setattr(rename_mod.MediaInfo, "parse", staticmethod(lambda path: _Fake()))
        p = tempfile.mktemp(suffix=".mkv"); open(p, "w").close()
        try:
            ok, info = get_video_info(p)
        finally:
            os.remove(p)
        assert ok is True
        assert info[7] == "2Audio"
        assert "国语" in info[8]
        assert "英语" in info[8]

    def test_portrait_height_gt_width_uses_height(self, fake_mediainfo, monkeypatch):
        # 修复：height 检查错写（other_width→other_height）导致竖屏资源误标分辨率
        import src.core.rename as rename_mod
        import tempfile
        holder = {}
        holder["tracks"] = [
            make_track("Video", other_width=["1 080 pixels"], other_height=["1 920 pixels"],
                       other_format=["AVC"],
                       other_hdr_format=[""], other_bit_depth=[""], writing_library=""),
        ]

        class _Fake:
            @property
            def tracks(self):
                return holder["tracks"]
            def to_json(self):
                import json
                return json.dumps({"tracks": [t.__dict__ for t in holder["tracks"]]})

        monkeypatch.setattr(rename_mod.MediaInfo, "parse", staticmethod(lambda path: _Fake()))
        p = tempfile.mktemp(suffix=".mkv"); open(p, "w").close()
        try:
            ok, info = get_video_info(p)
        finally:
            os.remove(p)
        assert ok is True
        # height 1920 > width 1080 → 选较长边 height → '1080p'
        assert info[0] == "1080p"


# ----------------------------------------------------------- get_name_from_template


class TestGetNameFromTemplate:
    def test_main_title_movie_replacements(self, mock_settings):
        mock_settings.patch("src.core.rename")
        name = get_name_from_template(
            "Godzilla", "哥斯拉", "1", "1", "2023", "1080p", "WEB-DL", "x264",
            "10bit", "HDR10", "", "DDP", "5.1", "", "AGSV", "", "1", "", "", "动作", "演员A",
            "main_title_movie",
        )
        # main_title_ 后处理：下划线→空格、连续空白压一个、' -'→'-'
        assert "Godzilla" in name
        assert "_" not in name

    def test_file_name_illegal_chars_replaced(self, mock_settings):
        mock_settings.patch("src.core.rename")
        name = get_name_from_template(
            "Godzilla", "哥:斯/拉", "1", "1", "2023", "1080p", "WEB-DL", "x264",
            "10bit", "HDR10", "", "DDP", "5.1", "", "AGSV", "", "1", "", "", "动作", "演员A",
            "file_name_tv",
        )
        # file_name_ 后处理：Windows 非法字符→'.'、连续点压缩、首字符裁剪
        assert "哥:斯/拉" not in name
        assert ":" not in name
        assert "/" not in name
        assert ".." not in name

    def test_second_title_pipe_trim(self, mock_settings):
        mock_settings.patch("src.core.rename")
        name = get_name_from_template(
            "Godzilla", "哥斯拉", "1", "1", "2023", "1080p", "WEB-DL", "x264",
            "10bit", "HDR10", "", "DDP", "5.1", "", "AGSV", "别名A / 别名B", "1", "", "", "动作", "演员A",
            "second_title_movie",
        )
        assert "哥斯拉" in name
        assert "类型：动作" in name
        assert "演员：演员A" in name


# ---------------------------------------------------------------- file operations


class TestRenameFile:
    def test_renames_keeping_extension(self, tmp_path):
        f = tmp_path / "a.mkv"
        f.write_bytes(b"x")
        ok, new = rename_file(str(f), "b:new_name")
        assert ok is True
        # 非法字符 ':' 被清洗为 '.'
        assert new.endswith(".mkv")
        assert "b.new_name.mkv" in new
        assert (tmp_path / "b.new_name.mkv").exists()

    def test_missing_file_error(self, tmp_path):
        ok, payload = rename_file(str(tmp_path / "ghost.mkv"), "x")
        assert ok is False
        assert "未找到文件" in payload


class TestRenameFolder:
    def test_renames_folder(self, tmp_path):
        d = tmp_path / "old_name"
        d.mkdir()
        ok, new = rename_folder(str(d), "new_name")
        assert ok is True
        assert new.endswith("new_name")
        assert (tmp_path / "new_name").is_dir()

    def test_non_directory_raises_valueerror(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        with pytest.raises(ValueError, match="提供的路径不是一个目录或不存在"):
            rename_folder(str(f), "x")


class TestMoveFileToFolder:
    def test_already_in_folder_returns_unchanged(self, tmp_path):
        sub = tmp_path / "movie"
        sub.mkdir()
        f = sub / "a.mkv"
        f.write_bytes(b"x")
        ok, path = move_file_to_folder(str(f), "movie")
        assert ok is True
        assert path == str(f)

    def test_moves_into_new_folder(self, tmp_path):
        f = tmp_path / "a.mkv"
        f.write_bytes(b"x")
        ok, new = move_file_to_folder(str(f), "my_movie")
        assert ok is True
        assert (tmp_path / "my_movie" / "a.mkv").exists()


class TestCreateHardLink:
    def test_file_link(self, tmp_path):
        f = tmp_path / "a.mkv"
        f.write_bytes(b"x")
        ok, link = create_hard_link(str(f))
        assert ok is True
        assert link.endswith("a-hardlink.mkv")
        assert os.path.exists(link)

    def test_folder_link_tree(self, tmp_path):
        d = tmp_path / "show"
        d.mkdir()
        (d / "a.mkv").write_bytes(b"x")
        ok, link = create_hard_link(str(d))
        assert ok is True
        assert link == str(d) + "-hardlink"
        assert os.path.exists(os.path.join(link, "a-hardlink.mkv"))

    def test_exdev_error(self, tmp_path, monkeypatch):
        f = tmp_path / "a.mkv"
        f.write_bytes(b"x")
        def _link(src, dst):
            raise OSError(errno.EXDEV, "cross-device")
        monkeypatch.setattr(os, "link", _link)
        ok, msg = create_hard_link(str(f))
        assert ok is False
        assert "different file systems" in msg

    def test_missing_path(self, tmp_path):
        ok, msg = create_hard_link(str(tmp_path / "ghost"))
        assert ok is False
        assert "Path does not exist" in msg


# ----------------------------------------------------------------- resolution


class TestResolutionHelpers:
    def test_approximate_1080p(self):
        assert approximate_resolution_by_width(1600) == "1080p"

    def test_approximate_fallback_240p(self):
        assert approximate_resolution_by_width(0) == "240p"

    def test_extract_numbers(self):
        # 拼接全部数字位（不跨分隔符拆分）
        assert extract_numbers("3840x2160") == 38402160
        assert extract_numbers("1 920 pixels") == 1920
        assert extract_numbers("no digits") is None


# ------------------------------------------------------------------ get_pt_gen_info


# ❁ 前缀格式示例（另一家 PT-Gen 输出）
F_DESCRIPTION = """❁ 片　　名:　猫的报恩
❁ 译　　名:　The Cat Returns / 猫的恩赐
❁ 年　　代:　2002
❁ 类　　别:　动画 / 奇幻 / 冒险
❁ 主　　演:　池胁千鹤 / 袴田吉彦 / 丹下樱
❁ 简　　介
"""


class TestGetPtGenInfoFallbackFormats:
    def test_circle_prefix_formats(self):
        original, english, year, other, categories, actors, episodes, season = get_pt_gen_info(
            F_DESCRIPTION
        )
        assert "猫的报恩" in original
        assert "The Cat Returns" in english
        assert year == "2002"
        assert categories == "动画 / 奇幻 / 冒险"
        assert len(actors) >= 1

    def test_no_category_set_to_none(self):
        # 类别以 '语' 开头（如被误判为语言行）→ 返回 '暂无分类'
        desc = "◎片　　名　X\n◎年　　代　2020\n◎类　　别　语言/abc\n"
        original, _, _, _, categories, _, _, _ = get_pt_gen_info(desc)
        assert categories == "暂无分类"

    def test_actor_stops_at_jian(self):
        desc = (
            "◎片　　名　X\n◎年　　代　2020\n"
            "◎主　　演　张三\n简　介\n◎简　　介\n"
        )
        original, _, _, _, _, actors, _, _ = get_pt_gen_info(desc)
        assert len(actors) == 1  # '简' 终止，不继续收集
        assert actors == ["张三"]
