from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Document
from app.models.base import BaseModel


class DocumentFile(BaseModel):
    __tablename__ = "document_files"

    # 主键
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # 关联文档
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 所属工作空间
    workspace_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 文件类型
    kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ORIGINAL",
        server_default=text("'ORIGINAL'"),
        index=True,
    )

    # 存储后端，例如 local、azure
    storage_backend: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="local",
        server_default=text("'local'"),
    )

    # 实际文件存储路径或存储标识
    storage_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    # 用户上传时的原始文件名
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # MIME 类型
    mime_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None,
    )

    # 文件大小，单位字节
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    # SHA-256 校验值
    checksum_sha256: Mapped[str | None] = mapped_column(
        CHAR(64),
        nullable=True,
        default=None,
    )

    # 上传者用户 ID
    created_by_id: Mapped[int | UUID | None] = mapped_column(
        BigInteger,
        nullable=True,
        default=None,
        index=True,
    )

    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )

    # ORM 关系
    document: Mapped[Document] = relationship(
        "Document",
        back_populates="files",
    )