from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from api.v1.models.conversation import Conversation
from api.v1.utils.logger import get_logger

logger = get_logger("conversation_service")


class ConversationService:
    def __init__(self):
        pass

    def create_conversation(
        self,
        user_id: str,
        thread_id: str,
        title: Optional[str] = None,
        db: Session = None,
    ) -> Conversation:
        """
        Create a new conversation.

        Args:
            user_id: User identifier
            thread_id: Unique thread identifier
            title: Optional conversation title (can be generated later)
            db: Database session

        Returns:
            Created Conversation instance
        """
        conversation = Conversation(
            user_id=user_id,
            thread_id=thread_id,
            title=title,
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        logger.info(
            "Conversation created",
            extra={
                "conversation_id": conversation.id,
                "user_id": user_id,
                "thread_id": thread_id,
            },
        )

        return conversation

    def get_conversation_by_thread_id(
        self, user_id: str, thread_id: str, db: Session
    ) -> Optional[Conversation]:
        """
        Get a conversation by thread_id.

        Args:
            user_id: User identifier
            thread_id: Thread identifier
            db: Database session

        Returns:
            Conversation instance or None if not found
        """
        return db.scalar(
            select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.thread_id == thread_id,
            )
        )

    def get_conversation_by_id(
        self, conversation_id: str, user_id: str, db: Session
    ) -> Optional[Conversation]:
        """
        Get a conversation by ID (with user verification).

        Args:
            conversation_id: Conversation identifier
            user_id: User identifier for verification
            db: Database session

        Returns:
            Conversation instance or None if not found or user doesn't have access
        """
        return db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )

    def update_conversation_title(
        self, conversation_id: str, title: str, db: Session
    ) -> Optional[Conversation]:
        """
        Update conversation title.

        Args:
            conversation_id: Conversation identifier
            title: New title
            db: Database session

        Returns:
            Updated Conversation instance or None if not found
        """
        conversation = db.scalar(
            select(Conversation).where(Conversation.id == conversation_id)
        )

        if not conversation:
            return None

        conversation.title = title
        db.commit()
        db.refresh(conversation)

        logger.info(
            "Conversation title updated",
            extra={"conversation_id": conversation_id, "title": title},
        )

        return conversation

    def get_user_conversations(
        self, user_id: str, db: Session, limit: Optional[int] = None
    ) -> list[Conversation]:
        """
        Get all conversations for a user, ordered by most recent.

        Args:
            user_id: User identifier
            db: Database session
            limit: Optional limit on number of conversations

        Returns:
            List of Conversation instances ordered by most recent
        """
        query = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )

        if limit:
            query = query.limit(limit)

        return list(db.scalars(query).all())


conversation_service = ConversationService()
