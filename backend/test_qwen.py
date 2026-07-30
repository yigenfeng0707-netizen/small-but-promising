"""Task 2 验证脚本：验证 Qwen3 / Qwen-VL 调用封装是否正常工作。

运行方式：
    cd backend
    python test_qwen.py

行为：
- 若 DASHSCOPE_API_KEY 未配置：仅做模块导入校验 + call_qwen3 异常路径校验，
  不发起真实 API 调用（避免无谓消耗 Token）。
- 若 DASHSCOPE_API_KEY 已配置：额外发起一次文本推理（"你好"）和一次
  多模态识别（公开图片 URL）以验证真实链路。
"""
import asyncio
import os
import sys

from config import settings


def _has_real_api_key() -> bool:
    """判断是否配置了非空 DASHSCOPE_API_KEY。"""
    return bool(settings.DASHSCOPE_API_KEY) and not settings.DASHSCOPE_API_KEY.startswith("占位")


async def _test_import() -> None:
    """验证模块可正常导入且关键符号存在。"""
    print("[1/4] 模块导入测试 ...")
    try:
        from services.qwen_client import call_qwen3, call_qwen_vl  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        print(f"  ✗ 导入失败：{exc}")
        raise
    print("  ✓ services.qwen_client 导入成功，call_qwen3 / call_qwen_vl 可用")


async def _test_value_error_when_no_key() -> None:
    """API Key 未配置时 call_qwen3 应抛 ValueError。"""
    print("[2/4] 异常路径测试（API Key 未配置时抛 ValueError）...")
    if _has_real_api_key():
        print("  - 跳过：已配置真实 DASHSCOPE_API_KEY，无需测试无 Key 异常路径")
        return
    from services.qwen_client import call_qwen3

    try:
        await call_qwen3("你好")
    except ValueError as exc:
        print(f"  ✓ 按预期抛出 ValueError：{exc}")
        return
    raise AssertionError("未配置 API Key 时 call_qwen3 未抛 ValueError")


async def _test_qwen3_text() -> None:
    """若配置了真实 Key，调用 call_qwen3 问\"你好\"。"""
    print("[3/4] Qwen3 文本推理测试 ...")
    if not _has_real_api_key():
        print("  - 跳过：DASHSCOPE_API_KEY 未配置，无法发起真实调用")
        return
    from services.qwen_client import call_qwen3

    reply = await call_qwen3("你好", system="你是一个简洁的助手。")
    print(f"  ✓ Qwen3 回复：{reply[:200]}")


async def _test_qwen_vl() -> None:
    """若配置了真实 Key，调用 call_qwen_vl 识别公开图片。"""
    print("[4/4] Qwen-VL 多模态识别测试 ...")
    if not _has_real_api_key():
        print("  - 跳过：DASHSCOPE_API_KEY 未配置，无法发起真实调用")
        return
    from services.qwen_client import call_qwen_vl

    image_url = "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpg"
    reply = await call_qwen_vl(image_url, "请用一句话描述这张图片的内容。")
    print(f"  ✓ Qwen-VL 回复：{reply[:200]}")


async def main() -> int:
    print("=" * 60)
    print("Task 2 验证：百炼 Qwen3 + Qwen-VL 接入")
    print("=" * 60)
    print(f"当前模型配置：QWEN3_MODEL={settings.QWEN3_MODEL}, "
          f"QWEN_VL_MODEL={settings.QWEN_VL_MODEL}")
    key_state = "已配置（将发起真实 API 调用）" if _has_real_api_key() else "未配置（仅验证导入+异常路径）"
    print(f"DASHSCOPE_API_KEY：{key_state}")
    print("-" * 60)

    try:
        await _test_import()
        await _test_value_error_when_no_key()
        await _test_qwen3_text()
        await _test_qwen_vl()
    except Exception as exc:  # noqa: BLE001
        print(f"\n✗ 验证失败：{exc}")
        return 1

    print("-" * 60)
    print("✓ 全部测试项通过")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
