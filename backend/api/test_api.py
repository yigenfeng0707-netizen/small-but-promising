"""Task 6 API 路由测试。

用 fastapi.testclient.TestClient + mock Orchestrator.evaluate，验证：
    - POST /api/evaluate（语音模式）
    - POST /api/evaluate/upload（multipart 假图片）
    - POST /api/voice
    - POST /api/batch-evaluate（2 个 item）
    - GET  /api/report/{request_id}（先 POST 再查）
    - GET  /api/report/{request_id}/pdf 返回 application/pdf
    - 错误：POST /api/evaluate 不传 image_url 与 voice_text 应 400
    - DELETE /api/report/{request_id} 删除报告

不调真实百炼 API：用 unittest.mock.AsyncMock 替换 Orchestrator.evaluate。

运行方式：
    cd backend
    python -m pytest api/test_api.py -v
"""
from __future__ import annotations

import copy
import io
import os
import sys
import uuid
from unittest.mock import AsyncMock, patch

# 把 backend 目录加入 sys.path，便于 from main import app
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


# ----------------------------------------------------------------------
# Mock 评测结果（结构与 orchestrator.evaluate 返回一致）
# ----------------------------------------------------------------------
_MOCK_RESULT_TEMPLATE = {
    "mode": "voice",
    "recognition": {
        "chemical_name": "洁厕灵",
        "brand": "威猛先生",
        "category": "清洁剂",
        "ingredients_text": "盐酸、表面活性剂",
        "raw_ocr": "盐酸、表面活性剂",
    },
    "ingredients": {
        "ingredients": [
            {"name": "盐酸", "msds": {"hazard_level": "高"}, "matched": True},
        ],
        "unmatched_ingredients": [],
    },
    "risk": {
        "overall_level": "高",
        "scores": {
            "toxicity": 85,
            "flammability": 10,
            "corrosivity": 90,
            "allergy": 60,
            "environment": 70,
        },
        "key_risks": ["强腐蚀性", "儿童误服风险高"],
        "interactions": ["盐酸与次氯酸钠混合产生剧毒氯气"],
    },
    "family_adjustment": {
        "adjusted_level": "极高",
        "adjustment_reasons": ["含 5 岁儿童，上调为极高"],
        "specific_warnings": ["远离儿童存放"],
    },
    "scenario_advice": {
        "storage": ["密封避光", "远离儿童"],
        "protection": ["戴橡胶手套", "通风"],
        "green_alternatives": [
            {"original": "盐酸", "alternatives": ["柠檬酸+小苏打", "白醋+食盐"],
             "reason": "低毒环保"}
        ],
    },
    "emergency_guide": {
        "immediate_actions": ["勿催吐", "饮牛奶", "就医"],
        "do_not": ["禁止催吐"],
        "seek_medical_help": True,
        "hotlines": [{"name": "急救", "number": "120"}],
    },
    "summary": "该洁厕灵含盐酸，综合风险极高，注意远离儿童，误服勿催吐并立即就医。",
    "errors": [],
    "partial": False,
}


def _make_mock_result(mode: str = "voice") -> dict:
    """生成一份独立的 mock 结果（新 request_id），避免批量场景覆盖。"""
    result = copy.deepcopy(_MOCK_RESULT_TEMPLATE)
    result["request_id"] = uuid.uuid4().hex
    result["mode"] = mode
    return result


@pytest.fixture()
def client_with_mock():
    """返回 (client, mock_orchestrator)。

    patch api.routes_evaluate.get_orchestrator，使其返回一个 evaluate 为
    AsyncMock 的对象。每次调用 evaluate 返回一份新的 mock 结果。
    """
    mock_orch = type("MockOrch", (), {})()
    # 默认按 voice 模式返回；上传测试会改写 side_effect
    async def _side_effect(*args, **kwargs):
        mode = "image" if kwargs.get("image_url") else "voice"
        return _make_mock_result(mode=mode)
    mock_orch.evaluate = AsyncMock(side_effect=_side_effect)

    # 清掉 lru_cache，确保 patch 生效
    import api.routes_evaluate as routes_eval
    routes_eval.get_orchestrator.cache_clear()

    with patch.object(routes_eval, "get_orchestrator", return_value=mock_orch):
        from main import app
        client = TestClient(app)
        yield client, mock_orch

    routes_eval.get_orchestrator.cache_clear()


