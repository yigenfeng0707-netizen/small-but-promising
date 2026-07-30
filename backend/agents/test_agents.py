"""6 Agent 核心模块测试。

不调真实百炼 API，全部用 unittest.mock.AsyncMock 模拟 call_qwen3 / call_qwen_vl，
验证：
1. 每个 Agent 可正常 __init__（不依赖真实 API Key）
2. 每个 Agent 的 run() 流程能跑通并返回结构化 dict

运行方式：
    cd backend
    python -m pytest agents/test_agents.py        # 推荐
    python -m pytest agents/test_agents.py -v      # 详细
    python agents/test_agents.py                   # 直接运行（不依赖 pytest）

pytest-asyncio 配置：每个 async 测试用 @pytest.mark.asyncio 装饰。
"""
from __future__ import annotations

import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock

# 把 backend 目录加入 sys.path，便于直接 python agents/test_agents.py 运行
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

# 模拟 Qwen-VL 识别洁厕灵包装的返回
_MOCK_RECOGNIZER_REPLY = """```json
{
  "chemical_name": "洁厕灵",
  "brand": "威猛先生",
  "category": "清洁剂",
  "ingredients_text": "盐酸、表面活性剂、缓蚀剂",
  "raw_ocr": "威猛先生洁厕灵 净含量500ml 主要成分：盐酸、表面活性剂"
}
```"""

# 模拟 Qwen3 解析成分表返回
_MOCK_PARSER_REPLY = """```json
{
  "ingredients": ["盐酸", "表面活性剂"]
}
```"""

# 模拟 Qwen3 风险评测返回
_MOCK_RISK_REPLY = """```json
{
  "overall_level": "高",
  "scores": {
    "toxicity": 85,
    "flammability": 10,
    "corrosivity": 90,
    "allergy": 60,
    "environment": 70
  },
  "key_risks": ["强腐蚀性，可致皮肤灼伤", "儿童误服风险高"],
  "interactions": ["盐酸与次氯酸钠混合会产生剧毒氯气"]
}
```"""

# 模拟 Qwen3 家庭画像调整返回
_MOCK_FAMILY_REPLY = """```json
{
  "adjusted_level": "极高",
  "adjustment_reasons": ["家庭含 5 岁儿童，原风险等级为高，上调为极高"],
  "specific_warnings": ["儿童误服风险：建议放置于儿童无法触及处", "建议在使用时确保儿童远离"]
}
```"""

# 模拟 Qwen3 场景建议返回
_MOCK_SCENARIO_REPLY = """```json
{
  "storage": ["密封避光储存", "远离儿童和金属存放", "与氨水、漂白剂隔离"],
  "protection": ["使用时戴橡胶手套", "保持通风", "避免接触皮肤和眼睛"],
  "green_alternatives": [
    {"original": "盐酸", "alternatives": ["柠檬酸+小苏打", "白醋+食盐"], "reason": "低毒可生物降解，对环境友好"}
  ]
}
```"""

# 模拟 Qwen3 应急指导返回
_MOCK_EMERGENCY_REPLY = """```json
{
  "immediate_actions": ["勿催吐", "立即饮牛奶或蛋清保护胃黏膜", "迅速就医"],
  "do_not": ["禁止催吐", "禁止直接中和"],
  "seek_medical_help": true,
  "hotlines": [
    {"name": "急救", "number": "120"},
    {"name": "全国中毒咨询热线", "number": "010-83132345"}
  ]
}
```"""


# ---------- Mock 工厂 ----------

def _make_mock_qwen3(reply: str) -> AsyncMock:
    """构造 mock call_qwen3，固定返回 reply。"""
    m = AsyncMock()
    m.return_value = reply
    return m


def _make_mock_qwen_vl(reply: str) -> AsyncMock:
    """构造 mock call_qwen_vl，固定返回 reply。"""
    m = AsyncMock()
    m.return_value = reply
    return m


class _FakeRetriever:
    """内存版 MSDSRetriever 替身，按预置字典返回。"""

    def __init__(self, table: dict[str, dict]) -> None:
        self._table = table

    def retrieve(self, name: str, top_k: int = 3) -> list[dict]:
        # 精确匹配 + 子串匹配，简化版
        hits: list[dict] = []
        for key, msds in self._table.items():
            if name == key or name in key:
                hits.append(msds)
        return hits[:top_k]

    def get_by_id(self, id: str) -> dict:
        for msds in self._table.values():
            if msds.get("id") == id:
                return msds
        return None

    def list_all(self) -> list[dict]:
        return list(self._table.values())


