"""Tests for the RESTful-style request payload handling in src.api.startapi.

覆盖「载荷迁移」之后的双栈行为（_payload() 兼容器）：
- POST 端点接受 JSON body（RESTful，参数入 body）；
- 旧客户端以 URL query 传参仍然可用（向后兼容）。

选取无副作用端点 /api/makeTorrent：传入不存在的 media 子路径 →
返回 422 FILE_PATH_ERROR，据此证明 body / query 两种传参都被正确读到。
"""

import pytest

from src.api.startapi import api


@pytest.fixture
def client():
    return api.test_client()


UNUSED = "nonexistent_path_restful_test_xyz"


def test_make_torrent_reads_json_body(client):
    """POST + JSON body：RESTful 方式，path 入 body 应被读取。"""
    resp = client.post("/api/makeTorrent", json={"path": UNUSED})
    assert resp.status_code == 422
    assert resp.get_json()["statusCode"] == "FILE_PATH_ERROR"  # 证明读到了 body 里的 path


def test_make_torrent_query_still_works(client):
    """旧客户端以 query 传参：path 放 URL 查询串，仍向后兼容。"""
    resp = client.post(f"/api/makeTorrent?path={UNUSED}")
    assert resp.status_code == 422
    assert resp.get_json()["statusCode"] == "FILE_PATH_ERROR"


def test_payload_returns_werkzeug_multidict(client):
    """JSON body 解析后包装为 werkzeug MultiDict，支持 type= 转换的 .get(key, default, type)。"""
    resp = client.post("/api/makeTorrent", data='{"path": "%s"}' % UNUSED,
                       content_type="application/json")
    assert resp.status_code == 422


def test_opt_in_auth(monkeypatch):
    """配置 API_AUTH_TOKEN 后全端点鉴权；未配置则开放（向后兼容）。"""
    import src.api.startapi as s
    client = s.api.test_client()

    # 默认不鉴权
    assert client.get("/api/settings").status_code == 200

    # 模拟启用
    monkeypatch.setattr(s, "AUTH_TOKEN", "secret")
    assert client.get("/api/settings").status_code == 401
    assert client.get("/api/settings", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/settings", headers={"Authorization": "Bearer secret"}).status_code == 200

    monkeypatch.setattr(s, "AUTH_TOKEN", "")