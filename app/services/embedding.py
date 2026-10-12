"""Embedding 服务：固定调用阿里云 DashScope，与 LLM 切换无关。"""
from __future__ import annotations

import logging
from openai import AsyncOpenAI
from app.config import config

logger = logging.getLogger(__name__)


async def embed_texts(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    """批量将文本转为向量，始终走阿里云 Embedding。"""
    client = _get_client()
    response = await client.embeddings.create(
        input=texts,
        model=model or config.ALIYUN_EMBEDDING_MODEL,
    )
    return [item.embedding for item in response.data]


async def embed_single(text: str, *, model: str | None = None) -> list[float]:
    """单文本转向量。"""
    result = await embed_texts([text], model=model)
    return result[0]


def _get_client() -> AsyncOpenAI:
    """固定使用阿里云 Embedding 配置，不走 LLM provider 切换逻辑。"""
    emb = config.embedding_config()
    return AsyncOpenAI(api_key=emb["api_key"], base_url=emb["base_url"])