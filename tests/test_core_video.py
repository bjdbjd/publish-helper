"""Tests for src.core.video: path resolution, video file listing, filename helpers."""

from src.core.video import (
    MIN_WIDTHS,
    VIDEO_EXTENSIONS,
    check_path_and_find_video,
    delete_season_number,
    get_video_files,
    is_filename_too_long,
)


class TestConstants:
    def test_video_extensions_count(self):
        assert len(VIDEO_EXTENSIONS) == 11
        assert ".mkv" in VIDEO_EXTENSIONS
        assert ".mp4" in VIDEO_EXTENSIONS

    def test_min_widths(self):
        assert MIN_WIDTHS["1600"] == "1080p"
        assert MIN_WIDTHS["3840"] if "3840" in MIN_WIDTHS else True  # sanity


class TestCheckPathAndFindVideo:
    def test_file_video_returns_1(self, tmp_path):
        f = tmp_path / "movie.mkv"
        f.write_bytes(b"x")
        code, path = check_path_and_find_video(str(f))
        assert code == 1
        assert path == str(f)

    def test_case_insensitive_extension(self, tmp_path):
        f = tmp_path / "movie.MKV"
        f.write_bytes(b"x")
        code, path = check_path_and_find_video(str(f))
        assert code == 1

    def test_non_video_file_returns_0(self, tmp_path):
        f = tmp_path / "note.txt"
        f.write_text("hi")
        code, msg = check_path_and_find_video(str(f))
        assert code == 0
        assert "不符合视频类型" in msg

    def test_dir_with_video_returns_2(self, tmp_path):
        sub = tmp_path / "show"
        sub.mkdir()
        (sub / "ep1.mkv").write_bytes(b"x")
        code, path = check_path_and_find_video(str(sub))
        assert code == 2
        assert path.endswith("ep1.mkv")

    def test_dir_without_video_returns_0(self, tmp_path):
        sub = tmp_path / "empty"
        sub.mkdir()
        (sub / "readme.txt").write_text("x")
        code, msg = check_path_and_find_video(str(sub))
        assert code == 0
        assert msg == "文件夹中没有符合类型的视频文件"

    def test_nonexistent_returns_0(self, tmp_path):
        code, msg = check_path_and_find_video(str(tmp_path / "ghost"))
        assert code == 0
        assert "既不是文件也不是文件夹" in msg

    def test_trailing_slash_normalized(self, tmp_path):
        f = tmp_path / "movie.mkv"
        f.write_bytes(b"x")
        code, path = check_path_and_find_video(str(f) + "/")
        assert code == 1

    def test_file_prefix_normalized(self, tmp_path):
        f = tmp_path / "movie.mkv"
        f.write_bytes(b"x")
        code, path = check_path_and_find_video("file:///" + str(f))
        assert code == 1


class TestGetVideoFiles:
    def test_natural_sort(self, tmp_path):
        for name in ["EP10.mkv", "EP1.mkv", "EP2.mkv"]:
            (tmp_path / name).write_bytes(b"x")
        ok, files = get_video_files(str(tmp_path))
        assert ok is True
        basenames = [f.split("/")[-1].split("\\")[-1] for f in files]
        assert basenames == ["EP1.mkv", "EP2.mkv", "EP10.mkv"]

    def test_non_video_excluded(self, tmp_path):
        (tmp_path / "a.mkv").write_bytes(b"x")
        (tmp_path / "b.txt").write_text("x")
        ok, files = get_video_files(str(tmp_path))
        assert ok is True
        assert len(files) == 1

    def test_invalid_dir_returns_error_list(self, tmp_path):
        ok, payload = get_video_files(str(tmp_path / "ghost"))
        assert ok is False
        # 错误包在单元素列表里
        assert isinstance(payload, list)
        assert "错误" in payload[0]


class TestIsFilenameTooLong:
    def test_exactly_250_false(self):
        assert is_filename_too_long("x" * 250) is False

    def test_251_true(self):
        assert is_filename_too_long("x" * 251) is True


class TestDeleteSeasonNumber:
    def test_no_suffix_keeps_intact(self):
        # "Ni Hao 1983" season=1 不应被改成 "Ni Hao983"
        assert delete_season_number("Ni Hao 1983", "1") == "Ni Hao 1983"

    def test_season_suffix_removed(self):
        assert delete_season_number("Movie Season 1", "1") == "Movie"

    def test_space_number_suffix_removed(self):
        assert delete_season_number("Show 2", "2") == "Show"

    def test_priority_of_longer_suffix(self):
        # ' Season 1' 必须先于 ' 1' 匹配
        assert delete_season_number("Title Season 1", "1") == "Title"