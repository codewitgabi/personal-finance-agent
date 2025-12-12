from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.v1.models.abstract_base import AbstractBaseModel

if TYPE_CHECKING:
    from api.v1.models.user import User
    from api.v1.models.chat_message import ChatMessage


class Conversation(AbstractBaseModel):
    __tablename__ = "conversations"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    thread_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        unique=True,
        index=True,
        comment="Unique thread identifier for the conversation",
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=True,
        comment="AI-generated conversation title",
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="conversation", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Convert conversation to dictionary format for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "thread_id": self.thread_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
