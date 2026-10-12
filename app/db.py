"""MySQL 异步引擎 + 会话工厂。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import config

DATABASE_URL = (
    f"mysql+aiomysql://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}"
    f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DB}"
)

engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


@asynccontextmanager
async def shielded_session():
    """客户端断开时保证 session.close() 不丢失。"""
    session = async_session_maker()
    try:
        yield session
    finally:
        await session.close()


async def init_db():
    """启动时建表（开发阶段用，生产走 Alembic 迁移）。"""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE DATABASE IF NOT EXISTS "
                                f"{config.MYSQL_DB}"))
        await conn.execute(text("SET NAMES utf8mb4"))