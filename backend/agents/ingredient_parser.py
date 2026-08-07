"""成分解析 Agent：从成分表文字提取成分名 + 调 MSDS 检索器匹配。

输入成分表文字，先让 Qwen3 解析出成分名列表，再对每个成分调 retriever.retrieve
匹配 MSDS 数据，输出含 msds 字段的成分列表。
"""
from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, Field

from services.qwen_client import call_qwen3, call_qwen_vl


# ---------- 输入/输出 schema ----------

class IngredientItem(BaseModel):
    name: str = Field(..., description="成分名")
    msds: Optional[dict] = Field(None, description="匹配到的 MSDS 记录，未匹配为 None")
    matched: bool = Field(False, description="是否匹配到 MSDS")


class IngredientParserOutput(BaseModel):
    ingredients: list[IngredientItem] = Field(default_factory=list)
    unmatched_ingredients: list[str] = Field(default_factory=list)


# ---------- Agent ----------

class IngredientParserAgent:
    """成分解析 Agent：解析成分 + 调 RAG 匹配 MSDS。"""

    def __init__(
        self,
        qwen_caller: Callable[..., Awaitable[str]] = call_qwen3,
        qwen_vl_caller: Callable[..., Awaitable[str]] = call_qwen_vl,
        retriever: Optional[Any] = None,
    ) -> None:
        self.qwen_caller = qwen_caller
        self.qwen_vl_caller = qwen_vl_caller
        self.retriever = retriever

    async def run(self, ingredients_text: str, **kwargs: Any) -> dict:
        """解析成分表文字 + 匹配 MSDS。

        Args:
            ingredients_text: 识别 Agent 输出的成分表文字。

        Returns:
            dict 形式的 IngredientParserOutput。
        """
        prompt = self._build_prompt(ingredients_text)
        raw_text = await self.qwen_caller(prompt)
        parsed = self._parse_json(raw_text)
        # 模型可能返回 {"ingredients": [...]} 或直接 [...]
        names: list[str] = []
        if isinstance(parsed, dict):
            raw_ingredients = parsed.get("ingredients", [])
        elif isinstance(parsed, list):
            raw_ingredients = parsed
        else:
            raw_ingredients = []
        for item in raw_ingredients:
            if isinstance(item, str):
                names.append(item.strip())
            elif isinstance(item, dict) and "name" in item:
                names.append(str(item["name"]).strip())

        # 去重保序
        seen = set()
        deduped_names: list[str] = []
        for n in names:
            if n and n not in seen:
                seen.add(n)
                deduped_names.append(n)

        # 对每个成分名调 retriever 匹配 MSDS
        ingredients: list[dict] = []
        unmatched: list[str] = []
        retriever = self._ensure_retriever()
        for name in deduped_names:
            msds: Optional[dict] = None
            if retriever is not None:
                hits = retriever.retrieve(name, top_k=1)
                if hits:
                    msds = hits[0] if isinstance(hits, list) else None
            if msds is not None:
                ingredients.append({"name": name, "msds": msds, "matched": True})
            else:
                ingredients.append({"name": name, "msds": None, "matched": False})
                unmatched.append(name)

        out = IngredientParserOutput(
            ingredients=[IngredientItem(**i) for i in ingredients],
            unmatched_ingredients=unmatched,
        )
        return out.model_dump()

    def _ensure_retriever(self) -> Any:
        """懒加载 Retriever：优先 EmbeddingRetriever，降级 MSDSRetriever。

        知识库加载失败时返回 None（不抛错，让流程继续，只是不匹配 MSDS）。
        """
        if self.retriever is not None:
            return self.retriever
        try:
            import os
            import sys
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            if root not in sys.path:
                sys.path.insert(0, root)
            # 优先使用 Embedding 检索器
            try:
                from knowledge_base import EmbeddingRetriever
                self.retriever = EmbeddingRetriever()
                return self.retriever
            except Exception:
                pass
            # 降级为精确+模糊匹配检索器
            from knowledge_base import MSDSRetriever
            self.retriever = MSDSRetriever()
            return self.retriever
        except Exception:
            return None

    def _build_prompt(self, ingredients_text: str) -> str:
        """构造 Qwen3 提示词。"""
        return (
            "你是化学成分解析专家。请从下面的成分表文字中提取所有化学成分名称，返回 JSON：\n"
            "{\"ingredients\": [\"成分名1\", \"成分名2\", ...]}\n\n"
            "要求：\n"
            "- 提取中文、英文或化学式形式的成分名（如\"盐酸\"、\"次氯酸钠\"、\"NaClO\"）\n"
            "- 去除浓度、百分比等数值修饰（如\"5% 盐酸\"只保留\"盐酸\"）\n"
            "- 不要遗漏任何成分\n"
            "- 仅返回 JSON，使用 ```json 代码块包裹\n\n"
            f"成分表文字：\n{ingredients_text}\n"
        )

    @staticmethod
    def _parse_json(text: str) -> Any:
        """稳健解析模型返回的 JSON（可能是对象或数组）。"""
        if not text:
            return {}
        text = text.strip()
        # 1. 直接 json.loads
        try:
            return json.loads(text)
        except Exception:
            pass
        # 2. 提取 ```json ... ``` 代码块（兼容对象/数组）
        m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        # 3. 提取首个 {...} 或 [...] 块
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        # 4. 失败兜底
        return {"raw_text": text}
