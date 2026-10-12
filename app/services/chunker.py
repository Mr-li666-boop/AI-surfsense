"""文本分块：递归分层切分，保持语义完整性。

完全照搬 surfsense_local/backend/worker/ingestion/chunking.py。
切分优先级（从高到低）：标题 → 段落 → 行 → 句子 → 空白 → 硬切兜底。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, NamedTuple

from chonkie import RecursiveChunker, RecursiveLevel, RecursiveRules

# bge-small 的 token 上限约 512，留点余量，和源码保持一致
CHUNK_TOKENS = 480


class Passage(NamedTuple):
    """一个文本片段及其在原文中的行号位置。"""
    text: str
    start_line: int
    end_line: int


def chunk(markdown: str, *, tokenizer: Any = None, chunk_size: int = CHUNK_TOKENS) -> list[Passage]:
    """将 Markdown 文本切分为 passages，供 embedding 模型消费。

    Args:
        markdown: 原始 Markdown 文本（来自 parse_document）
        tokenizer: 自定义 tokenizer，None 时使用 chonkie 默认（bpe）
        chunk_size: 每块最大 token 数（默认 480）

    Returns:
        Passage 列表，每项含文本和行号范围
    """
    if not markdown.strip():
        return []

    chunker = RecursiveChunker(
        tokenizer=tokenizer if tokenizer is not None else _default_tokenizer(),
        chunk_size=chunk_size,
        rules=_rules(),
        min_characters_per_chunk=24,  # 和源码一致
    )

    passages = (_passage(markdown, piece) for piece in chunker.chunk(markdown))
    return [passage for passage in passages if passage.text]


@lru_cache(maxsize=1)
def _rules() -> RecursiveRules:
    """构建递归切分规则，优先级从高到低。

    切分策略：
      1. 标题边界（# heading）   — 不切断章节
      2. 段落边界（空行）        — 不切断段落
      3. 行边界（换行）          — 不切断行
      4. 句子边界（. ! ?）      — 不切断句子
      5. 空白字符边界            — 按词切
      6. 硬切兜底               — 超长段强制截断
    """
    return RecursiveRules(
        levels=[
            RecursiveLevel(delimiters=["\n#"], include_delim="next"),
            RecursiveLevel(delimiters=["\n\n"], include_delim="prev"),
            RecursiveLevel(delimiters=["\n"], include_delim="prev"),
            RecursiveLevel(delimiters=[". ", "! ", "? "], include_delim="prev"),
            RecursiveLevel(whitespace=True),
            RecursiveLevel(),
        ]
    )


@lru_cache(maxsize=1)
def _default_tokenizer() -> Any:
    """返回默认 tokenizer。

    源码注释：
      tokenizer 在此处硬编码，而非跟随 active embedder。
      原因：如果由 embedder 决定边界，换模型会重新切分，
      导致 chunk_id 迁移，破坏所有已有引用。
    """
    # 简化版：返回 None，让 chonkie 用内置 bpe tokenizer
    # 如需精确对齐，可引入 tokenizers 库加载 bge tokenizer
    return None


def _passage(markdown: str, piece: Any) -> Passage:
    """修剪 Chonkie 携带的分隔符，并计算行号定位。

    Args:
        markdown: 原始 Markdown 文本（用于行号计算）
        piece: Chonkie 切分结果（含 start_index, end_index, text）

    Returns:
        Passage: 清洗后的文本 + 起始/结束行号
    """
    lead = len(piece.text) - len(piece.text.lstrip())
    trail = len(piece.text) - len(piece.text.rstrip())
    start = piece.start_index + lead
    end = piece.end_index - trail

    return Passage(
        piece.text.strip(),
        markdown.count("\n", 0, start) + 1,
        markdown.count("\n", 0, max(start, end - 1)) + 1,
    )