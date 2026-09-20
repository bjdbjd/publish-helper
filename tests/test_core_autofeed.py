"""Tests for src.core.autofeed: auto-feed link construction with base64 tail."""

from src.core.autofeed import get_auto_feed_link


TEMPLATE = (
    "https://upload.example/upload.php"
    "#separator#name#linkstr#{主标题}#linkstr#small_descr#linkstr#{副标题}"
    "#linkstr#torrent_name#linkstr#{种子名称}#linkstr#torrent_url#linkstr#{种子链接}"
)


class TestGetAutoFeedLink:
    def test_success_with_separator(self, mock_settings):
        mock_settings.patch("src.core.autofeed")
        mock_settings.set("auto_feed_link", TEMPLATE)
        ok, link = get_auto_feed_link(
            "Movie Title", "副标题", "简介", "mediainfo", "Movie.Title", "AGSV", "WEB-DL", "电影",
            "http://127.0.0.1/api/getFile?filePath=/tmp/m.torrent",
        )
        assert ok is True
        # 结果前缀保留未编码部分
        assert link.startswith("https://upload.example/upload.php#separator#")
        # 尾部是 base64 编码的整段替换后的字符串
        tail = link.split("#separator#")[-1]
        # 用占位符已全部被 quote 化后的原始尾部再 base64 应能对回来
        import base64 as b64
        decoded = b64.b64decode(tail.encode()).decode()
        assert "{主标题}" not in decoded  # 占位符已被替换
        assert "Movie+Title" in decoded or "Movie%20Title" in decoded

    def test_no_separator_returns_false(self, mock_settings):
        mock_settings.patch("src.core.autofeed")
        mock_settings.set("auto_feed_link", "https://upload.example/upload.php#nomarker#")
        ok, msg = get_auto_feed_link("T", "S", "D", "M", "F", "T", "S", "电影", "url")
        assert ok is False
        assert msg == "您设置的auto_feed_link不符合规则"
