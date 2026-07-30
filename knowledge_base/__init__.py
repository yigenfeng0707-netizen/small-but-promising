"""knowledge_base 包：MSDS 知识库与本地检索。

导出 MSDSRetriever 以便上层 Agent 直接使用：
    from knowledge_base import MSDSRetriever
    retriever = MSDSRetriever()
    results = retriever.retrieve("盐酸")
"""

from .retriever import MSDSRetriever

__all__ = ["MSDSRetriever"]
