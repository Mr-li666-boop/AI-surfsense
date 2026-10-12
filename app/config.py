"""应用配置 - 所有环境变量的单一来源。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class LLMProvider(BaseModel):
    """单个 LLM 提供商的配置（运行时动态切换用）。"""
    api_key: str
    base_url: str


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── MySQL ───────────────────────────────────────────────────────
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "my_ai_book"

    # ─── Milvus ──────────────────────────────────────────────────────
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    COLLECTION_NAME: str = "doc_vectors"
    EMBEDDING_DIM: int = 1024  # 默认值，后续可按模型调整

    # ─── Redis（Celery broker + result backend）───────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ─── LLM 提供商（支持多个，运行时按 provider 字段切换）──────────
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"

    CLAUDE_API_KEY: str = ""
    CLAUDE_BASE_URL: str = "https://api.anthropic.com/v1"
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    DEFAULT_PROVIDER: Literal["deepseek", "openai", "claude"] = "deepseek"
    DEFAULT_MODEL: str = "deepseek-chat"

    # ─── 文档处理 ────────────────────────────────────────────────────
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    SEARCH_TOP_K: int = 5

    # ─── 阿里云 Embedding（固定，不随 LLM 切换）─────────────────────────
    # 阿里 DashScope Embedding 兼容 OpenAI API 格式
    ALIYUN_EMBEDDING_API_KEY: str = ""
    ALIYUN_EMBEDDING_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ALIYUN_EMBEDDING_MODEL: str = "text-embedding-v3"

    def current_llm(self) -> dict[str, str]:
        """根据 DEFAULT_PROVIDER 返回当前 LLM 配置字典。"""
        providers = {
            "deepseek": {"api_key": self.DEEPSEEK_API_KEY, "base_url": self.DEEPSEEK_BASE_URL},
            "openai": {"api_key": self.OPENAI_API_KEY, "base_url": self.OPENAI_BASE_URL},
            "claude": {"api_key": self.CLAUDE_API_KEY, "base_url": self.CLAUDE_BASE_URL},
        }
        return providers[self.DEFAULT_PROVIDER]

    def embedding_config(self) -> dict[str, str]:
        """返回固定 Embedding 配置，独立于 LLM 切换逻辑。"""
        return {
            "api_key": self.ALIYUN_EMBEDDING_API_KEY,
            "base_url": self.ALIYUN_EMBEDDING_BASE_URL,
        }


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()


config = get_config()