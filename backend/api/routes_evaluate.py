"""评测相关路由：核心评测接口、文件上传、语音输入、批量评测。

对应 Task 6 子任务：
    - SubTask 6.1: POST /api/evaluate          拍照/语音/应急统一入口
    - SubTask 6.2: POST /api/voice             语音/文本语义入口（等价评测的语音分支）
    - SubTask 6.3: POST /api/batch-evaluate    公益机构批量评测（并发限制 5）
    - 上传：     POST /api/evaluate/upload     multipart 图片上传 → 评测

设计要点：
    - Orchestrator 实例用 lru_cache 单例，避免每请求重建 6 个 Agent
    - 评测完成后自动把结果落到 backend/storage/reports/{request_id}.json
      （由 routes_report.save_report 负责，便于后续 GET/DELETE）
    - 上传大小限制 10MB，超出 413
"""
from __future__ import annotations

import asyncio
import os
import uuid
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, Field

from orchestrator import Orchestrator
from config import UPLOAD_DIR
from .routes_report import save_report

router = APIRouter(prefix="/api", tags=["evaluate"])

# 上传文件大小上限：10MB
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# UPLOAD_DIR 由 config.py 集中解析（魔搭创空间自动走 /mnt/workspace 持久化）


# ----------------------------------------------------------------------
# Orchestrator 单例：lru_cache 保证全进程只建一次
# ----------------------------------------------------------------------
@lru_cache
def get_orchestrator() -> Orchestrator:
    """返回进程级单例 Orchestrator。

    用 lru_cache 而非模块级变量，便于测试时用 get_orchestrator.cache_clear()
    重置，也符合 FastAPI 依赖注入风格。
    """
    return Orchestrator()


# ----------------------------------------------------------------------
# 请求体模型
# ----------------------------------------------------------------------
class EvaluateRequest(BaseModel):
    """评测请求：image_url 与 voice_text 至少传一个。"""
    image_url: Optional[str] = Field(default=None, description="待识别图片的可访问 URL")
    voice_text: Optional[str] = Field(default=None, description="语音/文本输入内容")
    family_profile: Optional[dict] = Field(default=None, description="家庭成员画像")
    emergency_type: Optional[str] = Field(default=None, description="应急类型：误服/误触/泄漏等")


class VoiceRequest(BaseModel):
    """语音/文本评测请求：等价 /api/evaluate 的语音分支，语义更明确。"""
    voice_text: str = Field(..., description="语音转写或文本内容")
    family_profile: Optional[dict] = Field(default=None, description="家庭成员画像")
    emergency_type: Optional[str] = Field(default=None, description="应急类型")


class BatchItem(BaseModel):
    """批量评测中的单项。"""
    image_url: Optional[str] = None
    voice_text: Optional[str] = None
    family_profile: Optional[dict] = None


class BatchEvaluateRequest(BaseModel):
    """批量评测请求：用于公益机构上传多张/多条同时评测。"""
    items: list[BatchItem] = Field(..., description="评测项列表")


# ----------------------------------------------------------------------
# 路由
# ----------------------------------------------------------------------
@router.post("/evaluate")
async def evaluate(req: EvaluateRequest) -> dict:
    """统一评测入口：支持 image_url / voice_text / emergency_type 组合。

    校验：image_url 与 voice_text 至少传一个，否则 400。
    评测完成后自动保存报告到 storage/reports/{request_id}.json。
    """
    if not req.image_url and not req.voice_text:
        raise HTTPException(
            status_code=400,
            detail="image_url 和 voice_text 至少需要传一个",
        )

    orchestrator = get_orchestrator()
    result = await orchestrator.evaluate(
        image_url=req.image_url,
        voice_text=req.voice_text,
        family_profile=req.family_profile,
        emergency_type=req.emergency_type,
    )
    # 落地报告，便于后续 GET /api/report/{request_id}
    save_report(result)
    return result


@router.post("/evaluate/upload")
async def evaluate_upload(request: Request, file: UploadFile = File(...)) -> dict:
    """multipart/form-data 上传图片 → 评测。

    流程：
        1. 校验文件大小 ≤ 10MB
        2. 保存到 backend/uploads/{uuid}.{ext}
        3. 拼成可访问 URL（基于 request.base_url + /uploads/）
        4. 调 Orchestrator.evaluate(image_url=...)
    """
    # 读取并校验大小
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大：{len(data)} bytes，上限 {MAX_UPLOAD_BYTES} bytes",
        )
    await file.seek(0)

    # 确保目录存在（main.py 启动时也会创建，这里兜底）
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 生成唯一文件名，保留原扩展名
    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(data)

    # 拼可访问 URL：基于当前请求的 base_url + 静态挂载点
    image_url = f"{request.base_url}uploads/{filename}"

    orchestrator = get_orchestrator()
    result = await orchestrator.evaluate(image_url=image_url)
    save_report(result)
    return result


@router.post("/voice")
async def voice(req: VoiceRequest) -> dict:
    """语音/文本评测入口：等价 /api/evaluate 的语音分支，语义更明确。

    适合前端 Web Speech API 转写后直接调用。
    """
    orchestrator = get_orchestrator()
    result = await orchestrator.evaluate(
        voice_text=req.voice_text,
        family_profile=req.family_profile,
        emergency_type=req.emergency_type,
    )
    save_report(result)
    return result


@router.post("/batch-evaluate")
async def batch_evaluate(req: BatchEvaluateRequest) -> dict:
    """批量评测：用于公益机构批量上传评测。

    用 asyncio.gather 并发，Semaphore 限制并发数为 5（避免压垮百炼 API）。
    返回 {results, total, success, failed}。
    """
    if not req.items:
        raise HTTPException(status_code=400, detail="items 不能为空")

    orchestrator = get_orchestrator()
    sem = asyncio.Semaphore(5)

    async def _run_one(item: BatchItem) -> dict:
        """单条评测：信号量限流 + 单条失败不影响整批。"""
        async with sem:
            try:
                result = await orchestrator.evaluate(
                    image_url=item.image_url,
                    voice_text=item.voice_text,
                    family_profile=item.family_profile,
                )
                save_report(result)
                return result
            except Exception as e:
                # 单条失败不拖垮整批；返回错误项，failed 计数 +1
                return {
                    "request_id": uuid.uuid4().hex,
                    "error": f"{type(e).__name__}: {e}",
                    "partial": True,
                }

    results = await asyncio.gather(*[_run_one(it) for it in req.items])

    success = sum(1 for r in results if not r.get("partial"))
    failed = len(results) - success
    return {
        "results": results,
        "total": len(results),
        "success": success,
        "failed": failed,
    }
