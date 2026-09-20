"""Tests for src.core.torrent: .torrent creation via torf."""

import os

from src.core.torrent import make_torrent


class TestMakeTorrent:
    def test_missing_path(self, tmp_path):
        ok, msg = make_torrent(str(tmp_path / "ghost"), str(tmp_path / "out"))
        assert ok is False
        assert msg == "提供的路径不存在"

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "empty_dir"
        d.mkdir()
        ok, msg = make_torrent(str(d), str(tmp_path / "out"))
        assert ok is False
        assert msg == "路径指向一个空目录"

    def test_creates_torrent_file(self, tmp_path):
        src = tmp_path / "movie.mkv"
        src.write_bytes(b"\x00" * 1024)
        out_dir = tmp_path / "torrents"
        ok, torrent_path = make_torrent(str(src), str(out_dir))
        assert ok is True
        # 路径分隔符可能是 / 或 \，用 exists + basename 判定
        assert os.path.basename(torrent_path) == "movie.mkv.torrent"
        assert os.path.exists(torrent_path)

    def test_overwrites_existing_torrent(self, tmp_path):
        src = tmp_path / "movie.mkv"
        src.write_bytes(b"\x00" * 1024)
        out_dir = tmp_path / "torrents"
        out_dir.mkdir()
        target = out_dir / "movie.mkv.torrent"
        target.write_bytes(b"old-content-that-must-be-replaced")
        ok, torrent_path = make_torrent(str(src), str(out_dir))
        assert ok is True
        assert os.path.basename(torrent_path) == "movie.mkv.torrent"
        # 先删后写：不再是旧内容
        data = target.read_bytes()
        assert data != b"old-content-that-must-be-replaced"
        assert len(data) > 0

    def test_directory_source(self, tmp_path):
        d = tmp_path / "show"
        d.mkdir()
        (d / "ep1.mkv").write_bytes(b"x")
        ok, torrent_path = make_torrent(str(d), str(tmp_path))
        assert ok is True
        assert torrent_path.endswith("show.torrent")
        assert os.path.exists(torrent_path)


class TestTorrentMetadata:
    """用真实 torf 校验元数据常量（trackers/created_by）。"""

    def test_trackers_and_created_by(self, tmp_path):
        import torf
        src = tmp_path / "movie.mkv"
        src.write_bytes(b"\x00" * 512)
        ok, torrent_path = make_torrent(str(src), str(tmp_path))
        assert ok is True
        t = torf.Torrent.read(torrent_path)
        # torf 的 trackers 是分组的嵌套列表
        flat = [tr for group in t.trackers for tr in group]
        assert "https://tracker.example.com/announce" in flat
        assert t.created_by == "Publish Helper"
