
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from pathlib import Path


class StorageBackend:
    """将文件保存到本地磁盘。"""

    backend_name = "local"

    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = Path(base_dir).resolve()

    def _get_path(self, key: str) -> Path:
        """根据存储 key 获取文件路径，并防止路径穿越。"""
        path = (self.base_dir / key).resolve()

        if not path.is_relative_to(self.base_dir):
            raise ValueError("非法的文件存储路径")

        return path

    async def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> None:
        """保存完整文件，已存在则覆盖。"""
        path = self._get_path(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)

    async def put_stream(
        self,
        key: str,
        chunks: AsyncIterable[bytes],
        *,
        content_type: str | None = None,
    ) -> None:
        """以异步流的方式保存文件，避免一次性加载整个文件。"""
        path = self._get_path(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)

        with path.open("wb") as file:
            async for chunk in chunks:
                await asyncio.to_thread(file.write, chunk)

    async def open_stream(self, key: str) -> AsyncIterator[bytes]:
        """分块读取文件。"""
        path = self._get_path(key)

        with path.open("rb") as file:
            while True:
                chunk = await asyncio.to_thread(file.read, 1024 * 1024)
                if not chunk:
                    break
                yield chunk

    async def open_range(
        self,
        key: str,
        start: int,
        end: int,
    ) -> AsyncIterator[bytes]:
        """读取指定字节范围，end 是包含在内的。"""
        if start < 0 or end < start:
            raise ValueError("无效的字节范围")

        path = self._get_path(key)

        with path.open("rb") as file:
            await asyncio.to_thread(file.seek, start)
            remaining = end - start + 1

            while remaining > 0:
                chunk = await asyncio.to_thread(
                    file.read, min(1024 * 1024, remaining)
                )
                if not chunk:
                    break

                remaining -= len(chunk)
                yield chunk

    async def delete(self, key: str) -> None:
        """删除文件；文件不存在时不报错。"""
        path = self._get_path(key)
        await asyncio.to_thread(path.unlink, missing_ok=True)

    async def exists(self, key: str) -> bool:
        """判断文件是否存在。"""
        path = self._get_path(key)
        return await asyncio.to_thread(path.is_file)
