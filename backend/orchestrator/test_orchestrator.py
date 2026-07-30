"""Agent 编排层测试。

不调真实百炼 API，用 unittest.mock.AsyncMock mock 6 个 Agent 的 run 方法 +
summary_caller，验证：
1. 三种输入模式（拍照 / 语音 / 应急）都跑通
2. 单个 Agent 抛异常时降级返回 partial=true，其他步骤正常
3. 可并行的步骤（场景建议 & 应急指导）实际并行，总耗时 < 串行

运行方式：
    cd backend
    python -m pytest orchestrator/test_orchestrator.py        # 推荐
    python -m pytest orchestrator/test_orchestrator.py -v     # 详细
    python orchestrator/test_orchestrator.py                  # 直接运行（不依赖 pytest）
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import unittest
from unittest.mock import AsyncMock

# 把 backend 目录加入 sys.path，便于直接 python orchestrator/test_orchestrator.py 运行
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# 尝试导入 pytest + pytest.mark.asyncio；未安装则降级为 unittest 风格
try:
    import pytest  # noqa: F401
    _HAS_PYTEST = True
except ImportError:
    _HAS_PYTEST = False

# pytest-asyncio 装饰器；未装时退化为 no-op
try:
    pytest_mark_asyncio = pytest.mark.asyncio
except Exception:  # pragma: no cover
    def pytest_mark_asyncio(func):
        return func


# ---------- 测试用 mock 数据 ----------

# 识别 Agent 返回（洁厕灵）
_MOCK_RECOGNITION = {
    "chemical_name": "洁厕灵",
    "brand": "威猛先生",
    "category": "清洁剂",
    "ingredients_text": "盐酸、表面活性剂、缓蚀剂",
    "raw_ocr": "威猛先生洁厕灵 净含量500ml 主要成分：盐酸、表面活性剂",
}

# 成分解析 Agent 返回
_MOCK_INGREDIENTS = {
    "ingredients": [
        {
            "name": "盐酸",
            "msds": {
                "id": "msds_001",
                "name": "盐酸",
                "hazard_level": "高",
                "storage": "密封避光储存，远离儿童、金属和碱类",
                "green_alternatives": ["柠檬酸+小苏打", "白醋+食盐"],
                "first_aid_ingestion": "勿催吐，立即饮牛奶或蛋清保护胃黏膜，迅速就医",
                "first_aid_skin": "立即用大量清水冲洗 15 分钟以上",
            },
            "matched": True,
        },
        {
            "name": "表面活性剂",
            "msds": None,
            "matched": False,
        },
    ],
    "unmatched_ingredients": ["表面活性剂"],
}

# 风险评测 Agent 返回
_MOCK_RISK = {
    "overall_level": "高",
    "scores": {
        "toxicity": 85,
        "flammability": 10,
        "corrosivity": 90,
        "allergy": 60,
        "environment": 70,
    },
    "key_risks": ["强腐蚀性，可致皮肤灼伤", "儿童误服风险高"],
    "interactions": ["盐酸与次氯酸钠混合会产生剧毒氯气"],
}

# 家庭画像 Agent 返回
_MOCK_FAMILY = {
    "adjusted_level": "极高",
    "adjustment_reasons": ["家庭含 5 岁儿童，原风险等级为高，上调为极高"],
    "specific_warnings": ["儿童误服风险：建议放置于儿童无法触及处"],
}

# 场景建议 Agent 返回
_MOCK_SCENARIO = {
    "storage": ["密封避光储存", "远离儿童和金属存放", "与氨水、漂白剂隔离"],
    "protection": ["使用时戴橡胶手套", "保持通风", "避免接触皮肤和眼睛"],
    "green_alternatives": [
        {
            "original": "盐酸",
            "alternatives": ["柠檬酸+小苏打", "白醋+食盐"],
            "reason": "低毒可生物降解，对环境友好",
        }
    ],
}

# 应急指导 Agent 返回
_MOCK_EMERGENCY = {
    "immediate_actions": ["勿催吐", "立即饮牛奶或蛋清保护胃黏膜", "迅速就医"],
    "do_not": ["禁止催吐", "禁止直接中和"],
    "seek_medical_help": True,
    "hotlines": [
        {"name": "急救", "number": "120"},
        {"name": "全国中毒咨询热线", "number": "010-83132345"},
    ],
}

_MOCK_SUMMARY = "该洁厕灵含盐酸，综合风险极高，注意远离儿童，误服勿催吐并立即就医。"


# ---------- Mock 装配工厂 ----------

def _wire_all_agents(o, summary: str = _MOCK_SUMMARY) -> None:
    """把编排器内 6 个 Agent 的 run 方法全部替换为返回预设 dict 的 AsyncMock。

    同时把 summary_caller 替换为 AsyncMock，避免触发真实百炼 API。
    """
    o.recognizer.run = AsyncMock(return_value=_MOCK_RECOGNITION)
    o.parser.run = AsyncMock(return_value=_MOCK_INGREDIENTS)
    o.risk_evaluator.run = AsyncMock(return_value=_MOCK_RISK)
    o.family_profiler.run = AsyncMock(return_value=_MOCK_FAMILY)
    o.scenario_advisor.run = AsyncMock(return_value=_MOCK_SCENARIO)
    o.emergency_guide.run = AsyncMock(return_value=_MOCK_EMERGENCY)
    o.summary_caller = AsyncMock(return_value=summary)


# ---------- 测试用例 ----------

class TestOrchestratorImport(unittest.TestCase):
    """验证编排器可正常导入与实例化（不依赖真实 API Key）。"""

    def test_import_and_instantiate(self) -> None:
        from orchestrator import Orchestrator
        o = Orchestrator()
        # 6 个 Agent 实例就位
        self.assertIsNotNone(o.recognizer)
        self.assertIsNotNone(o.parser)
        self.assertIsNotNone(o.risk_evaluator)
        self.assertIsNotNone(o.family_profiler)
        self.assertIsNotNone(o.scenario_advisor)
        self.assertIsNotNone(o.emergency_guide)
        # summary_caller 默认指向 call_qwen3
        self.assertTrue(callable(o.summary_caller))


class TestOrchestratorImageMode(unittest.IsolatedAsyncioTestCase):
    """a) 拍照模式：image_url + family_profile。"""

    async def test_image_mode_full_flow(self) -> None:
        from orchestrator import Orchestrator
        o = Orchestrator()
        _wire_all_agents(o)

        result = await o.evaluate(
            image_url="https://example.com/toilet_cleaner.jpg",
            family_profile={"children": 1, "elderly": 0, "pregnant": False,
                            "pets": False, "chronic_disease": []},
        )

        # 基本字段
        self.assertIn("request_id", result)
        self.assertEqual(len(result["request_id"]), 32)  # uuid4().hex
        self.assertEqual(result["mode"], "image")
        self.assertFalse(result["partial"])
        self.assertEqual(result["errors"], [])

        # 各步骤结果正确传递
        self.assertEqual(result["recognition"]["chemical_name"], "洁厕灵")
        self.assertEqual(result["ingredients"]["ingredients"][0]["name"], "盐酸")
        self.assertEqual(result["risk"]["overall_level"], "高")
        self.assertEqual(result["family_adjustment"]["adjusted_level"], "极高")
        self.assertGreater(len(result["scenario_advice"]["storage"]), 0)
        self.assertTrue(result["emergency_guide"]["seek_medical_help"])

        # 识别 Agent 应以 image_url 被调用一次
        # _step_recognize 内部以关键字 run(image_url=...) 调用
        o.recognizer.run.assert_awaited_once()
        call_args = o.recognizer.run.await_args
        self.assertEqual(call_args.kwargs.get("image_url"),
                         "https://example.com/toilet_cleaner.jpg")

        # summary 生成被调用
        o.summary_caller.assert_awaited_once()
        self.assertTrue(result["summary"])


class TestOrchestratorVoiceMode(unittest.IsolatedAsyncioTestCase):
    """b) 语音/文本模式：voice_text + family_profile（无 image_url）。"""

    async def test_voice_mode_pseudo_recognition(self) -> None:
        from orchestrator import Orchestrator
        o = Orchestrator()
        _wire_all_agents(o)

        result = await o.evaluate(
            voice_text="84消毒液和洁厕灵能混用吗",
            family_profile={"children": 0, "elderly": 0, "pregnant": False,
                            "pets": False, "chronic_disease": []},
        )

        self.assertEqual(result["mode"], "voice")
        self.assertFalse(result["partial"])

        # 语音模式下不应调用 Qwen-VL 识别 Agent，而是构造伪识别结果
        o.recognizer.run.assert_not_awaited()
        # 伪识别结果：chemical_name 取自 voice_text，ingredients_text = voice_text
        self.assertEqual(result["recognition"]["ingredients_text"], "84消毒液和洁厕灵能混用吗")
        self.assertEqual(result["recognition"]["category"], "其他")

        # 风险评测应以 scenario=voice_text 调用
        risk_call = o.risk_evaluator.run.await_args
        self.assertEqual(risk_call.kwargs.get("scenario"), "84消毒液和洁厕灵能混用吗")

        # 成分解析的输入应是 voice_text（伪识别 ingredients_text）
        parser_call = o.parser.run.await_args
        self.assertEqual(parser_call.kwargs.get("ingredients_text"),
                         "84消毒液和洁厕灵能混用吗")

        # 应急指导默认事故类型为"正常使用"（未传 emergency_type）
        em_call = o.emergency_guide.run.await_args
        self.assertEqual(em_call.kwargs.get("emergency_type"), "正常使用")


class TestOrchestratorEmergencyMode(unittest.IsolatedAsyncioTestCase):
    """c) 应急模式：voice_text 描述场景 + emergency_type 指定类型。"""

    async def test_emergency_mode_passes_emergency_type(self) -> None:
        from orchestrator import Orchestrator
        o = Orchestrator()
        _wire_all_agents(o)

        result = await o.evaluate(
            voice_text="孩子误喝了洁厕灵",
            emergency_type="误服",
        )

        self.assertEqual(result["mode"], "emergency")
        self.assertFalse(result["partial"])

        # 应急指导应以 emergency_type="误服" 调用
        em_call = o.emergency_guide.run.await_args
        self.assertEqual(em_call.kwargs.get("emergency_type"), "误服")

        # 伪识别结果基于 voice_text
        self.assertEqual(result["recognition"]["ingredients_text"], "孩子误喝了洁厕灵")

        # 仍跑完整 6 步流程（不因应急模式跳过其他 Agent）
        self.assertEqual(result["risk"]["overall_level"], "高")
        self.assertEqual(result["family_adjustment"]["adjusted_level"], "极高")
        self.assertGreater(len(result["scenario_advice"]["storage"]), 0)


class TestOrchestratorDegradation(unittest.IsolatedAsyncioTestCase):
    """单个 Agent 抛异常时降级：partial=true，其他步骤正常。"""

    async def test_risk_evaluator_failure_degrades_gracefully(self) -> None:
        from orchestrator import Orchestrator
        o = Orchestrator()
        _wire_all_agents(o)
        # 让风险评测 Agent 抛异常
        o.risk_evaluator.run = AsyncMock(side_effect=RuntimeError("百炼服务不可用"))

        result = await o.evaluate(
            image_url="https://example.com/x.jpg",
            family_profile={"children": 1},
        )

        # 整体标记 partial，errors 非空
        self.assertTrue(result["partial"])
        self.assertGreater(len(result["errors"]), 0)
        self.assertTrue(any("风险评测" in e for e in result["errors"]))

        # 风险评测结果降级为 {"error":..., "partial":True}
        self.assertEqual(result["risk"].get("partial"), True)
        self.assertIn("error", result["risk"])

        # 其他步骤仍正常执行（未被拖垮）
        self.assertEqual(result["recognition"]["chemical_name"], "洁厕灵")
        self.assertEqual(result["ingredients"]["ingredients"][0]["name"], "盐酸")
        # 家庭画像仍跑（拿到的是降级 risk dict，但 Agent 本身未抛错）
        self.assertEqual(result["family_adjustment"]["adjusted_level"], "极高")
        # 场景建议、应急指导仍跑
        self.assertGreater(len(result["scenario_advice"]["storage"]), 0)
        self.assertTrue(result["emergency_guide"]["seek_medical_help"])

    async def test_summary_failure_falls_back_to_rules(self) -> None:
        """summary 生成失败时应降级为规则拼接，且整体 partial=true。"""
        from orchestrator import Orchestrator
        o = Orchestrator()
        _wire_all_agents(o)
        # summary_caller 抛异常 → 触发规则兜底
        o.summary_caller = AsyncMock(side_effect=RuntimeError("summary 模型超时"))

        result = await o.evaluate(
            image_url="https://example.com/x.jpg",
            family_profile={"children": 1},
        )

        self.assertTrue(result["partial"])
        # summary 不为空（规则兜底）
        self.assertTrue(result["summary"])
        self.assertIn("洁厕灵", result["summary"])
        self.assertIn("高", result["summary"])


class TestOrchestratorParallelism(unittest.IsolatedAsyncioTestCase):
    """验证可并行的步骤（场景建议 & 应急指导）实际并行执行。

    依编排设计：Step 5（ScenarioAdvisor）与 Step 6（EmergencyGuide）无依赖关系，
    通过 asyncio.gather 并行。二者各 sleep 0.3s 时，并行总耗时应明显小于串行 0.6s。
    """

    async def test_scenario_and_emergency_run_in_parallel(self) -> None:
        from orchestrator import Orchestrator
        o = Orchestrator()
        _wire_all_agents(o)

        delay = 0.3

        async def _slow_scenario(*args, **kwargs):
            await asyncio.sleep(delay)
            return _MOCK_SCENARIO

        async def _slow_emergency(*args, **kwargs):
            await asyncio.sleep(delay)
            return _MOCK_EMERGENCY

        o.scenario_advisor.run = AsyncMock(side_effect=_slow_scenario)
        o.emergency_guide.run = AsyncMock(side_effect=_slow_emergency)

        start = time.perf_counter()
        result = await o.evaluate(
            image_url="https://example.com/x.jpg",
            family_profile={"children": 1},
        )
        elapsed = time.perf_counter() - start

        # 并行：总耗时应接近 delay（0.3s），远小于串行 2*delay（0.6s）
        # 留足余量，断言 < 2*delay - 0.15
        self.assertLess(elapsed, 2 * delay - 0.15,
                        f"并行步骤总耗时 {elapsed:.3f}s 未明显小于串行 {2 * delay}s")
        # 结果仍正确
        self.assertFalse(result["partial"])
        self.assertEqual(result["scenario_advice"]["storage"][0], "密封避光储存")
        self.assertTrue(result["emergency_guide"]["seek_medical_help"])

    async def test_serial_steps_not_parallel(self) -> None:
        """对照：Step 3（风险评测）与 Step 4（家庭画像）串行，总耗时 ≈ 2*delay。"""
        from orchestrator import Orchestrator
        o = Orchestrator()
        _wire_all_agents(o)

        delay = 0.2

        async def _slow_risk(*args, **kwargs):
            await asyncio.sleep(delay)
            return _MOCK_RISK

        async def _slow_family(*args, **kwargs):
            await asyncio.sleep(delay)
            return _MOCK_FAMILY

        o.risk_evaluator.run = AsyncMock(side_effect=_slow_risk)
        o.family_profiler.run = AsyncMock(side_effect=_slow_family)

        start = time.perf_counter()
        await o.evaluate(
            image_url="https://example.com/x.jpg",
            family_profile={"children": 1},
        )
        elapsed = time.perf_counter() - start

        # 串行：总耗时应 ≥ 2*delay（减去调度抖动）
        self.assertGreaterEqual(elapsed, 2 * delay - 0.05,
                                f"串行步骤总耗时 {elapsed:.3f}s 未达到 2*delay {2*delay}s")


# ---------- 直接 python 执行入口 ----------

def _run_all() -> int:
    """python orchestrator/test_orchestrator.py 直接运行入口。"""
    print("=" * 60)
    print("Task 4 测试：Agent 编排层")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    import inspect
    test_classes = [
        obj for _, obj in inspect.getmembers(sys.modules[__name__], inspect.isclass)
        if issubclass(obj, unittest.TestCase) and obj is not unittest.TestCase
    ]
    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(_run_all())
