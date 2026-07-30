"""应急指导 Agent：综合 MSDS first_aid_* 字段给出事故处置方案。

输入成分列表 + 事故类型（误服/皮肤接触/眼睛接触/吸入/泄漏），
输出立即行动 + 禁止事项 + 是否就医 + 急救电话。
"""
from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, Field

from services.qwen_client import call_qwen3, call_qwen_vl


# ---------- 输入/输出 schema ----------

class Hotline(BaseModel):
    name: str = Field("", description="热线名称")
    number: str = Field("", description="电话号码")


class EmergencyGuideOutput(BaseModel):
    immediate_actions: list[str] = Field(default_factory=list)
    do_not: list[str] = Field(default_factory=list)
    seek_medical_help: bool = Field(False)
    hotlines: list[Hotline] = Field(default_factory=list)


# ---------- Agent ----------

# 默认急救热线（中国地区）
_DEFAULT_HOTLINES = [
    {"name": "急救", "number": "120"},
    {"name": "全国中毒咨询热线", "number": "010-83132345"},
]


class EmergencyGuideAgent:
    """应急指导 Agent：误服/误触/泄漏处置 + 急救电话。"""

    # 高危事故类型/成分 → 必须就医
    _HIGH_RISK_TYPES = {"误服", "吸入"}
    _HIGH_RISK_HAZARDS = {"高", "极高"}

    def __init__(
        self,
        qwen_caller: Callable[..., Awaitable[str]] = call_qwen3,
        qwen_vl_caller: Callable[..., Awaitable[str]] = call_qwen_vl,
        retriever: Optional[Any] = None,
    ) -> None:
        self.qwen_caller = qwen_caller
        self.qwen_vl_caller = qwen_vl_caller
        self.retriever = retriever

    async def run(
        self,
        ingredients: list[dict],
        emergency_type: str,
        **kwargs: Any,
    ) -> dict:
        """给出事故应急处置方案。

        Args:
            ingredients: 成分列表，每项含 name、msds。
            emergency_type: 事故类型，"误服"/"皮肤接触"/"眼睛接触"/"吸入"/"泄漏"。

        Returns:
            dict 形式的 EmergencyGuideOutput。
        """
        prompt = self._build_prompt(ingredients, emergency_type)
        raw_text = await self.qwen_caller(prompt)
        parsed = self._parse_json(raw_text)

        actions = parsed.get("immediate_actions", []) if isinstance(parsed, dict) else []
        do_not = parsed.get("do_not", []) if isinstance(parsed, dict) else []
        seek_help = parsed.get("seek_medical_help", False) if isinstance(parsed, dict) else False
        hotlines_in = parsed.get("hotlines", []) if isinstance(parsed, dict) else []

        if not isinstance(actions, list):
            actions = [str(actions)]
        if not isinstance(do_not, list):
            do_not = [str(do_not)]
        if not isinstance(hotlines_in, list):
            hotlines_in = []

        # 兜底：根据 MSDS hazard_level / 事故类型判断是否必须就医
        if not seek_help:
            seek_help = self._must_seek_medical(ingredients, emergency_type)

        # hotlines 默认含 120 + 全国中毒咨询热线；若模型返回也合并去重
        hotlines = self._merge_hotlines(hotlines_in)

        out = EmergencyGuideOutput(
            immediate_actions=[str(a) for a in actions if a],
            do_not=[str(d) for d in do_not if d],
            seek_medical_help=bool(seek_help),
            hotlines=hotlines,
        )
        return out.model_dump()

    def _must_seek_medical(self, ingredients: list[dict], emergency_type: str) -> bool:
        """兜底判断是否必须就医：高危事故类型 / MSDS hazard_level=高或极高 → True。"""
        if emergency_type in self._HIGH_RISK_TYPES:
            return True
        for item in ingredients:
            msds = item.get("msds") or {}
            if msds.get("hazard_level") in self._HIGH_RISK_HAZARDS:
                return True
        return False

    def _merge_hotlines(self, model_hotlines: list[Any]) -> list[Hotline]:
        """合并默认热线与模型返回的，按 number 去重保序。"""
        seen_numbers = set()
        result: list[Hotline] = []
        # 先放默认
        for h in _DEFAULT_HOTLINES:
            num = str(h["number"])
            if num not in seen_numbers:
                seen_numbers.add(num)
                result.append(Hotline(name=h["name"], number=num))
        # 再合并模型返回的
        for h in model_hotlines:
            if isinstance(h, dict):
                name = str(h.get("name", ""))
                number = str(h.get("number", ""))
            else:
                continue
            if not number or number in seen_numbers:
                continue
            seen_numbers.add(number)
            result.append(Hotline(name=name, number=number))
        return result

    def _build_prompt(self, ingredients: list[dict], emergency_type: str) -> str:
        """构造 Qwen3 提示词。"""
        # 只保留 name + first_aid_* 字段，避免上下文过长
        ctx_ingredients = []
        for item in ingredients:
            msds = item.get("msds") or {}
            ctx_ingredients.append({
                "name": item.get("name", ""),
                "hazard_level": msds.get("hazard_level", ""),
                "first_aid_ingestion": msds.get("first_aid_ingestion", ""),
                "first_aid_skin": msds.get("first_aid_skin", ""),
                "first_aid_eye": msds.get("first_aid_eye", ""),
                "first_aid_inhalation": msds.get("first_aid_inhalation", ""),
            })
        ingredients_json = json.dumps(ctx_ingredients, ensure_ascii=False, indent=2)
        return (
            "你是化学品事故应急处置专家。基于成分 MSDS 数据给出处置方案，返回 JSON。\n\n"
            f"成分列表与 MSDS 摘要：\n{ingredients_json}\n\n"
            f"事故类型：{emergency_type}\n\n"
            "请返回如下 JSON：\n"
            "```json\n"
            "{\n"
            "  \"immediate_actions\": [\"立即行动1\", \"立即行动2\"],\n"
            "  \"do_not\": [\"禁止事项1\", \"禁止事项2\"],\n"
            "  \"seek_medical_help\": true 或 false,\n"
            "  \"hotlines\": [\n"
            "    {\"name\": \"急救\", \"number\": \"120\"},\n"
            "    {\"name\": \"全国中毒咨询热线\", \"number\": \"010-83132345\"}\n"
            "  ]\n"
            "}\n"
            "```\n\n"
            "处置原则：\n"
            "- immediate_actions 综合 MSDS 的 first_aid_ingestion/skin/eye/inhalation 字段（根据事故类型选最相关字段）+ 模型补充\n"
            "- 事故类型对照：误服→first_aid_ingestion；皮肤接触→first_aid_skin；眼睛接触→first_aid_eye；吸入→first_aid_inhalation；泄漏→综合判断\n"
            "- do_not 列出明确禁止的动作（如强酸/强碱误服勿催吐；切勿直接中和等）\n"
            "- 高危场景（误服强酸强碱、吸入剧毒气体、MSDS hazard_level=高）seek_medical_help=true 并强调立即就医\n"
            "- hotlines 默认包含 120 急救 + 010-83132345 全国中毒咨询热线，模型可补充其他专科热线\n"
            "- 仅返回 JSON，使用 ```json 代码块包裹\n"
        )

    @staticmethod
    def _parse_json(text: str) -> dict:
        """稳健解析模型返回的 JSON。"""
        if not text:
            return {}
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {"raw_text": text}
