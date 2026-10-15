"""文档模型。embedding 存 Milvus，这里只存元信息。"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import JSON
from app.models.base import BaseModel


class Document(BaseModel):

    __tablename__ = "documents"

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    unique_identifier_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    document_metadata: Mapped[dict | None] = mapped_column(JSON,nullable=True,default=dict,)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(String(500), default=None)

    workspace = relationship("Workspace", back_populates="documents")

