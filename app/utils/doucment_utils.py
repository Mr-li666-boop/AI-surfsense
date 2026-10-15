import hashlib

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.models import Document


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





