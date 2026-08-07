"""knowledge_base 包：MSDS 知识库与检索。

导出两种检索器：
- EmbeddingRetriever（推荐）：语义向量检索 + 精确匹配混合策略
- MSDSRetriever（兼容）：精确 + 模糊匹配

使用示例：
    from knowledge_base import EmbeddingRetriever
    retriever = EmbeddingRetriever()
    results = retriever.retrieve("盐酸")
"""

from .retriever import MSDSRetriever
from .embedding_retriever import EmbeddingRetriever

__all__ = ["MSDSRetriever", "EmbeddingRetriever"]
