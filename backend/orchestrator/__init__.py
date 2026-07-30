"""Agent 编排层：串联 6 个 Agent 完成家庭化学品安全评测全流程。

编排器（Orchestrator）负责：
- 根据输入模式（拍照 / 语音 / 应急）选择评测链路
- 串联识别 → 成分解析 → 风险评测 → 家庭画像 → 场景建议 / 应急指导
- 对可并行的步骤用 asyncio.gather 优化耗时
- 单个 Agent 失败时降级返回部分结果，不让整体崩溃
"""
from .orchestrator import Orchestrator

__all__ = ["Orchestrator"]