# ----------------------------------------------------------------------
# 测试用例
# ----------------------------------------------------------------------
def test_evaluate_voice_mode(client_with_mock):
    """POST /api/evaluate 语音模式：返回完整结果，mode=voice。"""
    client, mock_orch = client_with_mock
    r = client.post("/api/evaluate", json={"voice_text": "84消毒液和洁厕灵能混用吗"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "voice"
    assert body["recognition"]["chemical_name"] == "洁厕灵"
    assert body["risk"]["overall_level"] == "高"
    assert "request_id" in body
    # evaluate 被调用一次，且 voice_text 透传
    mock_orch.evaluate.assert_awaited_once()
    call_kwargs = mock_orch.evaluate.await_args.kwargs
    assert call_kwargs.get("voice_text") == "84消毒液和洁厕灵能混用吗"


def test_evaluate_missing_inputs_returns_400(client_with_mock):
    """POST /api/evaluate 不传 image_url 与 voice_text 应 400。"""
    client, _ = client_with_mock
    r = client.post("/api/evaluate", json={})
    assert r.status_code == 400
    assert "至少" in r.json()["detail"]


def test_evaluate_upload(client_with_mock):
    """POST /api/evaluate/upload：multipart 假图片 → 评测。

    验证：返回 200；evaluate 以 image_url 被调用；image_url 含 /uploads/。
    """
    client, mock_orch = client_with_mock
    # 构造假 JPEG 字节流（不真实解码，路由只读字节存盘）
    fake_bytes = b"\xff\xd8\xff\xe0" + b"fake-jpeg-content" * 100
    files = {"file": ("test.jpg", io.BytesIO(fake_bytes), "image/jpeg")}
    r = client.post("/api/evaluate/upload", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "image"
    call_kwargs = mock_orch.evaluate.await_args.kwargs
    image_url = call_kwargs.get("image_url")
    assert image_url and "/uploads/" in image_url
    # 文件确实落盘
    filename = image_url.rsplit("/", 1)[-1]
    assert os.path.isfile(os.path.join(_BACKEND_DIR, "uploads", filename))


def test_voice_endpoint(client_with_mock):
    """POST /api/voice：等价评测的语音分支，语义明确。"""
    client, mock_orch = client_with_mock
    r = client.post("/api/voice", json={"voice_text": "孩子误喝了洁厕灵",
                                        "emergency_type": "误服"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "voice"
    call_kwargs = mock_orch.evaluate.await_args.kwargs
    assert call_kwargs.get("voice_text") == "孩子误喝了洁厕灵"
    assert call_kwargs.get("emergency_type") == "误服"


def test_batch_evaluate(client_with_mock):
    """POST /api/batch-evaluate：2 个 item 并发，返回 total/success/failed。"""
    client, mock_orch = client_with_mock
    payload = {
        "items": [
            {"voice_text": "84消毒液能和洁厕灵混用吗"},
            {"voice_text": "杀虫剂对孕妇有影响吗"},
        ]
    }
    r = client.post("/api/batch-evaluate", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    assert body["success"] == 2
    assert body["failed"] == 0
    assert len(body["results"]) == 2
    # evaluate 被调用 2 次
    assert mock_orch.evaluate.await_count == 2


def test_report_get_after_evaluate(client_with_mock):
    """POST /api/evaluate 后 GET /api/report/{request_id} 返回同一份报告。"""
    client, _ = client_with_mock
    r = client.post("/api/evaluate", json={"voice_text": "测试报告落盘"})
    assert r.status_code == 200
    request_id = r.json()["request_id"]

    r2 = client.get(f"/api/report/{request_id}")
    assert r2.status_code == 200, r2.text
    report = r2.json()
    assert report["request_id"] == request_id
    assert report["recognition"]["chemical_name"] == "洁厕灵"


def test_report_get_not_found(client_with_mock):
    """GET 不存在的 request_id 应 404。"""
    client, _ = client_with_mock
    r = client.get("/api/report/nonexistent-id-12345")
    assert r.status_code == 404


def test_report_pdf(client_with_mock):
    """POST 评测 → GET /api/report/{request_id}/pdf 返回 application/pdf。"""
    client, _ = client_with_mock
    r = client.post("/api/evaluate", json={"voice_text": "测试 PDF"})
    request_id = r.json()["request_id"]

    r2 = client.get(f"/api/report/{request_id}/pdf")
    assert r2.status_code == 200, r2.text
    assert r2.headers["content-type"].startswith("application/pdf")
    # PDF 魔数：%PDF-
    assert r2.content[:4] == b"%PDF"


def test_report_delete(client_with_mock):
    """DELETE /api/report/{request_id} 后再 GET 应 404。"""
    client, _ = client_with_mock
    r = client.post("/api/evaluate", json={"voice_text": "测试删除"})
    request_id = r.json()["request_id"]

    r2 = client.delete(f"/api/report/{request_id}")
    assert r2.status_code == 200, r2.text
    assert r2.json()["deleted"] is True

    r3 = client.get(f"/api/report/{request_id}")
    assert r3.status_code == 404


def test_evaluate_upload_too_large(client_with_mock):
    """POST /api/evaluate/upload 超过 10MB 应 413。"""
    client, _ = client_with_mock
    # 11MB 假数据
    big = b"\x00" * (11 * 1024 * 1024)
    files = {"file": ("big.jpg", io.BytesIO(big), "image/jpeg")}
    r = client.post("/api/evaluate/upload", files=files)
    assert r.status_code == 413
