"""Tests for src.core.mediainfo: forum-format MediaInfo text generation."""

from src.core import mediainfo
from src.core.mediainfo import get_media_info
from tests.conftest import make_track


class TestGetMediaInfo:
    def test_missing_file(self):
        ok, msg = get_media_info("/nonexistent/ghost.mkv")
        assert ok is False
        assert msg == "视频文件路径不存在"

    def test_output_alignment_and_basename(self, fake_mediainfo, monkeypatch):
        import json
        fake_mediainfo.tracks = [
            make_track(
                "General",
                complete_name="C:/videos/Movie.mkv",
                other_format=["Matroska"],
                other_duration=["02:00:00.000"],
                other_frame_rate=["23.976 FPS"],
            ),
            make_track(
                "Video",
                other_format=["AVC"],
                other_width=["1 920 pixels"],
                other_height=["1 080 pixels"],
                other_frame_rate=["23.976 FPS"],
            ),
        ]

        class _Fake:
            tracks = fake_mediainfo.tracks
            def to_json(self):
                return json.dumps({"tracks": [t.__dict__ for t in self.tracks]})

        monkeypatch.setattr(mediainfo.MediaInfo, "parse", staticmethod(lambda path: _Fake()))
        # get_media_info 先检查 os.path.exists
        import tempfile, os
        p = tempfile.mktemp(suffix=".mkv")
        open(p, "w").close()
        try:
            ok, output = get_media_info(p)
        finally:
            os.remove(p)
        assert ok is True
        # 标签列对齐：'{label:36}: value'
        assert "Complete name" in output
        assert "Movie.mkv" in output  # basename 去路径
        assert "Matroska" in output
        assert "Format" in output
        # 对齐：'Format' + 空格 + ':' 形式
        for line in output.splitlines():
            if ":" in line and not line.startswith("General"):
                label_part = line.split(":", 1)[0]
                # 标签右对齐到 36 列（含空格）
                assert len(label_part) == 36, f"label '{label_part}' not 36 wide"

    def test_audio_delay_zero_skipped(self, fake_mediainfo, monkeypatch):
        import json, tempfile, os
        fake_mediainfo.tracks = [
            make_track("Audio",
                       other_delay_relative_to_video=["00:00:00.000"],
                       other_format=["AAC"]),
        ]

        class _Fake:
            tracks = fake_mediainfo.tracks
            def to_json(self):
                return json.dumps({"tracks": [t.__dict__ for t in self.tracks]})

        monkeypatch.setattr(mediainfo.MediaInfo, "parse", staticmethod(lambda path: _Fake()))
        p = tempfile.mktemp(suffix=".mkv")
        open(p, "w").close()
        try:
            ok, output = get_media_info(p)
        finally:
            os.remove(p)
        assert ok is True
        # Delay relative to video = 00:00:00.000 被跳过
        assert "Delay relative to video" not in output

    def test_menu_chapter_timestamp_format(self, fake_mediainfo, monkeypatch):
        import json, tempfile, os
        fake_mediainfo.tracks = [
            make_track("Menu", **{"00_00_00000": "Chapter 1", "00_05_30000": "Chapter 2"}),
        ]

        class _Fake:
            tracks = fake_mediainfo.tracks
            def to_json(self):
                return json.dumps({"tracks": [t.__dict__ for t in self.tracks]})

        monkeypatch.setattr(mediainfo.MediaInfo, "parse", staticmethod(lambda path: _Fake()))
        p = tempfile.mktemp(suffix=".mkv")
        open(p, "w").close()
        try:
            ok, output = get_media_info(p)
        finally:
            os.remove(p)
        assert ok is True
        assert "00:00:00.000" in output
        assert "00:05:30.000" in output
        assert "Chapter 1" in output
        assert "Chapter 2" in output

    def test_suffix_control(self, fake_mediainfo, monkeypatch, mock_settings):
        import json, tempfile, os
        mock_settings.patch("src.core.mediainfo")
        fake_mediainfo.tracks = [make_track("General", other_format=["Matroska"])]

        class _Fake:
            tracks = fake_mediainfo.tracks
            def to_json(self):
                return json.dumps({"tracks": [t.__dict__ for t in self.tracks]})

        monkeypatch.setattr(mediainfo.MediaInfo, "parse", staticmethod(lambda path: _Fake()))
        p = tempfile.mktemp(suffix=".mkv")
        open(p, "w").close()
        try:
            # media_info_suffix 默认 True → 有水印
            ok, output = get_media_info(p)
        finally:
            os.remove(p)
        assert ok is True
        assert "Created by Publish Helper" in output

        # 关闭 suffix → 无水印
        mock_settings.set("media_info_suffix", False)
        p2 = tempfile.mktemp(suffix=".mkv")
        open(p2, "w").close()
        try:
            ok, output2 = get_media_info(p2)
        finally:
            os.remove(p2)
        assert ok is True
        assert "Created by Publish Helper" not in output2
