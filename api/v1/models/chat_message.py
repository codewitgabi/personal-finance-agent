from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from enum import Enum as PyEnum
from sqlalchemy import String, ForeignKey, Integer, Text, Enum, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from api.v1.models.abstract_base import AbstractBaseModel

if TYPE_CHECKING:
    from api.v1.models.conversation import Conversation


class MessageRole(PyEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MessageStatus(PyEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class FinishReason(PyEnum):
    STOP = "stop"  # Model hit a natural stopping point
    LENGTH = "length"  # Maximum token limit reached
    TOOL_CALLS = "tool_calls"  # Model requested tool/function calls
    CONTENT_FILTER = "content_filter"  # Content was filtered
    ERROR = "error"  # An error occurred


class ChatMessage(AbstractBaseModel):
    __tablename__ = "chat_messages"

    # Conversation tracking
    conversation_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the conversation this message belongs to",
    )
    parent_message_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to parent message for threading/replies",
    )

    # Message content
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, native_enum=False),
        nullable=False,
        index=True,
        comment="Message role: user, assistant, system, or tool",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="The actual message text content"
    )

    # Model information
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="LLM model identifier (e.g., 'gemini-2.5-flash', 'gpt-4', 'claude-3')",
    )
    temperature: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Temperature parameter used for this generation",
    )

    # Token tracking (critical for cost analysis)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Number of tokens in the input/prompt"
    )
    completion_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Number of tokens in the completion/response"
    )
    total_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Total tokens used (prompt + completion)",
    )

    # Status and completion
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus, native_enum=False),
        nullable=False,
        default=MessageStatus.COMPLETED,
        index=True,
    )
    finish_reason: Mapped[Optional[FinishReason]] = mapped_column(
        Enum(FinishReason, native_enum=False),
        nullable=True,
        comment="Reason why generation stopped (stop, length, tool_calls, etc.)",
    )

    # Performance metrics
    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Response latency in milliseconds"
    )

    # Metadata for tool calls, function calls, and other structured data
    message_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured metadata: tool_calls, function_calls, usage details, etc.",
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )
    parent_message: Mapped[Optional["ChatMessage"]] = relationship(
        "ChatMessage", remote_side="ChatMessage.id", backref="child_messages"
    )

    def to_dict(self) -> dict:
        """Convert message to dictionary format for API responses."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "parent_message_id": self.parent_message_id,
            "role": self.role.value if hasattr(self.role, "value") else str(self.role),
            "content": self.content,
            "model": self.model,
            "temperature": (
                float(self.temperature) if self.temperature is not None else None
            ),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "status": (
                self.status.value if hasattr(self.status, "value") else str(self.status)
            ),
            "finish_reason": (
                self.finish_reason.value
                if self.finish_reason and hasattr(self.finish_reason, "value")
                else (str(self.finish_reason) if self.finish_reason else None)
            ),
            "latency_ms": self.latency_ms,
            "metadata": self.message_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
