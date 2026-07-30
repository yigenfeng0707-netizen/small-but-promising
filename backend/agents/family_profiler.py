"""家庭画像 Agent：根据家庭成员画像调整风险等级与针对性建议。

输入家庭成员画像（儿童/老人/孕妇/宠物/慢性病）+ 风险评测结果，
输出调整后风险等级 + 调整理由 + 针对性警示。
"""
from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, Field

from services.qwen_client import call_qwen3, call_qwen_vl


# ---------- 输入/输出 schema ----------

class FamilyProfilerOutput(BaseModel):
    adjusted_level: str = Field("中", description="低|中|高|极高")
    adjustment_reasons: list[str] = Field(default_factory=list)
    specific_warnings: list[str] = Field(default_factory=list)


# ---------- Agent ----------

class FamilyProfilerAgent:
    """家庭画像 Agent：根据家庭成员调整风险等级。"""

    # 风险等级排序，用于判断"上调一档"
    _LEVEL_ORDER = ["低", "中", "高", "极高"]

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
        family_profile: dict,
        risk_result: dict,
        **kwargs: Any,
    ) -> dict:
        """根据家庭成员画像调整风险等级。

        Args:
            family_profile: 家庭画像，含 children/elderly/pregnant/pets/chronic_disease。
            risk_result: 风险评测 Agent 输出。

        Returns:
            dict 形式的 FamilyProfilerOutput。
        """
        prompt = self._build_prompt(family_profile, risk_result)
        raw_text = await self.qwen_caller(prompt)
        parsed = self._parse_json(raw_text)

        adjusted = str(parsed.get("adjusted_level", "")) if isinstance(parsed, dict) else ""
        if adjusted not in self._LEVEL_ORDER:
            # 兜底：沿用原等级
            adjusted = str(risk_result.get("overall_level", "中"))
            if adjusted not in self._LEVEL_ORDER:
                adjusted = "中"

        reasons = parsed.get("adjustment_reasons", []) if isinstance(parsed, dict) else []
        warnings = parsed.get("specific_warnings", []) if isinstance(parsed, dict) else []
        if not isinstance(reasons, list):
            reasons = [str(reasons)]
        if not isinstance(warnings, list):
            warnings = [str(warnings)]

        out = FamilyProfilerOutput(
            adjusted_level=adjusted,
            adjustment_reasons=[str(r) for r in reasons if r],
            specific_warnings=[str(w) for w in warnings if w],
        )
        return out.model_dump()

    def _build_prompt(self, family_profile: dict, risk_result: dict) -> str:
        """构造 Qwen3 提示词。"""
        family_json = json.dumps(family_profile, ensure_ascii=False, indent=2)
        risk_json = json.dumps(risk_result, ensure_ascii=False, indent=2)
        return (
            "你是家庭安全风险评估专家。请根据家庭成员画像调整风险等级并给出针对性警示，返回 JSON。\n\n"
            f"家庭成员画像：\n{family_json}\n\n"
            f"原风险评测结果：\n{risk_json}\n\n"
            "调整规则：\n"
            "- 含 0-6 岁儿童 + 风险等级为高或极高 → 调整为\"极高\" + 加\"儿童误服风险\"警示\n"
            "- 含孕妇 + 含挥发性/刺激性成分 → 加\"孕妇避免接触\"警示\n"
            "- 含慢性病（如哮喘/心脏病/肝病） + 含特定成分 → 加\"慢性病相互作用\"警示\n"
            "- 含宠物（猫/狗/鱼等） + 含菊酯/拟除虫菊酯/苯胺类成分 → 加\"对宠物剧毒\"警示\n"
            "- 含 65 岁以上老人 → 风险等级上调一档（低→中→高→极高）\n"
            "- 调整后的等级不能比原等级更低\n\n"
            "请返回如下 JSON：\n"
            "```json\n"
            "{\n"
            "  \"adjusted_level\": \"低|中|高|极高\",\n"
            "  \"adjustment_reasons\": [\"原因1\", \"原因2\"],\n"
            "  \"specific_warnings\": [\"针对性警示1\", \"警示2\"]\n"
            "}\n"
            "```\n\n"
            "要求：\n"
            "- adjusted_level 只能是\"低\"/\"中\"/\"高\"/\"极高\"之一\n"
            "- adjustment_reasons 解释为何调整（如未调整则填[\"维持原等级\"]）\n"
            "- specific_warnings 列出针对家庭成员的警示，无则返回空数组\n"
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
