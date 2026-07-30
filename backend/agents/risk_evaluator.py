"""风险评测 Agent：综合 MSDS + 成分相互作用给出 5 维评分。

5 维：毒性 / 易燃性 / 腐蚀性 / 过敏性 / 环境性，每维 0-100 分。
综合给出 overall_level（低/中/高/极高）、key_risks、interactions。
"""
from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, Field

from services.qwen_client import call_qwen3, call_qwen_vl


# ---------- 输入/输出 schema ----------

class RiskScores(BaseModel):
    toxicity: int = Field(0, ge=0, le=100)
    flammability: int = Field(0, ge=0, le=100)
    corrosivity: int = Field(0, ge=0, le=100)
    allergy: int = Field(0, ge=0, le=100)
    environment: int = Field(0, ge=0, le=100)


class RiskEvaluatorOutput(BaseModel):
    overall_level: str = Field("中", description="低|中|高|极高")
    scores: RiskScores = Field(default_factory=RiskScores)
    key_risks: list[str] = Field(default_factory=list)
    interactions: list[str] = Field(default_factory=list)


# ---------- Agent ----------

class RiskEvaluatorAgent:
    """风险评测 Agent：5 维评分 + 综合等级。"""

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
        scenario: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """对成分列表进行 5 维风险评测。

        Args:
            ingredients: 成分列表，每项含 name、msds（可能为 None）、matched 字段。
            scenario: 可选使用场景，如"混合使用"、"误服"、"正常使用"。

        Returns:
            dict 形式的 RiskEvaluatorOutput。
        """
        # 构造喂给模型的成分上下文（只保留 name + msds，去掉无意义字段）
        context_ingredients = []
        for item in ingredients:
            ctx = {"name": item.get("name", "")}
            msds = item.get("msds")
            if msds:
                ctx["msds"] = msds
            else:
                ctx["msds"] = None
            context_ingredients.append(ctx)

        scenario_text = scenario or "正常使用"
        prompt = self._build_prompt(context_ingredients, scenario_text)
        raw_text = await self.qwen_caller(prompt)
        parsed = self._parse_json(raw_text)

        # 解析 5 维分数
        scores_in = parsed.get("scores", {}) if isinstance(parsed, dict) else {}
        scores = RiskScores(
            toxicity=int(scores_in.get("toxicity", 0) or 0),
            flammability=int(scores_in.get("flammability", 0) or 0),
            corrosivity=int(scores_in.get("corrosivity", 0) or 0),
            allergy=int(scores_in.get("allergy", 0) or 0),
            environment=int(scores_in.get("environment", 0) or 0),
        )

        overall = str(parsed.get("overall_level", "中")) if isinstance(parsed, dict) else "中"
        # 校验 overall 取值合法
        if overall not in ("低", "中", "高", "极高"):
            overall = self._derive_level(scores)

        key_risks = parsed.get("key_risks", []) if isinstance(parsed, dict) else []
        interactions = parsed.get("interactions", []) if isinstance(parsed, dict) else []
        if not isinstance(key_risks, list):
            key_risks = [str(key_risks)]
        if not isinstance(interactions, list):
            interactions = [str(interactions)]

        out = RiskEvaluatorOutput(
            overall_level=overall,
            scores=scores,
            key_risks=[str(k) for k in key_risks if k],
            interactions=[str(i) for i in interactions if i],
        )
        return out.model_dump()

    @staticmethod
    def _derive_level(scores: RiskScores) -> str:
        """根据 5 维分数兜底推导 overall_level。"""
        values = [
            scores.toxicity,
            scores.flammability,
            scores.corrosivity,
            scores.allergy,
            scores.environment,
        ]
        mx = max(values)
        if mx >= 80:
            return "极高"
        if mx >= 60:
            return "高"
        if mx >= 40:
            return "中"
        return "低"

    def _build_prompt(self, ingredients: list[dict], scenario: str) -> str:
        """构造 Qwen3 提示词。"""
        ingredients_json = json.dumps(ingredients, ensure_ascii=False, indent=2)
        return (
            "你是化学品安全风险评估专家。请基于以下成分及其 MSDS 数据，综合评估整体风险，返回 JSON。\n\n"
            f"成分列表与 MSDS：\n{ingredients_json}\n\n"
            f"使用场景：{scenario}\n\n"
            "请返回如下 JSON 结构：\n"
            "```json\n"
            "{\n"
            "  \"overall_level\": \"低|中|高|极高\",\n"
            "  \"scores\": {\n"
            "    \"toxicity\": 0-100,\n"
            "    \"flammability\": 0-100,\n"
            "    \"corrosivity\": 0-100,\n"
            "    \"allergy\": 0-100,\n"
            "    \"environment\": 0-100\n"
            "  },\n"
            "  \"key_risks\": [\"风险点1\", \"风险点2\"],\n"
            "  \"interactions\": [\"成分间相互作用1\", ...]\n"
            "}\n"
            "```\n\n"
            "评估原则：\n"
            "- 5 维评分：毒性 / 易燃性 / 腐蚀性 / 过敏性 / 环境性，0=无风险 100=极高风险\n"
            "- overall_level 综合考虑 5 维分数：任一≥80→极高；任一≥60→高；任一≥40→中；否则→低\n"
            "- 当 scenario=\"混合使用\" 时，重点检查成分间相互作用（如 84 消毒液 + 洁厕灵 → 剧毒氯气；含氯消毒剂 + 酸 → 氯气）\n"
            "- key_risks 列出 2-5 个关键风险点（中文描述）\n"
            "- interactions 列出成分间可能发生的危险化学反应（无相互作用返回空数组）\n"
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
