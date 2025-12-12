from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select
from api.v1.models.conversation import Conversation
from api.v1.models.chat_message import (
    ChatMessage,
    MessageRole,
    MessageStatus,
    FinishReason,
)
from api.v1.utils.logger import get_logger

logger = get_logger("chat_message_service")


class ChatMessageService:
    def __init__(self):
        pass

    def create_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        status: MessageStatus = MessageStatus.COMPLETED,
        finish_reason: Optional[FinishReason] = None,
        latency_ms: Optional[int] = None,
        message_metadata: Optional[dict] = None,
        parent_message_id: Optional[str] = None,
        db: Session = None,
    ) -> ChatMessage:
        """
        Create a new chat message in the database.

        Args:
            conversation_id: Conversation identifier
            role: Message role (USER, ASSISTANT, SYSTEM, TOOL)
            content: Message content text
            model: LLM model identifier
            temperature: Temperature parameter used
            prompt_tokens: Input token count
            completion_tokens: Output token count
            total_tokens: Total token count
            status: Message status
            finish_reason: Reason generation stopped
            latency_ms: Response latency in milliseconds
            message_metadata: Additional metadata (tool calls, etc.)
            parent_message_id: Parent message ID for threading
            db: Database session

        Returns:
            Created ChatMessage instance
        """
        chat_message = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            model=model,
            temperature=temperature,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            status=status,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            message_metadata=message_metadata,
            parent_message_id=parent_message_id,
        )

        db.add(chat_message)
        db.commit()
        db.refresh(chat_message)

        logger.info(
            "Chat message created",
            extra={
                "message_id": chat_message.id,
                "conversation_id": conversation_id,
                "role": role.value,
                "model": model,
            },
        )

        return chat_message

    def update_message(
        self,
        message_id: str,
        content: Optional[str] = None,
        status: Optional[MessageStatus] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        finish_reason: Optional[FinishReason] = None,
        latency_ms: Optional[int] = None,
        message_metadata: Optional[dict] = None,
        db: Session = None,
    ) -> Optional[ChatMessage]:
        """
        Update an existing chat message.

        Args:
            message_id: Message identifier
            content: Updated content (for appending chunks)
            status: Updated status
            prompt_tokens: Updated prompt token count
            completion_tokens: Updated completion token count
            total_tokens: Updated total token count
            finish_reason: Updated finish reason
            latency_ms: Updated latency
            message_metadata: Updated metadata
            db: Database session

        Returns:
            Updated ChatMessage instance or None if not found
        """
        message = db.scalar(select(ChatMessage).where(ChatMessage.id == message_id))

        if not message:
            return None

        if content is not None:
            message.content = content
        if status is not None:
            message.status = status
        if prompt_tokens is not None:
            message.prompt_tokens = prompt_tokens
        if completion_tokens is not None:
            message.completion_tokens = completion_tokens
        if total_tokens is not None:
            message.total_tokens = total_tokens
        if finish_reason is not None:
            message.finish_reason = finish_reason
        if latency_ms is not None:
            message.latency_ms = latency_ms
        if message_metadata is not None:
            # Merge metadata if it exists, otherwise replace
            if message.message_metadata and isinstance(message.message_metadata, dict):
                message.message_metadata = {
                    **message.message_metadata,
                    **message_metadata,
                }
            else:
                message.message_metadata = message_metadata

        db.commit()
        db.refresh(message)

        logger.info("Chat message updated", extra={"message_id": message_id})

        return message

    def get_conversation_messages(
        self,
        conversation_id: str,
        user_id: str,
        db: Session,
        limit: Optional[int] = None,
    ) -> list[ChatMessage]:
        """
        Get all messages for a specific conversation.

        Args:
            conversation_id: Conversation identifier
            user_id: User identifier for verification (ensures user owns the conversation)
            db: Database session
            limit: Optional limit on number of messages

        Returns:
            List of ChatMessage instances ordered by creation time
        """
        # Verify ownership through conversation relationship
        query = (
            select(ChatMessage)
            .join(Conversation, ChatMessage.conversation_id == Conversation.id)
            .where(
                ChatMessage.conversation_id == conversation_id,
                Conversation.user_id == user_id,
            )
            .order_by(ChatMessage.created_at.asc())
        )

        if limit:
            query = query.limit(limit)

        return list(db.scalars(query).all())


chat_message_service = ChatMessageService()
