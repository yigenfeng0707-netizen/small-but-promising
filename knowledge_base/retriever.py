"""MSDS 知识库检索器。

本模块实现 MSDSRetriever 类，用于从本地 msds_data.json 中按化学品名/别名/常见产品名
进行精确与模糊匹配。不依赖任何外部 embedding 服务，可独立运行。

匹配策略（优先级从高到低）：
1. 化学品名完全匹配
2. 别名完全匹配
3. 常见产品名完全匹配
4. 名称/别名/产品名包含查询串（子串匹配）
5. 上述均不命中时，使用 difflib.SequenceMatcher 对所有候选文本做相似度排序
"""

from __future__ import annotations

import json
import os
from difflib import SequenceMatcher
from typing import Any


class MSDSRetriever:
    """MSDS 知识库检索器。

    初始化时加载同目录下的 msds_data.json，提供按成分名/别名/常见产品名检索的能力。
    """

    def __init__(self, data_path: str | None = None) -> None:
        # 默认数据文件与本文件同目录
        if data_path is None:
            data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "msds_data.json")

        if not os.path.exists(data_path):
            raise FileNotFoundError(f"MSDS 数据文件不存在: {data_path}")

        with open(data_path, "r", encoding="utf-8") as f:
            self._data: list[dict[str, Any]] = json.load(f)

        # 构建索引：id -> 记录，便于按 id 查询
        self._index_by_id: dict[str, dict[str, Any]] = {item["id"]: item for item in self._data}

    # ---------- 公开方法 ----------

    def list_all(self) -> list[dict[str, Any]]:
        """返回全部 MSDS 记录。"""
        return list(self._data)

    def get_by_id(self, id: str) -> dict[str, Any] | None:
        """按 id 精确查询，未命中返回 None。"""
        return self._index_by_id.get(id)

    def retrieve(self, ingredient_name: str, top_k: int = 3) -> list[dict[str, Any]]:
        """按成分名/别名/常见产品名检索 MSDS。

        Args:
            ingredient_name: 用户输入的成分名/化学品名/产品名/别名。
            top_k: 返回结果条数上限。

        Returns:
            命中的 MSDS 记录列表（已按匹配优先级排序）。若完全无任何关联，则返回空列表。
            注意：当无精确/子串命中时，本方法不会回退到"最相似项"，以避免误导；
            如需模糊相似项，请使用 retrieve_with_fuzzy 方法。
        """
        if not ingredient_name or not isinstance(ingredient_name, str):
            return []

        query = ingredient_name.strip()
        if not query:
            return []

        # 1) 精确匹配（不区分大小写）
        exact_hits: list[dict[str, Any]] = []
        for item in self._data:
            if self._exact_match(item, query):
                exact_hits.append(item)
        if exact_hits:
            return exact_hits[:top_k]

        # 2) 子串包含匹配
        substring_hits: list[tuple[float, dict[str, Any]]] = []
        query_lower = query.lower()
        for item in self._data:
            score = self._substring_score(item, query_lower)
            if score > 0.0:
                substring_hits.append((score, item))
        if substring_hits:
            # 按得分降序排序（得分综合考虑匹配字段优先级与匹配长度比例）
            substring_hits.sort(key=lambda x: x[0], reverse=True)
            return [item for _, item in substring_hits[:top_k]]

        # 3) 默认不返回模糊相似项，避免误导用户
        return []

    def retrieve_with_fuzzy(self, ingredient_name: str, top_k: int = 3, threshold: float = 0.4) -> list[dict[str, Any]]:
        """检索并在无精确/子串命中时，回退到 difflib 相似度排序。

        Args:
            ingredient_name: 用户输入。
            top_k: 返回结果条数上限。
            threshold: 相似度阈值（0~1），低于此值不返回。

        Returns:
            匹配的 MSDS 记录列表。
        """
        # 先走精确+子串匹配
        hits = self.retrieve(ingredient_name, top_k=top_k)
        if hits:
            return hits

        # 走相似度模糊匹配
        if not ingredient_name or not isinstance(ingredient_name, str):
            return []
        query = ingredient_name.strip()
        if not query:
            return []

        scored: list[tuple[float, dict[str, Any]]] = []
        for item in self._data:
            score = self._similarity_score(item, query)
            if score >= threshold:
                scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    # ---------- 内部辅助方法 ----------

    @staticmethod
    def _norm(s: str) -> str:
        """归一化字符串：去空白并转小写。"""
        return (s or "").strip().lower()

    def _exact_match(self, item: dict[str, Any], query: str) -> bool:
        """判断查询串是否与名称/别名/常见产品名之一完全匹配（不区分大小写）。"""
        q = self._norm(query)
        if not q:
            return False

        # 名称
        if self._norm(str(item.get("name", ""))) == q:
            return True

        # 别名
        for alias in item.get("aliases", []) or []:
            if self._norm(str(alias)) == q:
                return True

        # 常见产品名
        for prod in item.get("common_products", []) or []:
            if self._norm(str(prod)) == q:
                return True

        return False

    def _substring_score(self, item: dict[str, Any], query_lower: str) -> float:
        """计算子串匹配得分；不匹配返回 0。

        得分规则（叠加）：
        - 名称包含查询串：+ 1.0
        - 别名包含查询串：+ 0.8（任一别名命中即加）
        - 常见产品名包含查询串：+ 0.6（任一产品命中即加）
        - 在名称命中时，再叠加"查询长度 / 名称长度"作为微调，避免短查询命中过长名称时得分过高
        """
        if not query_lower:
            return 0.0

        score = 0.0

        name = str(item.get("name", "")).lower()
        if name and query_lower in name:
            # 短查询命中长名称时，比例越小得分越低
            ratio = len(query_lower) / max(len(name), 1)
            score += 1.0 + 0.5 * ratio  # 1.0 ~ 1.5

        for alias in item.get("aliases", []) or []:
            alias_l = str(alias).lower()
            if alias_l and query_lower in alias_l:
                ratio = len(query_lower) / max(len(alias_l), 1)
                score += 0.8 + 0.3 * ratio
                break  # 别名只计一次

        for prod in item.get("common_products", []) or []:
            prod_l = str(prod).lower()
            if prod_l and query_lower in prod_l:
                ratio = len(query_lower) / max(len(prod_l), 1)
                score += 0.6 + 0.2 * ratio
                break  # 产品名只计一次

        return score

    def _similarity_score(self, item: dict[str, Any], query: str) -> float:
        """使用 difflib.SequenceMatcher 计算查询与名称/别名/产品名的最大相似度。"""
        q = self._norm(query)
        if not q:
            return 0.0

        best = 0.0
        # 名称相似度（权重最高）
        name = self._norm(str(item.get("name", "")))
        if name:
            best = max(best, SequenceMatcher(None, q, name).ratio())

        # 别名相似度
        for alias in item.get("aliases", []) or []:
            a = self._norm(str(alias))
            if a:
                best = max(best, SequenceMatcher(None, q, a).ratio() * 0.95)

        # 常见产品名相似度
        for prod in item.get("common_products", []) or []:
            p = self._norm(str(prod))
            if p:
                best = max(best, SequenceMatcher(None, q, p).ratio() * 0.9)

        return best
