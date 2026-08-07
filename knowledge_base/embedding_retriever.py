"""MSDS 知识库嵌入检索器（Embedding + FAISS 向量检索）。

本模块实现 EmbeddingRetriever 类，使用阿里云百炼 text-embedding-v3 模型生成向量，
结合 FAISS 索引进行语义检索。相比 difflib 模糊匹配，语义检索能理解同义词、
俗称、中英文混用等复杂查询场景。

检索策略（优先级从高到低）：
1. 精确匹配（化学品名/别名/产品名）
2. 子串匹配（名称包含查询串）
3. FAISS 语义向量检索（余弦相似度）
4. difflib 相似度兜底
"""
from __future__ import annotations

import json
import logging
import os
import pickle
from difflib import SequenceMatcher
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

# 尝试导入 FAISS（可选依赖，未安装时降级为精确+模糊匹配）
FAISS_AVAILABLE = False
DASHSCOPE_AVAILABLE = False
np = None

try:
    import numpy as np
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    logger.warning("faiss-cpu 未安装，语义检索不可用，降级为精确+模糊匹配")

try:
    import dashscope
    DASHSCOPE_AVAILABLE = True
except ImportError:
    logger.warning("dashscope SDK 未安装，语义检索不可用")


class EmbeddingRetriever:
    """MSDS 知识库嵌入检索器：语义向量检索 + 精确匹配混合策略。

    初始化时加载 msds_data.json，为每条记录生成 embedding 向量并构建 FAISS 索引。
    检索时优先精确匹配，未命中时回退到语义向量检索。
    """

    def __init__(
        self,
        data_path: str | None = None,
        embedding_cache_path: str | None = None,
    ) -> None:
        if data_path is None:
            data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "msds_data.json")

        if not os.path.exists(data_path):
            raise FileNotFoundError(f"MSDS 数据文件不存在: {data_path}")

        with open(data_path, "r", encoding="utf-8") as f:
            self._data: list[dict[str, Any]] = json.load(f)

        # 索引目录（用于缓存 embedding）
        self._index_dir = os.path.dirname(os.path.abspath(__file__))
        self._embedding_cache_path = embedding_cache_path or os.path.join(
            self._index_dir, ".embedding_cache.pkl"
        )

        # 构建精确匹配索引
        self._build_alias_index()

        # 构建向量索引
        self._faiss_index: Any = None
        self._embeddings: np.ndarray | None = None
        self._build_vector_index()

    def _build_alias_index(self) -> None:
        """构建别名索引：alias -> record_id 的快速查找映射。"""
        self._alias_index: dict[str, str] = {}
        for item in self._data:
            item_id = item.get("id", "")
            # 名称
            name = item.get("name", "")
            if name:
                self._alias_index[name.lower()] = item_id
            # 别名
            for alias in item.get("aliases", []) or []:
                self._alias_index[alias.lower()] = item_id
            # 常见产品名
            for prod in item.get("common_products", []) or []:
                self._alias_index[prod.lower()] = item_id

    def _build_vector_index(self) -> None:
        """构建 FAISS 向量索引（优先使用缓存）。"""
        if not FAISS_AVAILABLE:
            return

        # 尝试从缓存加载
        if self._load_embedding_cache():
            logger.info(f"从缓存加载 {len(self._data)} 条 embedding 向量")
            return

        # 生成新 embedding
        if not DASHSCOPE_AVAILABLE:
            logger.warning("dashscope 不可用，跳过 embedding 生成")
            return

        try:
            texts = self._build_texts_for_embedding()
            if not texts:
                return

            logger.info(f"生成 {len(texts)} 条 embedding 向量...")
            embeddings = self._batch_embed(texts)
            if embeddings is not None and len(embeddings) > 0:
                self._embeddings = embeddings
                self._build_faiss_index(embeddings)
                self._save_embedding_cache()
                logger.info(f"FAISS 索引构建完成，维度: {embeddings.shape[1]}")
        except Exception as e:
            logger.warning(f"Embedding 生成失败，降级为精确匹配: {e}")

    def _build_texts_for_embedding(self) -> list[str]:
        """为每条 MSDS 记录构造用于 embedding 的文本。"""
        texts = []
        for item in self._data:
            parts = []
            parts.append(f"化学品名称: {item.get('name', '')}")
            aliases = item.get("aliases", [])
            if aliases:
                parts.append(f"别名: {'、'.join(str(a) for a in aliases)}")
            products = item.get("common_products", [])
            if products:
                parts.append(f"常见产品: {'、'.join(str(p) for p in products)}")
            category = item.get("category", "")
            if category:
                parts.append(f"类别: {category}")
            hazard = item.get("hazard_level", "")
            if hazard:
                parts.append(f"危险等级: {hazard}")
            toxicity = item.get("toxicity", "")
            if toxicity:
                parts.append(f"毒性: {toxicity}")
            texts.append("；".join(parts))
        return texts

    def _batch_embed(self, texts: list[str], batch_size: int = 10) -> np.ndarray | None:
        """批量调用百炼 Embedding API 生成向量。"""
        if not DASHSCOPE_AVAILABLE:
            return None

        dashscope.api_key = settings.DASHSCOPE_API_KEY
        if settings.DASHSCOPE_API_BASE:
            dashscope.base_http_api_url = settings.DASHSCOPE_API_BASE

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                resp = dashscope.TextEmbedding.call(
                    model=settings.EMBEDDING_MODEL,
                    input=batch,
                )
                if resp.status_code == 200 and hasattr(resp, "output"):
                    for emb in resp.output.get("embeddings", []):
                        all_embeddings.append(emb.get("embedding", []))
                else:
                    logger.warning(f"Embedding API 调用失败: {resp.message}")
                    # 失败时填充零向量，保持索引对齐
                    for _ in batch:
                        all_embeddings.append([0.0] * 1024)
            except Exception as e:
                logger.warning(f"Embedding API 异常: {e}")
                for _ in batch:
                    all_embeddings.append([0.0] * 1024)

        if not all_embeddings:
            return None
        return np.array(all_embeddings, dtype=np.float32)

    def _build_faiss_index(self, embeddings: np.ndarray) -> None:
        """构建 FAISS 索引（L2 距离 + 归一化 = 余弦相似度）。"""
        if not FAISS_AVAILABLE:
            return

        dimension = embeddings.shape[1]
        # L2 归一化后使用 IndexFlatIP 做内积 = 余弦相似度
        faiss.normalize_L2(embeddings)
        self._faiss_index = faiss.IndexFlatIP(dimension)
        self._faiss_index.add(embeddings)

    def _load_embedding_cache(self) -> bool:
        """从本地缓存加载 embedding。"""
        if not os.path.exists(self._embedding_cache_path):
            return False
        try:
            with open(self._embedding_cache_path, "rb") as f:
                cache = pickle.load(f)
            embeddings = cache.get("embeddings")
            if embeddings is not None and isinstance(embeddings, np.ndarray):
                if embeddings.shape[0] == len(self._data):
                    self._embeddings = embeddings.copy()
                    faiss.normalize_L2(self._embeddings)
                    self._build_faiss_index(self._embeddings)
                    return True
        except Exception as e:
            logger.warning(f"加载 embedding 缓存失败: {e}")
        return False

    def _save_embedding_cache(self) -> None:
        """保存 embedding 到本地缓存。"""
        if self._embeddings is None:
            return
        try:
            with open(self._embedding_cache_path, "wb") as f:
                pickle.dump({"embeddings": self._embeddings}, f)
        except Exception as e:
            logger.warning(f"保存 embedding 缓存失败: {e}")

    # ---------- 公开方法 ----------

    def list_all(self) -> list[dict[str, Any]]:
        """返回全部 MSDS 记录。"""
        return list(self._data)

    def get_by_id(self, id: str) -> dict[str, Any] | None:
        """按 id 精确查询。"""
        for item in self._data:
            if item.get("id") == id:
                return item
        return None

    def retrieve(self, ingredient_name: str, top_k: int = 3) -> list[dict[str, Any]]:
        """按成分名/别名/常见产品名检索 MSDS（混合策略）。

        策略：
        1. 精确匹配（不区分大小写）
        2. 子串包含匹配
        3. FAISS 语义向量检索（余弦相似度 ≥ 0.6）
        4. difflib 相似度兜底（≥ 0.4）

        Args:
            ingredient_name: 用户输入的成分名/化学品名/产品名/别名。
            top_k: 返回结果条数上限。

        Returns:
            命中的 MSDS 记录列表（已按匹配优先级排序）。
        """
        if not ingredient_name or not isinstance(ingredient_name, str):
            return []

        query = ingredient_name.strip()
        if not query:
            return []

        # 1. 精确匹配
        exact = self._exact_match(query)
        if exact:
            return exact[:top_k]

        # 2. 子串匹配
        substring = self._substring_match(query)
        if substring:
            return substring[:top_k]

        # 3. FAISS 语义检索
        if self._faiss_index is not None and FAISS_AVAILABLE:
            semantic = self._semantic_match(query, top_k=top_k, threshold=0.6)
            if semantic:
                return semantic

        # 4. difflib 相似度兜底
        fuzzy = self._fuzzy_match(query, top_k=top_k, threshold=0.4)
        return fuzzy

    def _exact_match(self, query: str) -> list[dict[str, Any]]:
        """精确匹配（不区分大小写）。"""
        q = query.lower().strip()
        results = []
        for item in self._data:
            # 名称
            if item.get("name", "").lower() == q:
                results.append(item)
                continue
            # 别名
            for alias in item.get("aliases", []) or []:
                if alias.lower() == q:
                    results.append(item)
                    break
            else:
                # 常见产品名
                for prod in item.get("common_products", []) or []:
                    if prod.lower() == q:
                        results.append(item)
                        break
        return results

    def _substring_match(self, query: str) -> list[dict[str, Any]]:
        """子串包含匹配。"""
        q = query.lower()
        results: list[tuple[float, dict[str, Any]]] = []
        for item in self._data:
            score = 0.0
            name = item.get("name", "").lower()
            if q in name:
                score = 1.0 + 0.5 * len(q) / max(len(name), 1)
            else:
                for alias in item.get("aliases", []) or []:
                    if q in alias.lower():
                        score = max(score, 0.8)
                        break
                else:
                    for prod in item.get("common_products", []) or []:
                        if q in prod.lower():
                            score = max(score, 0.6)
                            break
            if score > 0:
                results.append((score, item))
        results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in results]

    def _semantic_match(self, query: str, top_k: int = 3, threshold: float = 0.6) -> list[dict[str, Any]]:
        """FAISS 语义向量检索。"""
        if self._faiss_index is None or not DASHSCOPE_AVAILABLE:
            return []

        try:
            # 生成查询向量
            dashscope.api_key = settings.DASHSCOPE_API_KEY
            if settings.DASHSCOPE_API_BASE:
                dashscope.base_http_api_url = settings.DASHSCOPE_API_BASE

            resp = dashscope.TextEmbedding.call(
                model=settings.EMBEDDING_MODEL,
                input=query,
            )
            if resp.status_code != 200:
                return []

            embedding = resp.output["embeddings"][0]["embedding"]
            query_vec = np.array([embedding], dtype=np.float32)
            faiss.normalize_L2(query_vec)

            # 检索（返回 top_k*2 后过滤）
            actual_k = min(top_k * 2, len(self._data))
            scores, indices = self._faiss_index.search(query_vec, actual_k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self._data):
                    continue
                if score >= threshold:
                    item = self._data[idx].copy()
                    item["_semantic_score"] = float(score)
                    results.append(item)
                    if len(results) >= top_k:
                        break
            return results
        except Exception as e:
            logger.warning(f"语义检索异常: {e}")
            return []

    def _fuzzy_match(self, query: str, top_k: int = 3, threshold: float = 0.4) -> list[dict[str, Any]]:
        """difflib 相似度兜底。"""
        q = query.lower()
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in self._data:
            best = 0.0
            name = item.get("name", "").lower()
            if name:
                best = max(best, SequenceMatcher(None, q, name).ratio())
            for alias in item.get("aliases", []) or []:
                best = max(best, SequenceMatcher(None, q, alias.lower()).ratio() * 0.95)
            for prod in item.get("common_products", []) or []:
                best = max(best, SequenceMatcher(None, q, prod.lower()).ratio() * 0.9)
            if best >= threshold:
                scored.append((best, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]