def _build_fake_retriever() -> _FakeRetriever:
    """构造一个含盐酸 MSDS 的 fake retriever。"""
    return _FakeRetriever({
        "盐酸": {
            "id": "msds_001",
            "name": "盐酸",
            "aliases": ["氢氯酸", "盐镪水"],
            "category": "清洁剂",
            "common_products": ["洁厕灵", "威猛先生洁厕剂"],
            "hazard_level": "高",
            "toxicity": "强腐蚀性",
            "flammability": "不燃",
            "corrosivity": "强腐蚀",
            "allergy": "可致化学灼伤",
            "environment": "对水生生物有毒",
            "first_aid_ingestion": "勿催吐，立即饮牛奶或蛋清保护胃黏膜，迅速就医",
            "first_aid_skin": "立即用大量清水冲洗 15 分钟以上",
            "first_aid_eye": "立即用清水冲洗 15 分钟并就医",
            "first_aid_inhalation": "迅速移至空气新鲜处",
            "storage": "密封避光储存，远离儿童、金属和碱类",
            "green_alternatives": ["柠檬酸+小苏打", "白醋+食盐"],
        },
    })


# ---------- 测试用例 ----------

class TestAgentImport(unittest.TestCase):
    """验证所有 Agent 可正常导入与实例化（不依赖真实 API Key）。"""

    def test_import_all_agents(self) -> None:
        from agents import (
            RecognizerAgent,
            IngredientParserAgent,
            RiskEvaluatorAgent,
            FamilyProfilerAgent,
            ScenarioAdvisorAgent,
            EmergencyGuideAgent,
        )
        # 全部为类
        for cls in (
            RecognizerAgent,
            IngredientParserAgent,
            RiskEvaluatorAgent,
            FamilyProfilerAgent,
            ScenarioAdvisorAgent,
            EmergencyGuideAgent,
        ):
            self.assertTrue(callable(cls))

    def test_instantiate_all_agents(self) -> None:
        from agents import (
            RecognizerAgent,
            IngredientParserAgent,
            RiskEvaluatorAgent,
            FamilyProfilerAgent,
            ScenarioAdvisorAgent,
            EmergencyGuideAgent,
        )
        # 用 mock 作为 qwen_caller / qwen_vl_caller，避免触发真实 dashscope 导入副作用
        mock3 = _make_mock_qwen3("ok")
        mockvl = _make_mock_qwen_vl("ok")
        for cls in (
            RecognizerAgent,
            IngredientParserAgent,
            RiskEvaluatorAgent,
            FamilyProfilerAgent,
            ScenarioAdvisorAgent,
            EmergencyGuideAgent,
        ):
            agent = cls(qwen_caller=mock3, qwen_vl_caller=mockvl, retriever=None)
            self.assertIsNotNone(agent)


class TestRecognizerAgent(unittest.IsolatedAsyncioTestCase):
    """识别 Agent 测试。"""

    async def test_run_returns_expected_fields(self) -> None:
        from agents import RecognizerAgent
        agent = RecognizerAgent(
            qwen_caller=_make_mock_qwen3("ok"),
            qwen_vl_caller=_make_mock_qwen_vl(_MOCK_RECOGNIZER_REPLY),
            retriever=None,
        )
        result = await agent.run(image_url="https://example.com/test.jpg")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["chemical_name"], "洁厕灵")
        self.assertEqual(result["brand"], "威猛先生")
        self.assertEqual(result["category"], "清洁剂")
        self.assertIn("盐酸", result["ingredients_text"])
        self.assertTrue(result["raw_ocr"])

    async def test_run_handles_non_json_gracefully(self) -> None:
        """模型返回纯文本时应降级为 raw_text 包在 dict 里，不抛错。"""
        from agents import RecognizerAgent
        agent = RecognizerAgent(
            qwen_caller=_make_mock_qwen3("ok"),
            qwen_vl_caller=_make_mock_qwen_vl("这是纯文本，没有 JSON"),
            retriever=None,
        )
        result = await agent.run(image_url="https://example.com/test.jpg")
        self.assertIsInstance(result, dict)
        # 缺字段全部兜底为空串
        self.assertEqual(result["chemical_name"], "")
        # raw_ocr 至少保留了原文
        self.assertIn("纯文本", result["raw_ocr"])


