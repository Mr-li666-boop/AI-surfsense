import asyncio
import os
import tempfile
from datetime import datetime, UTC
from pathlib import Path
from uuid import uuid4
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import get_async_session
from app.models.document import Document
from app.models.workspace import Workspace
from app.tasks.document_tasks import ingest_document_task
from app.utils.doucment_utils import get_hash_filename_workspace, get_hash_in_sql, store_document_file

router = APIRouter()
logger = logging.getLogger(__name__)


MAX_FILE_SIZE_BYTES = config.MAX_FILE_SIZE_MB * 1024 * 1024

@router.post("/", status_code=202)
async def upload_document(
    workspace_id: int = Form(...),
    files: list[UploadFile] = File(...),
    use_vision_llm: bool = Form(False),
    session: AsyncSession = Depends(get_async_session),
    # dispatcher: TaskDispatcher = Depends(get_task_dispatcher),
):
    try:
        if not files:
            raise HTTPException(status_code=400, detail="未提供文件")


        for file in files:
            file_size = file.size or 0

            # 判断是否超过最大容量
            if file_size > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"文件大小 '{file.filename}' ({file_size / (1024 * 1024):.1f} MB) "
                           f"超过最大文件 {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB ",
                )

        # 并发读取所有文件，防止阻塞事件循环
        async def read_and_save(file: UploadFile) -> tuple[str, str, int, str | None]:
            """读取上传内容，并脱离事件循环写入临时文件。"""
            content = await file.read()
            file_size = len(content)
            filename = file.filename or "unknown"
            content_type = file.content_type

            # 判断是否超过最大容量
            if file_size > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"文件大小 '{file.filename}' ({file_size / (1024 * 1024):.1f} MB) "
                           f"超过最大文件 {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB ",
                )

            # 保存临时文件
            def _write_temp() -> str:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=os.path.splitext(filename)[1]
                ) as tmp:
                    tmp.write(content)
                    return tmp.name

            temp_path = await asyncio.to_thread(_write_temp)
            return temp_path, filename, file_size, content_type

        saved_files = await asyncio.gather(*(read_and_save(f) for f in files))

        # 为所有文件创建待处理文档
        created_documents: list[Document] = []

        # 记录需要处理的文件
        files_to_process: list[tuple[Document, str, str, str | None]] = []
        # 记录跳过了多少个重复文件
        skipped_duplicates = 0
        # 记录重复文件对应的数据库 ID
        duplicate_document_ids: list[int] = []

        for temp_path, filename, file_size, content_type in saved_files:
            try:

                # 根据文件名和工作空间获取唯一hash
                unique_hash = get_hash_filename_workspace(filename,workspace_id)

                # 去数据库查找有没有相同hash
                existing = await get_hash_in_sql(session, unique_hash)


                if existing:
                    # 如果已经保存过了
                    if existing.status == "ready":
                        os.unlink(temp_path)
                        skipped_duplicates += 1
                        duplicate_document_ids.append(existing.id)
                        continue

                    # 状态不是已保存，可能以前保存失败
                    existing.status = "pending"
                    existing.document_metadata = {
                        **(existing.document_metadata or {}),
                        "file_size": file_size,
                        "upload_time": datetime.now().isoformat(),
                    }
                    existing.updated_at = datetime.now(UTC)
                    created_documents.append(existing)
                    files_to_process.append((existing, temp_path, filename, content_type))
                    continue

                # 如果不存在
                document = Document(
                    workspace_id=workspace_id,
                    title=filename if filename != "unknown" else "Uploaded File",
                    file_type="file",
                    document_metadata={
                        "FILE_NAME": filename,
                        "file_size": file_size,
                        "upload_time": datetime.now().isoformat(),
                    },
                    unique_identifier_hash=unique_hash,
                    status="pending",
                    updated_at=datetime.now(UTC),
                    # TODO 目前写死，后面加用户认证再改
                    created_by_id=1

                )
                session.add(document)
                created_documents.append(document)
                files_to_process.append((document, temp_path, filename, content_type))

            except HTTPException:
                raise
            except Exception as e:
                os.unlink(temp_path)
                raise HTTPException(
                    status_code=422,
                    detail=f"文件处理失败 {filename}: {e!s}",
                ) from e

        # 将文档基本信息保存到数据库
        if created_documents:
            await session.commit()
            for doc in created_documents:
                await session.refresh(doc)


        # 将原始上传文件持久化保存至持久化存储
        for document,temp_path,filename,content_type in files_to_process:
            try:
                # 异步多线程读取文件二进制
                original_bytes = await asyncio.to_thread(
                    lambda p=temp_path: Path(p).read_bytes()
                )

                # 保存原始文件
                await store_document_file(
                    session,
                    document_id=document.id,
                    workspace_id=workspace_id,
                    data=original_bytes,
                    filename=filename,
                    mime_type=content_type,
                    # TODO 目前写死，后面加用户认证再改
                    created_by_id=1,
                )

            except Exception as storage_error:
                logger.warning(
                "文档 % s 的原始上传文件存储失败：% s",
                document.id,
                storage_error,
                )

        await session.commit()

        # 异步进行文档向量化






    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to upload files: {e!s}"
        ) from e




