# 安居智评 Agent —— 多阶段构建 Dockerfile
# Stage 1: 构建前端静态资源（React + Vite）
# Stage 2: 运行时镜像（FastAPI + 前端静态 + 知识库）

# ----------------------------------------------------------------------
# Stage 1: frontend-build
# ----------------------------------------------------------------------
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

# 先复制依赖清单，利用 Docker 层缓存
COPY frontend/package.json frontend/package-lock.json ./

# 安装依赖（npm ci 严格按 lockfile 安装，速度更快且可重现）
RUN npm ci

# 复制前端源码并构建产物到 dist/
COPY frontend/ ./
RUN npm run build

# ----------------------------------------------------------------------
# Stage 2: runtime
# ----------------------------------------------------------------------
FROM python:3.10-slim AS runtime

# 设置时区与编码（PDF 中文字体兜底、日志时间用）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8

WORKDIR /app

# 安装系统依赖：
#   - fonts-wqy-zenhei：PDF 中文字体兜底（routes_report._CJK_FONT_CANDIDATES 已包含该路径）
#   - curl：health check 探测用（可选）
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-wqy-zenhei curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖清单并安装，利用层缓存
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 复制后端代码 + 知识库
COPY backend/ /app/backend/
COPY knowledge_base/ /app/knowledge_base/

# 复制前端 build 产物到 /app/static（与 backend/main.py 中 _STATIC_DIR 路径对应）
COPY --from=frontend-build /app/frontend/dist /app/static

# 运行时目录（uploads / storage/reports 由 config.py 启动时自动创建，这里显式声明便于挂卷）
RUN mkdir -p /app/backend/uploads /app/backend/storage/reports

# 暴露端口：
#   - 魔搭创空间强制 7860（ms_deploy.json 中 port 字段必须为 7860）
#   - 其他平台（Zeabur/Railway/Render）可通过 PORT 环境变量覆盖
# config.py 默认 PORT=8000，魔搭创空间部署时 ms_deploy.json 的环境变量会设 PORT=7860
EXPOSE 7860

# 工作目录切到 backend/，使 main.py 中的相对路径（uploads/、storage/reports/）落到正确位置
WORKDIR /app/backend

# 健康检查（Cloud Run / Zeabur / Railway / Render 都支持；魔搭创空间不强制但兼容）
# 端口跟随 PORT 环境变量；默认 8000，魔搭部署时 PORT=7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT:-8000}/health || exit 1

# 启动命令：uvicorn 监听 0.0.0.0:${PORT}
# 不在 CMD 里写死端口，而是让 config.py 从 PORT 环境变量读取（main.py __main__ 分支已支持）
# uvicorn 显式 --port 优先级最高，避免 pydantic-settings 读取失败时端口兜底
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
