"""场景建议 Agent：综合给存储 + 防护 + 绿色替代品建议。

重点：绿色替代品必须从 MSDS 的 green_alternatives 字段提取 + 模型补充，
呼应绿色发展主题。
"""
from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, Field

from services.qwen_client import call_qwen3, call_qwen_vl


# ---------- 输入/输出 schema ----------

class GreenAlternative(BaseModel):
    original: str = Field("", description="原成分名")
    alternatives: list[str] = Field(default_factory=list)
    reason: str = Field("", description="推荐理由")


class ScenarioAdvisorOutput(BaseModel):
    storage: list[str] = Field(default_factory=list)
    protection: list[str] = Field(default_factory=list)
    green_alternatives: list[GreenAlternative] = Field(default_factory=list)


# ---------- Agent ----------

class ScenarioAdvisorAgent:
    """场景建议 Agent：存储 + 防护 + 绿色替代品。"""

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
        risk_result: dict,
        family_adjustment: dict,
        ingredients: list[dict],
        **kwargs: Any,
    ) -> dict:
        """综合给出存储 + 防护 + 绿色替代品建议。

        Args:
            risk_result: 风险评测 Agent 输出。
            family_adjustment: 家庭画像 Agent 输出。
            ingredients: 成分列表，每项含 name、msds（可能为 None）。

        Returns:
            dict 形式的 ScenarioAdvisorOutput。
        """
        # 先从 MSDS 的 green_alternatives 字段直接提取（不依赖模型）
        msds_greens = self._extract_msds_greens(ingredients)

        prompt = self._build_prompt(risk_result, family_adjustment, ingredients, msds_greens)
        raw_text = await self.qwen_caller(prompt)
        parsed = self._parse_json(raw_text)

        storage = parsed.get("storage", []) if isinstance(parsed, dict) else []
        protection = parsed.get("protection", []) if isinstance(parsed, dict) else []
        greens_in = parsed.get("green_alternatives", []) if isinstance(parsed, dict) else []
        if not isinstance(storage, list):
            storage = [str(storage)]
        if not isinstance(protection, list):
            protection = [str(protection)]
        if not isinstance(greens_in, list):
            greens_in = [greens_in]

        # 合并 MSDS 直接提取的绿色替代品与模型补充的，去重保序
        merged_greens = self._merge_greens(msds_greens, greens_in)

        out = ScenarioAdvisorOutput(
            storage=[str(s) for s in storage if s],
            protection=[str(p) for p in protection if p],
            green_alternatives=merged_greens,
        )
        return out.model_dump()

    def _extract_msds_greens(self, ingredients: list[dict]) -> list[dict]:
        """直接从 MSDS 的 green_alternatives 字段提取绿色替代品。

        Returns:
            [{"original": 成分名, "alternatives": [...], "reason": "MSDS 推荐"}]
        """
        result: list[dict] = []
        for item in ingredients:
            msds = item.get("msds") or {}
            greens = msds.get("green_alternatives") or []
            if greens:
                result.append({
                    "original": str(item.get("name", "")),
                    "alternatives": [str(g) for g in greens if g],
                    "reason": "MSDS 知识库推荐",
                })
        return result

    def _merge_greens(
        self,
        msds_greens: list[dict],
        model_greens: list[Any],
    ) -> list[GreenAlternative]:
        """合并 MSDS 提取的与模型补充的绿色替代品。

        策略：以 original 为键合并，MSDS 提取的优先，模型补充的追加到 alternatives 末尾（去重）。
        """
        merged: dict[str, GreenAlternative] = {}
        # 先放 MSDS 提取的
        for g in msds_greens:
            key = g.get("original", "")
            if not key:
                continue
            alts = list(g.get("alternatives", []))
            merged[key] = GreenAlternative(
                original=key,
                alternatives=alts,
                reason=str(g.get("reason", "MSDS 知识库推荐")),
            )
        # 再合并模型补充的
        for g in model_greens:
            if isinstance(g, str):
                # 模型只给了字符串：跳过（无 original 关联）
                continue
            if not isinstance(g, dict):
                continue
            key = str(g.get("original", "")).strip()
            if not key:
                continue
            alts = [str(a) for a in (g.get("alternatives", []) or []) if a]
            reason = str(g.get("reason", "模型推荐") or "模型推荐")
            if key in merged:
                # 追加 alternatives（去重保序）
                existing = merged[key].alternatives
                for a in alts:
                    if a not in existing:
                        existing.append(a)
                # 如果原 reason 是默认的 MSDS 推荐，且模型给了更具体的，覆盖
                if merged[key].reason == "MSDS 知识库推荐" and reason != "模型推荐":
                    merged[key].reason = reason
            else:
                merged[key] = GreenAlternative(
                    original=key,
                    alternatives=alts,
                    reason=reason,
                )
        return list(merged.values())

    def _build_prompt(
        self,
        risk_result: dict,
        family_adjustment: dict,
        ingredients: list[dict],
        msds_greens: list[dict],
    ) -> str:
        """构造 Qwen3 提示词。"""
        risk_json = json.dumps(risk_result, ensure_ascii=False, indent=2)
        family_json = json.dumps(family_adjustment, ensure_ascii=False, indent=2)
        # 只保留 name + storage + hazard_level，避免上下文过长
        ctx_ingredients = []
        for item in ingredients:
            msds = item.get("msds") or {}
            ctx_ingredients.append({
                "name": item.get("name", ""),
                "hazard_level": msds.get("hazard_level", ""),
                "storage": msds.get("storage", ""),
                "green_alternatives": msds.get("green_alternatives", []),
            })
        ingredients_json = json.dumps(ctx_ingredients, ensure_ascii=False, indent=2)
        msds_greens_json = json.dumps(msds_greens, ensure_ascii=False, indent=2)
        return (
            "你是家庭化学品使用场景建议专家。基于风险评测和家庭调整结果，给出存储 + 防护 + 绿色替代品建议，返回 JSON。\n\n"
            f"风险评测：\n{risk_json}\n\n"
            f"家庭调整：\n{family_json}\n\n"
            f"成分列表与 MSDS 摘要：\n{ingredients_json}\n\n"
            f"已从 MSDS 提取的绿色替代品（必须包含在输出中，模型可补充更多）：\n{msds_greens_json}\n\n"
            "请返回如下 JSON：\n"
            "```json\n"
            "{\n"
            "  \"storage\": [\"存储建议1\", \"存储建议2\"],\n"
            "  \"protection\": [\"防护建议1\", \"防护建议2\"],\n"
            "  \"green_alternatives\": [\n"
            "    {\"original\": \"原成分名\", \"alternatives\": [\"绿色替代品1\", \"替代品2\"], \"reason\": \"推荐理由\"}\n"
            "  ]\n"
            "}\n"
            "```\n\n"
            "要求：\n"
            "- green_alternatives 必须优先包含上面已从 MSDS 提取的条目，模型可在此基础上补充更多替代品与理由\n"
            "- storage 综合各成分 MSDS 的 storage 字段 + 家庭画像（如含儿童应加\"远离儿童存放\"）\n"
            "- protection 根据风险等级给出防护建议（如戴手套/口罩/通风等）\n"
            "- 绿色替代品应优先推荐低毒、可生物降解的家用物品（如小苏打、白醋、柠檬酸、茶籽粉等），呼应绿色发展主题\n"
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
