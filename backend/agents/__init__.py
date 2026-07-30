"""6 Agent 核心模块：家庭化学品安全评测的专职 Agent 集合。

每个 Agent 职责单一、可独立调用，由编排层（Task 4）串联。
统一接口风格：
    __init__(self, qwen_caller=call_qwen3, qwen_vl_caller=call_qwen_vl, retriever=None)
    async def run(self, **kwargs) -> dict
"""
from .recognizer import RecognizerAgent
from .ingredient_parser import IngredientParserAgent
from .risk_evaluator import RiskEvaluatorAgent
from .family_profiler import FamilyProfilerAgent
from .scenario_advisor import ScenarioAdvisorAgent
from .emergency_guide import EmergencyGuideAgent

__all__ = [
    "RecognizerAgent",
    "IngredientParserAgent",
    "RiskEvaluatorAgent",
    "FamilyProfilerAgent",
    "ScenarioAdvisorAgent",
    "EmergencyGuideAgent",
]
