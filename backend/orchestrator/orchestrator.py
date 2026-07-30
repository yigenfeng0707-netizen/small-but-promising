"""Agent 编排层：串联 6 个 Agent 完成家庭化学品安全评测全流程。

编排顺序（依依赖关系）：
    Step 1 识别       —— 拍照走 Qwen-VL；语音/应急构造伪识别结果
    Step 2 成分解析   —— 依赖 Step 1 的 ingredients_text
    Step 3 风险评测   —— 依赖 Step 2 的 ingredients
    Step 4 家庭画像   —— 依赖 Step 3 的 risk_result
    Step 5 场景建议   —— 依赖 Step 3+4+2，与 Step 6 并行
    Step 6 应急指导   —— 依赖 Step 2 的 ingredients，与 Step 5 并行

简化序列：1 → 2 → 3 → 4 → [5, 6 并行]

错误降级：每个 Agent 调用都 try/except，失败时在对应结果里记
{"error": str(e), "partial": True}，不让单个 Agent 故障拖垮整条链路。

编排层不直接调 call_qwen3 / call_qwen_vl，全部通过 Agent 间接调用（便于测试）。
唯一例外：summary 总结生成可以直接调 call_qwen3，失败时降级用规则拼接。
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Awaitable, Callable, Optional

from agents import (
    EmergencyGuideAgent,
    FamilyProfilerAgent,
    IngredientParserAgent,
    RecognizerAgent,
    RiskEvaluatorAgent,
    ScenarioAdvisorAgent,
)
from services.qwen_client import call_qwen3

logger = logging.getLogger(__name__)


class Orchestrator:
    """家庭化学品安全评测编排器：串联 6 Agent，处理多模态输入与降级。"""

    def __init__(self) -> None:
        # 实例化 6 个 Agent，共享默认 caller（call_qwen3 / call_qwen_vl）
        # 不在此传入 retriever，让 IngredientParserAgent 内部按需懒加载 MSDSRetriever
        self.recognizer: RecognizerAgent = RecognizerAgent()
        self.parser: IngredientParserAgent = IngredientParserAgent()
        self.risk_evaluator: RiskEvaluatorAgent = RiskEvaluatorAgent()
        self.family_profiler: FamilyProfilerAgent = FamilyProfilerAgent()
        self.scenario_advisor: ScenarioAdvisorAgent = ScenarioAdvisorAgent()
        self.emergency_guide: EmergencyGuideAgent = EmergencyGuideAgent()
        # summary 生成是编排层唯一允许直接调 call_qwen3 的例外；
        # 暴露为实例属性便于测试注入 mock
        self.summary_caller: Callable[..., Awaitable[str]] = call_qwen3

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        image_url: Optional[str] = None,
        voice_text: Optional[str] = None,
        family_profile: Optional[dict] = None,
        emergency_type: Optional[str] = None,
    ) -> dict:
        """主流程编排：根据输入模式自动选择评测链路。

        输入模式：
            a) 拍照评测：image_url + family_profile（无 emergency_type）
            b) 语音/文本评测：voice_text + family_profile（无 image_url）
            c) 应急查询：voice_text 描述场景 + emergency_type 指定类型

        Returns:
            完整评测结果 dict，含 request_id / mode / 各 Agent 输出 /
            summary / errors / partial。
        """
        request_id = uuid.uuid4().hex
        errors: list[str] = []
        family_profile = family_profile or {}

        # 判定输入模式
        mode = self._detect_mode(image_url, voice_text, emergency_type)

        # ---------- Step 1: 识别 ----------
        recognition = await self._run_step(
            "识别", errors,
            self._step_recognize, image_url, voice_text,
        )
        # 从识别结果取出 ingredients_text 作为下一步输入
        ingredients_text = self._extract_ingredients_text(recognition, voice_text)

        # ---------- Step 2: 成分解析 ----------
        ingredients_result = await self._run_step(
            "成分解析", errors,
            self._step_parse_ingredients, ingredients_text,
        )
        ingredients = (
            ingredients_result.get("ingredients", [])
            if isinstance(ingredients_result, dict)
            else []
        )

        # ---------- Step 3: 风险评测 ----------
        risk_result = await self._run_step(
            "风险评测", errors,
            self._step_evaluate_risk, ingredients, voice_text,
        )

        # ---------- Step 4: 家庭画像 ----------
        family_adjustment = await self._run_step(
            "家庭画像", errors,
            self._step_family_profile, family_profile, risk_result,
        )

        # ---------- Step 5 & 6: 场景建议 与 应急指导 并行 ----------
        # ScenarioAdvisor 依赖 risk_result + family_adjustment + ingredients
        # EmergencyGuide 仅依赖 ingredients + emergency_type，二者无依赖关系，可并行
        etype = emergency_type or "正常使用"
        scenario_advice, emergency_guide = await asyncio.gather(
            self._run_step(
                "场景建议", errors,
                self._step_scenario_advice,
                risk_result, family_adjustment, ingredients,
            ),
            self._run_step(
                "应急指导", errors,
                self._step_emergency_guide, ingredients, etype,
            ),
        )

        # ---------- Summary ----------
        summary = await self._build_summary(
            recognition, ingredients_result, risk_result, family_adjustment,
            scenario_advice, emergency_guide, errors,
        )

        return {
            "request_id": request_id,
            "mode": mode,
            "recognition": recognition,
            "ingredients": ingredients_result,
            "risk": risk_result,
            "family_adjustment": family_adjustment,
            "scenario_advice": scenario_advice,
            "emergency_guide": emergency_guide,
            "summary": summary,
            "errors": errors,
            "partial": len(errors) > 0,
        }

    # ------------------------------------------------------------------
    # 模式判定
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_mode(
        image_url: Optional[str],
        voice_text: Optional[str],
        emergency_type: Optional[str],
    ) -> str:
        """根据入参判定输入模式：emergency > image > voice。"""
        if emergency_type:
            return "emergency"
        if image_url:
            return "image"
        return "voice"

    # ------------------------------------------------------------------
    # 各步骤包装（统一 try/except 降级）
    # ------------------------------------------------------------------

    async def _run_step(
        self,
        step_name: str,
        errors: list[str],
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """统一 try/except 包装：失败时记录错误并返回带 partial 标记的降级 dict。"""
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            msg = f"{step_name}步骤失败: {type(e).__name__}: {e}"
            logger.exception(msg)
            errors.append(msg)
            return {"error": str(e), "partial": True}

    async def _step_recognize(
        self, image_url: Optional[str], voice_text: Optional[str]
    ) -> dict:
        """Step 1: 识别。有图片走 Qwen-VL；只有语音则构造伪识别结果。"""
        if image_url:
            return await self.recognizer.run(image_url=image_url)
        # 语音/文本模式：从文本提取化学品名作为伪识别结果
        return self._pseudo_recognize(voice_text or "")

    @staticmethod
    def _pseudo_recognize(voice_text: str) -> dict:
        """语音/文本模式下构造伪识别结果。

        简单规则：取整段文本作为 chemical_name 与 ingredients_text，
        让后续成分解析 Agent 从中提取成分名。
        """
        text = (voice_text or "").strip()
        return {
            "chemical_name": text[:32] if text else "未知",
            "brand": "未知",
            "category": "其他",
            "ingredients_text": text,
            "raw_ocr": text,
        }

    @staticmethod
    def _extract_ingredients_text(
        recognition: Any, voice_text: Optional[str]
    ) -> str:
        """从识别结果取 ingredients_text，兜底用 voice_text。"""
        if isinstance(recognition, dict):
            text = recognition.get("ingredients_text") or ""
            if text:
                return text
        return voice_text or ""

    async def _step_parse_ingredients(self, ingredients_text: str) -> dict:
        """Step 2: 成分解析 + MSDS 匹配。"""
        return await self.parser.run(ingredients_text=ingredients_text)

    async def _step_evaluate_risk(
        self, ingredients: list[dict], scenario: Optional[str]
    ) -> dict:
        """Step 3: 5 维风险评测。"""
        return await self.risk_evaluator.run(
            ingredients=ingredients, scenario=scenario,
        )

    async def _step_family_profile(
        self, family_profile: dict, risk_result: dict
    ) -> dict:
        """Step 4: 家庭画像调整。"""
        return await self.family_profiler.run(
            family_profile=family_profile, risk_result=risk_result,
        )

    async def _step_scenario_advice(
        self,
        risk_result: dict,
        family_adjustment: dict,
        ingredients: list[dict],
    ) -> dict:
        """Step 5: 场景建议（存储 + 防护 + 绿色替代品）。"""
        return await self.scenario_advisor.run(
            risk_result=risk_result,
            family_adjustment=family_adjustment,
            ingredients=ingredients,
        )

    async def _step_emergency_guide(
        self, ingredients: list[dict], emergency_type: str
    ) -> dict:
        """Step 6: 应急指导。"""
        return await self.emergency_guide.run(
            ingredients=ingredients, emergency_type=emergency_type,
        )

    # ------------------------------------------------------------------
    # Summary 总结生成（唯一允许编排层直接调 call_qwen3 的例外）
    # ------------------------------------------------------------------

    async def _build_summary(
        self,
        recognition: Any,
        ingredients_result: Any,
        risk_result: Any,
        family_adjustment: Any,
        scenario_advice: Any,
        emergency_guide: Any,
        errors: list[str],
    ) -> str:
        """综合 6 个 Agent 结果生成一段用户可读的总结。

        优先调 summary_caller（默认 call_qwen3）生成自然语言总结；
        失败时降级用规则拼接。
        """
        # 收集各步骤要点（容忍部分失败，dict 缺字段时兜底）
        chemical_name = (
            recognition.get("chemical_name", "未知化学品")
            if isinstance(recognition, dict)
            else "未知化学品"
        )
        overall_level = (
            risk_result.get("overall_level", "未知")
            if isinstance(risk_result, dict)
            else "未知"
        )
        adjusted_level = (
            family_adjustment.get("adjusted_level", overall_level)
            if isinstance(family_adjustment, dict)
            else overall_level
        )
        key_risks = (
            risk_result.get("key_risks", [])
            if isinstance(risk_result, dict)
            else []
        )
        greens = (
            scenario_advice.get("green_alternatives", [])
            if isinstance(scenario_advice, dict)
            else []
        )
        actions = (
            emergency_guide.get("immediate_actions", [])
            if isinstance(emergency_guide, dict)
            else []
        )

        fallback = self._rule_based_summary(
            chemical_name, overall_level, adjusted_level,
            key_risks, greens, actions, errors,
        )

        # 调模型生成自然语言总结（失败降级）
        try:
            prompt = self._build_summary_prompt(
                chemical_name, overall_level, adjusted_level,
                key_risks, greens, actions, errors,
            )
            text = await self.summary_caller(prompt)
            if text and text.strip():
                return text.strip()
            return fallback
        except Exception as e:
            msg = f"总结生成失败，降级为规则拼接: {type(e).__name__}: {e}"
            logger.warning(msg)
            errors.append(msg)
            return fallback

    @staticmethod
    def _rule_based_summary(
        chemical_name: str,
        overall_level: str,
        adjusted_level: str,
        key_risks: list,
        greens: list,
        actions: list,
        errors: list[str],
    ) -> str:
        """规则拼接的兜底总结：从各 Agent 结果抽取要点组成一段中文。"""
        parts: list[str] = [f"评测对象：{chemical_name}。"]
        if adjusted_level and adjusted_level != overall_level:
            parts.append(
                f"综合风险等级：{adjusted_level}（原 {overall_level}，经家庭画像调整）。"
            )
        else:
            parts.append(f"综合风险等级：{overall_level}。")

        if key_risks:
            risks = "；".join(str(r) for r in key_risks[:5])
            parts.append(f"主要风险：{risks}。")

        if greens:
            green_strs: list[str] = []
            for g in greens[:3]:
                if not isinstance(g, dict):
                    continue
                alts = g.get("alternatives", []) or []
                if alts:
                    green_strs.append(
                        f"{g.get('original', '')}→{'/'.join(str(a) for a in alts)}"
                    )
            if green_strs:
                parts.append("绿色替代：" + "；".join(green_strs) + "。")

        if actions:
            acts = "；".join(str(a) for a in actions[:3])
            parts.append(f"应急行动：{acts}。")

        if errors:
            parts.append(f"注：本次评测有 {len(errors)} 个步骤降级。")

        return " ".join(parts)

    @staticmethod
    def _build_summary_prompt(
        chemical_name: str,
        overall_level: str,
        adjusted_level: str,
        key_risks: list,
        greens: list,
        actions: list,
        errors: list[str],
    ) -> str:
        """构造总结生成的 Qwen3 提示词。"""
        return (
            "你是家庭化学品安全评测助手。请根据以下评测结果，用通俗易懂的一段话"
            "（150 字以内）向普通用户总结：这是什么化学品、综合风险等级、主要风险、"
            "存储/防护要点、应急建议、绿色替代品。\n\n"
            f"化学品名称：{chemical_name}\n"
            f"原始风险等级：{overall_level}\n"
            f"家庭调整后等级：{adjusted_level}\n"
            f"主要风险点：{json.dumps(key_risks, ensure_ascii=False)}\n"
            f"绿色替代品：{json.dumps(greens, ensure_ascii=False)}\n"
            f"应急行动：{json.dumps(actions, ensure_ascii=False)}\n"
            f"降级步骤数：{len(errors)}\n\n"
            "要求：直接输出一段中文总结，不要 JSON、不要 Markdown 标题。"
        )
