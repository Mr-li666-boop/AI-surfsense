
import asyncio
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.models.document import Document
from app.services import parse_document, chunk, embed_texts
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# 单个批量任务内，最多同时处理 4 篇文档
MAX_DOCUMENT_CONCURRENCY = 4


async def _ingest_document(
    session: AsyncSession,
    doc: Document,
) -> None:
    """解析 → 分块 → 批量 Embedding → 写入 Milvus。"""

    # 1. 解析文档
    markdown_text = await parse_document(
        Path(doc.file_path)
    )

    if not markdown_text or not markdown_text.strip():
        raise ValueError("没有提取到任何文本内容")

    # 2. 分块
    passages = chunk(markdown_text)

    if not passages:
        raise ValueError("文档分块结果为空")

    texts = [passage.text for passage in passages]

    # 3. 一次性批量 Embedding
    # 保留你现有的异步 embed_texts 接口
    vectors = await embed_texts(texts)

    if len(vectors) != len(passages):
        raise ValueError(
            f"Embedding 数量不匹配："
            f"chunks={len(passages)}, vectors={len(vectors)}"
        )

    # 4. 写入 Milvus
    # get_milvus() 使用你项目中已有的实现
    from app.services import get_milvus

    client = get_milvus()

    # 当前沿用已有的逐 Chunk upsert 接口
    for passage, vector in zip(passages, vectors):
        client.upsert(
            document_id=doc.id,
            chunk_text=passage.text,
            vector=vector,
            workspace_id=doc.workspace_id,
        )

    logger.info(
        "文档 %s 索引完成，共 %s 个 chunks",
        doc.id,
        len(passages),
    )


async def process_document(document_id: int) -> dict:
    """处理单篇文档。数据库 Session 由当前任务独立创建。"""

    async with async_session_maker() as session:
        doc = await session.get(Document, document_id)

        if doc is None:
            logger.error("文档 %s 不存在", document_id)
            return {
                "document_id": document_id,
                "status": "not_found",
            }

        # 防止已经成功的文档被重复处理
        if doc.status == "ready":
            return {
                "document_id": document_id,
                "status": "ready",
                "skipped": True,
            }

        doc.status = "processing"
        doc.error_message = None
        await session.commit()

        try:
            await _ingest_document(session, doc)

            doc.status = "ready"
            doc.error_message = None

            await session.commit()

            return {
                "document_id": document_id,
                "status": "ready",
            }

        except Exception as exc:
            logger.exception(
                "文档 %s 向量化失败",
                document_id,
            )

            # 如果数据库事务失败，先回滚再尝试更新失败状态
            await session.rollback()

            try:
                doc = await session.get(
                    Document,
                    document_id,
                )

                if doc is not None:
                    doc.status = "failed"
                    doc.error_message = str(exc)[:500]
                    await session.commit()

            except Exception:
                await session.rollback()
                logger.exception(
                    "更新文档 %s 的失败状态时出错",
                    document_id,
                )

            # 抛出异常，让 Celery 决定是否重试
            raise


async def process_documents_batch(
    document_ids: list[int],
    max_concurrency: int = MAX_DOCUMENT_CONCURRENCY,
) -> list[dict]:
    """并发处理多篇文档，每篇文档使用独立 Session。"""

    if max_concurrency < 1:
        raise ValueError("max_concurrency 必须大于等于 1")

    semaphore = asyncio.Semaphore(max_concurrency)

    async def index_one(document_id: int) -> dict:
        async with semaphore:
            try:
                return await process_document(document_id)
            except Exception as exc:
                # 单篇文档失败不影响其他文档
                return {
                    "document_id": document_id,
                    "status": "failed",
                    "error": str(exc)[:500],
                }

    return await asyncio.gather(
        *(index_one(doc_id) for doc_id in document_ids)
    )


@celery_app.task(
    name="documents.ingest",
    bind=True,
    max_retries=3,
)
def ingest_document_task(self, document_id: int):
    """原有单文档任务入口，保持兼容。"""

    try:
        return asyncio.run(
            process_document(document_id)
        )

    except Exception as exc:
        logger.exception(
            "文档 %s 的索引任务执行失败",
            document_id,
        )

        raise self.retry(
            exc=exc,
            countdown=10,
        )


@celery_app.task(
    name="documents.ingest_batch",
)
def ingest_documents_batch_task(
    document_ids: list[int],
):
    """批量文档任务入口。"""

    return asyncio.run(
        process_documents_batch(
            document_ids,
            max_concurrency=MAX_DOCUMENT_CONCURRENCY,
        )
    )