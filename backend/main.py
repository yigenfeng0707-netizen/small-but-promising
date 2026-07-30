"""FastAPI 应用入口。

Task 1：健康检查 + CORS。
Task 6：把业务路由按职责拆到 backend/api/ 下用 APIRouter 组织，并挂载
        /uploads 静态文件服务（供 /api/evaluate/upload 的图片被 Qwen-VL 拉取）。
        启动时自动创建 uploads/ 与 storage/reports/ 目录。
Task 8：挂载前端 build 产物（../static 目录）到根路径 /，
        并对所有未匹配 API/upload 的路由返回 index.html（SPA 兜底），
        让 FastAPI 单服务即可同时提供 API + 前端，便于容器化部署。
"""
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings, UPLOAD_DIR as _UPLOAD_DIR, REPORT_DIR as _REPORT_DIR

app = FastAPI(
    title="安居智评 Agent",
    description="家庭化学品安全智能评测后端",
    version="0.1.0",
)


def _cors_origins() -> list[str]:
    return [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 上传/报告目录由 config.py 集中解析（魔搭创空间自动走 /mnt/workspace 持久化）
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# 前端 build 产物目录：
#   - 本地开发：通常不存在，跳过挂载
#   - Docker 部署：Dockerfile 把 frontend/dist 复制到 /app/static，
#     而本文件位于 /app/backend/main.py，所以相对路径是 ../static
_STATIC_DIR = os.path.abspath(os.path.join(_BACKEND_DIR, "..", "static"))
_STATIC_INDEX = os.path.join(_STATIC_DIR, "index.html")


# ----------------------------------------------------------------------
# 挂载业务路由（Task 6 拆分到 api/ 包）
# ----------------------------------------------------------------------
from api import evaluate_router, report_router  # noqa: E402

app.include_router(evaluate_router)
app.include_router(report_router)


# ----------------------------------------------------------------------
# 静态文件服务：/uploads → backend/uploads/
# 供 /api/evaluate/upload 保存的图片被 Qwen-VL 通过 HTTP 拉取
# ----------------------------------------------------------------------
app.mount("/uploads", StaticFiles(directory=_UPLOAD_DIR), name="uploads")


@app.get("/health")
def health() -> dict[str, str]:
    """健康检查接口（容器/云平台 health check 用）。"""
    return {"status": "ok"}


# ----------------------------------------------------------------------
# Task 8：前端静态资源服务 + SPA 兜底
# ----------------------------------------------------------------------
# 1. 前端 build 产物（vite build）默认带 assets/ 子目录与 hash 文件名，
#    用 StaticFiles 挂载到根 / 后，/assets/xxx.js、/favicon.svg 等能直接命中。
# 2. React Router 使用 History 模式时，刷新 /result/xxx 等子路径需要服务端
#    兜底返回 index.html；这里用 catch-all 路由实现 SPA 兜底。
# 3. 必须放在所有 API 路由（/api/*）和 /uploads、/health 之后，避免吞掉这些路径。
# 4. 仅当 static 目录存在时挂载（本地开发无 build 产物则不挂载，由 vite dev server 接管前端）。
if os.path.isdir(_STATIC_DIR):
    # 挂载 /assets 等静态资源到根（html=False 表示这些路径不会被视为页面入口）
    app.mount("/assets", StaticFiles(directory=os.path.join(_STATIC_DIR, "assets")), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str, request: Request):
        """SPA 兜底：未匹配 API/uploads/health 的所有路径返回 index.html 或静态文件。

        - 命中 static 目录下真实文件（如 favicon.svg、icons.svg）→ 直接返回
        - 否则返回 index.html，交给 React Router 在前端处理路由
        """
        # 安全：禁止路径穿越
        candidate = os.path.normpath(os.path.join(_STATIC_DIR, full_path))
        if not candidate.startswith(_STATIC_DIR):
            raise HTTPException(status_code=404, detail="Not Found")

        # 命中真实文件 → 直接返回（favicon.svg / icons.svg / robots.txt 等）
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)

        # 其余一律返回 index.html（React Router 接管 / /result / /batch 等）
        if os.path.isfile(_STATIC_INDEX):
            return FileResponse(_STATIC_INDEX)
        raise HTTPException(status_code=404, detail="Static index not found")


if __name__ == "__main__":
    import uvicorn

    # 端口由 PORT 环境变量控制（魔搭创空间要求 7860，本地默认 8000）
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