class TestIngredientParserAgent(unittest.IsolatedAsyncioTestCase):
    """成分解析 Agent 测试。"""

    async def test_run_parses_ingredients_and_matches_msds(self) -> None:
        from agents import IngredientParserAgent
        retriever = _build_fake_retriever()
        agent = IngredientParserAgent(
            qwen_caller=_make_mock_qwen3(_MOCK_PARSER_REPLY),
            qwen_vl_caller=_make_mock_qwen_vl("ok"),
            retriever=retriever,
        )
        result = await agent.run(ingredients_text="盐酸、表面活性剂")
        self.assertIsInstance(result, dict)
        self.assertIn("ingredients", result)
        self.assertGreaterEqual(len(result["ingredients"]), 2)
        # 盐酸应命中 MSDS
        matched_hcl = [i for i in result["ingredients"] if i["name"] == "盐酸"]
        self.assertTrue(matched_hcl)
        self.assertTrue(matched_hcl[0]["matched"])
        self.assertIsNotNone(matched_hcl[0]["msds"])
        # 表面活性剂未命中 → 在 unmatched_ingredients 中
        self.assertIn("表面活性剂", result["unmatched_ingredients"])

    async def test_run_handles_array_response(self) -> None:
        """模型直接返回 JSON 数组也应能解析。"""
        from agents import IngredientParserAgent
        retriever = _build_fake_retriever()
        agent = IngredientParserAgent(
            qwen_caller=_make_mock_qwen3('```json\n["盐酸", "次氯酸钠"]\n```'),
            qwen_vl_caller=_make_mock_qwen_vl("ok"),
            retriever=retriever,
        )
        result = await agent.run(ingredients_text="盐酸、次氯酸钠")
        names = [i["name"] for i in result["ingredients"]]
        self.assertIn("盐酸", names)
        self.assertIn("次氯酸钠", names)


class TestRiskEvaluatorAgent(unittest.IsolatedAsyncioTestCase):
    """风险评测 Agent 测试。"""

    async def test_run_returns_five_dim_scores(self) -> None:
        from agents import RiskEvaluatorAgent
        agent = RiskEvaluatorAgent(
            qwen_caller=_make_mock_qwen3(_MOCK_RISK_REPLY),
            qwen_vl_caller=_make_mock_qwen_vl("ok"),
            retriever=None,
        )
        ingredients = [
            {"name": "盐酸", "msds": {"hazard_level": "高"}, "matched": True},
            {"name": "表面活性剂", "msds": None, "matched": False},
        ]
        result = await agent.run(ingredients=ingredients, scenario="混合使用")
        self.assertEqual(result["overall_level"], "高")
        scores = result["scores"]
        self.assertIn("toxicity", scores)
        self.assertIn("flammability", scores)
        self.assertIn("corrosivity", scores)
        self.assertIn("allergy", scores)
        self.assertIn("environment", scores)
        self.assertGreater(scores["corrosivity"], 0)
        self.assertIsInstance(result["key_risks"], list)
        self.assertIsInstance(result["interactions"], list)
        self.assertGreater(len(result["key_risks"]), 0)

    async def test_run_derives_level_when_invalid(self) -> None:
        """模型返回不合法 overall_level 时应基于 5 维分数兜底推导。"""
        from agents import RiskEvaluatorAgent
        bad_reply = """```json
{
  "overall_level": "无效值",
  "scores": {"toxicity": 90, "flammability": 10, "corrosivity": 95, "allergy": 50, "environment": 70},
  "key_risks": ["强腐蚀"],
  "interactions": []
}
```"""
        agent = RiskEvaluatorAgent(
            qwen_caller=_make_mock_qwen3(bad_reply),
            qwen_vl_caller=_make_mock_qwen_vl("ok"),
            retriever=None,
        )
        result = await agent.run(ingredients=[{"name": "盐酸", "msds": None, "matched": False}])
        # 任一分数≥80 → 极高
        self.assertEqual(result["overall_level"], "极高")


