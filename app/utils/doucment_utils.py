import hashlib
import os
import uuid
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.models import Document
from app.models.doument_file import DocumentFile
from app.utils.storagebackend import StorageBackend


# 根据文件名和工作空间获取唯一hash
def get_hash_filename_workspace(
        filename: str | int | float,
        workspace_id: int
) -> str:

    # 转换为字符串，以处理不同类型的数据
    identifier_str = str(filename)

    # 唯一标识符以及工作区 ID
    combined_data = f"{identifier_str}:{workspace_id}"

    return hashlib.sha256(combined_data.encode("utf-8")).hexdigest()


# 去数据库查找有没有相同hash
async def get_hash_in_sql(
        session: AsyncSession,
        unique_hash : str
)-> Document | None:
    existing_doc_result = await session.execute(
        select(Document)
        .where(Document.unique_identifier_hash == unique_hash)
    )

    return existing_doc_result.scalars().first()


# 生成单个文档文件的存储键
def build_document_file_key(
    *,
    workspace_id: int,
    document_id: int,
    kind: str,
    filename: str,
) -> str:
    """生成单个文档文件的存储键.

    格式：documents/{workspace_id}/{document_id}/{kind}/{uuid}{ext}。
    """
    extension = os.path.splitext(filename)[1].lower()
    unique = uuid.uuid4().hex
    return (
        f"documents/{workspace_id}/{document_id}/"
        f"{kind.lower()}/{unique}{extension}"
    )

# 持久化保存文档到MySQL
async def store_document_file(
        session: AsyncSession,
        *,
        document_id: int,
        workspace_id: int,
        data: bytes,
        filename: str,
        mime_type: str | None = None,
        kind: str = "ORIGINAL",
        created_by_id: int | UUID | None = None,
        backend: StorageBackend | None = None,
) -> DocumentFile:

    """向存储写入字节，并向会话中添加一条DocumentFile记录"""

    # 生成单个文档文件的存储键
    key = build_document_file_key(
        workspace_id=workspace_id,
        document_id=document_id,
        kind=kind,
        filename=filename,
    )

    # 将文件保存到文件夹
    await backend.put(key, data, content_type=mime_type)

    record = DocumentFile(
        document_id=document_id,
        workspace_id=workspace_id,
        kind=kind,
        storage_backend=backend.backend_name,
        storage_key=key,
        original_filename=filename,
        mime_type=mime_type,
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
        created_by_id=created_by_id,
    )
    session.add(record)
    return record











