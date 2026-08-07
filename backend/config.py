"""应用配置：通过 pydantic-settings 从环境变量读取。"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DASHSCOPE_API_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    QWEN3_MODEL: str = "qwen-plus"
    QWEN_VL_MODEL: str = "qwen-vl-plus"
    EMBEDDING_MODEL: str = "text-embedding-v3"

    # CORS 允许的前端来源，逗号分隔
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 百炼业务空间专属网关（可选）。
    # 若使用业务空间 API Key，必须填此项指向业务空间的 dashscope 端点。
    # 普通账号 Key 留空即可（SDK 默认走 https://dashscope.aliyuncs.com）。
    # 示例：https://llm-uarugoa0rqgduef5.cn-beijing.maas.aliyuncs.com/api/v1
    DASHSCOPE_API_BASE: str = ""

    # 服务监听端口（魔搭创空间强制 7860，本地开发默认 8000）
    PORT: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


# ----------------------------------------------------------------------
# 路径配置：集中管理上传/报告存储目录，避免多处硬编码。
# 魔搭创空间持久化：/mnt/workspace 是创空间唯一持久化卷（重启不丢数据）。
# 检测到该目录存在时，把 uploads / storage/reports 重定向到其子目录，
# 避免评测图片和报告 JSON 在创空间重启后丢失。本地开发无此目录则走原逻辑。
# ----------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PERSIST_ROOT = "/mnt/workspace" if os.path.isdir("/mnt/workspace") else None

if _PERSIST_ROOT:
    # 魔搭创空间环境：使用持久化卷
    UPLOAD_DIR = os.path.join(_PERSIST_ROOT, "uploads")
    REPORT_DIR = os.path.join(_PERSIST_ROOT, "storage", "reports")
else:
    # 本地开发：使用 backend/ 下相对路径
    UPLOAD_DIR = os.path.join(_BACKEND_DIR, "uploads")
    REPORT_DIR = os.path.join(_BACKEND_DIR, "storage", "reports")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