class TestFamilyProfilerAgent(unittest.IsolatedAsyncioTestCase):
    """家庭画像 Agent 测试。"""

    async def test_run_adjusts_level_for_children(self) -> None:
        from agents import FamilyProfilerAgent
        agent = FamilyProfilerAgent(
            qwen_caller=_make_mock_qwen3(_MOCK_FAMILY_REPLY),
            qwen_vl_caller=_make_mock_qwen_vl("ok"),
            retriever=None,
        )
        family_profile = {
            "children": 1,
            "elderly": 0,
            "pregnant": False,
            "pets": False,
            "chronic_disease": [],
        }
        risk_result = {
            "overall_level": "高",
            "scores": {"toxicity": 85, "flammability": 10, "corrosivity": 90, "allergy": 60, "environment": 70},
            "key_risks": ["强腐蚀"],
            "interactions": [],
        }
        result = await agent.run(family_profile=family_profile, risk_result=risk_result)
        self.assertEqual(result["adjusted_level"], "极高")
        self.assertIsInstance(result["adjustment_reasons"], list)
        self.assertGreater(len(result["adjustment_reasons"]), 0)
        self.assertGreater(len(result["specific_warnings"]), 0)

    async def test_run_falls_back_to_original_level(self) -> None:
        """模型返回不合法时兜底沿用原等级。"""
        from agents import FamilyProfilerAgent
        agent = FamilyProfilerAgent(
            qwen_caller=_make_mock_qwen3("纯文本无 JSON"),
            qwen_vl_caller=_make_mock_qwen_vl("ok"),
            retriever=None,
        )
        result = await agent.run(
            family_profile={"children": 0, "elderly": 0, "pregnant": False, "pets": False, "chronic_disease": []},
            risk_result={"overall_level": "中"},
        )
        self.assertEqual(result["adjusted_level"], "中")


class TestScenarioAdvisorAgent(unittest.IsolatedAsyncioTestCase):
    """场景建议 Agent 测试。"""

    async def test_run_returns_storage_protection_greens(self) -> None:
        from agents import ScenarioAdvisorAgent
        agent = ScenarioAdvisorAgent(
            qwen_caller=_make_mock_qwen3(_MOCK_SCENARIO_REPLY),
            qwen_vl_caller=_make_mock_qwen_vl("ok"),
            retriever=None,
        )
        risk_result = {
            "overall_level": "高",
            "scores": {"toxicity": 85, "flammability": 10, "corrosivity": 90, "allergy": 60, "environment": 70},
            "key_risks": ["强腐蚀"],
            "interactions": [],
        }
        family_adjustment = {
            "adjusted_level": "极高",
            "adjustment_reasons": ["含 5 岁儿童"],
            "specific_warnings": ["儿童误服风险"],
        }
        ingredients = [
            {
                "name": "盐酸",
                "msds": {
                    "hazard_level": "高",
                    "storage": "密封避光储存，远离儿童",
                    "green_alternatives": ["柠檬酸+小苏打", "白醋+食盐"],
                },
                "matched": True,
            },
        ]
        result = await agent.run(
            risk_result=risk_result,
            family_adjustment=family_adjustment,
            ingredients=ingredients,
        )
        self.assertIsInstance(result["storage"], list)
        self.assertGreater(len(result["storage"]), 0)
        self.assertIsInstance(result["protection"], list)
        self.assertGreater(len(result["protection"]), 0)
        # 绿色替代品必须包含从 MSDS 提取的
        greens = result["green_alternatives"]
        self.assertGreater(len(greens), 0)
        original_names = [g["original"] for g in greens]
        self.assertIn("盐酸", original_names)
        hcl_greens = [g for g in greens if g["original"] == "盐酸"][0]
        self.assertIn("柠檬酸+小苏打", hcl_greens["alternatives"])

    async def test_run_extracts_greens_even_if_model_empty(self) -> None:
        """即使模型返回空 green_alternatives，MSDS 提取的仍应保留。"""
        from agents import ScenarioAdvisorAgent
        empty_reply = """```json
{"storage": ["通风处存放"], "protection": ["戴手套"], "green_alternatives": []}
```"""
        agent = ScenarioAdvisorAgent(
            qwen_caller=_make_mock_qwen3(empty_reply),
            qwen_vl_caller=_make_mock_qwen_vl("ok"),
            retriever=None,
        )
        ingredients = [
            {
                "name": "盐酸",
                "msds": {
                    "hazard_level": "高",
                    "storage": "密封储存",
                    "green_alternatives": ["柠檬酸+小苏打"],
                },
                "matched": True,
            },
        ]
        result = await agent.run(
            risk_result={"overall_level": "高"},
            family_adjustment={"adjusted_level": "高"},
            ingredients=ingredients,
        )
        greens = result["green_alternatives"]
        self.assertGreater(len(greens), 0)
        self.assertEqual(greens[0]["original"], "盐酸")
        self.assertIn("柠檬酸+小苏打", greens[0]["alternatives"])


