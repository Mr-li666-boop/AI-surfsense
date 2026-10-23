
from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    String,
    JSON,
    DateTime,
    BigInteger,
    Integer,
    text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.doument_file import DocumentFile


class Document(BaseModel):

    __tablename__ = "documents"

    # 文档主键 ID
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    # 所属工作空间 ID
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 文档显示名称
    title: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    # 文件类型或扩展名，例如 pdf、docx、txt
    file_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    # 原始文件在服务器上的存储路径
    file_path: Mapped[str] = mapped_column(
        String(500), nullable=False
    )

    # 文档处理状态：pending、processing、ready、failed
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )

    # 文档处理失败时的错误信息
    error_message: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None
    )

    # 文档记录创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(3),
        nullable=False,
        server_default=func.current_timestamp(3),
    )

    # 文档记录最后更新时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(3),
        nullable=False,
        server_default=func.current_timestamp(3),
        onupdate=func.current_timestamp(3),
    )

    # 文档唯一标识哈希值，用于识别文档身份及幂等处理
    unique_identifier_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None
    )

    # 文档扩展元数据，例如文件名、文件大小、上传时间
    document_metadata: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None
    )

    # 文件 MIME 类型，例如 application/pdf、text/plain
    content_type: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )

    # 创建者或上传者的用户 ID
    created_by_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )

    # 所属工作空间
    workspace = relationship(
        "Workspace", back_populates="documents"
    )

    files: Mapped[list[DocumentFile]] = relationship(
        "DocumentFile",
        back_populates="document",
        cascade="all, delete-orphan",
    )
