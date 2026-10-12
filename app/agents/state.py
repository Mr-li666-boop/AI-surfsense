"""Agent 图状态定义。

对齐源码的 SurfSenseFilesystemState 模式，但做简化：
- messages: LangGraph 标准对话历史
- citation_registry: [n] → 源文档映射（每次 search_knowledge_base 后合并）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    """单轮对话的完整状态，持久化到 checkpointer。"""

    messages: list[Any] = field(default_factory=list)
    workspace_id: int = 0
    citation_registry: dict[int, dict[str, Any]] = field(default_factory=dict)
    _next_citation_n: int = 1  # 内部计数器，不入 checkpoint

    def register_citation(self, doc_id: int, chunk_text: str, score: float) -> int:
        """注册一个引用，返回 [n] 编号；重复来源返回已有编号。"""
        key = (doc_id, chunk_text[:80])
        for n, entry in self.citation_registry.items():
            if entry.get("_key") == key:
                return n
        n = self._next_citation_n
        self._next_citation_n += 1
        self.citation_registry[n] = {
            "n": n,
            "doc_id": doc_id,
            "chunk_text": chunk_text,
            "score": score,
            "_key": key,
        }
        return n

    def resolve(self, n: int) -> dict[str, Any] | None:
        """根据 [n] 解析源文档信息。"""
        return self.citation_registry.get(n)