class TestEmergencyGuideAgent(unittest.IsolatedAsyncioTestCase):
    """应急指导 Agent 测试。"""

    async def test_run_returns_actions_and_default_hotlines(self) -> None:
        from agents import EmergencyGuideAgent
        agent = EmergencyGuideAgent(
            qwen_caller=_make_mock_qwen3(_MOCK_EMERGENCY_REPLY),
            qwen_vl_caller=_make_mock_qwen_vl("ok"),
            retriever=None,
        )
        ingredients = [
            {
                "name": "盐酸",
                "msds": {
                    "hazard_level": "高",
                    "first_aid_ingestion": "勿催吐，立即饮牛奶或蛋清保护胃黏膜，迅速就医",
                    "first_aid_skin": "立即用大量清水冲洗 15 分钟以上",
                    "first_aid_eye": "立即用清水冲洗 15 分钟并就医",
                    "first_aid_inhalation": "迅速移至空气新鲜处",
                },
                "matched": True,
            },
        ]
        result = await agent.run(ingredients=ingredients, emergency_type="误服")
        self.assertIsInstance(result["immediate_actions"], list)
        self.assertGreater(len(result["immediate_actions"]), 0)
        self.assertIsInstance(result["do_not"], list)
        self.assertTrue(result["seek_medical_help"])
        # hotlines 默认含 120 + 全国中毒咨询热线
        numbers = [h["number"] for h in result["hotlines"]]
        self.assertIn("120", numbers)
        self.assertIn("010-83132345", numbers)

    async def test_run_forces_medical_help_for_high_risk(self) -> None:
        """高危事故类型即使模型返回 false 也应兜底为 true。"""
        from agents import EmergencyGuideAgent
        low_risk_reply = """```json
{
  "immediate_actions": ["清水冲洗"],
  "do_not": [],
  "seek_medical_help": false,
  "hotlines": []
}
```"""
        agent = EmergencyGuideAgent(
            qwen_caller=_make_mock_qwen3(low_risk_reply),
            qwen_vl_caller=_make_mock_qwen_vl("ok"),
            retriever=None,
        )
        ingredients = [{"name": "盐酸", "msds": {"hazard_level": "高"}, "matched": True}]
        result = await agent.run(ingredients=ingredients, emergency_type="误服")
        # 误服 + hazard_level=高 → 必须就医
        self.assertTrue(result["seek_medical_help"])
        # 即使模型没返回 hotlines，默认的 120 + 中毒热线也应在
        numbers = [h["number"] for h in result["hotlines"]]
        self.assertIn("120", numbers)
        self.assertIn("010-83132345", numbers)


# ---------- pytest 风格入口（可选） ----------

if _HAS_PYTEST:

    @pytest_mark_asyncio
    async def test_recognizer_pytest_style():
        """pytest-asyncio 风格样例（验证 pytest 装饰器可用）。"""
        from agents import RecognizerAgent
        agent = RecognizerAgent(
            qwen_caller=_make_mock_qwen3("ok"),
            qwen_vl_caller=_make_mock_qwen_vl(_MOCK_RECOGNIZER_REPLY),
            retriever=None,
        )
        result = await agent.run(image_url="https://example.com/test.jpg")
        assert result["chemical_name"] == "洁厕灵"


# ---------- 直接 python 执行入口 ----------

def _run_all() -> int:
    """python agents/test_agents.py 直接运行入口。"""
    print("=" * 60)
    print("Task 3 测试：6 Agent 核心模块")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    # 加载所有 TestCase 子类
    import sys
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
