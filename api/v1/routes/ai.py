from typing import List
from fastapi import APIRouter, status, Depends, HTTPException
from fastapi.responses import StreamingResponse
from api.v1.schemas.ai import AIRequest, ThreadSummary, ThreadResponse, MessageResponse
from api.v1.services.user import user_service
from api.v1.services.chat_message_service import chat_message_service
from api.v1.services.conversation_service import conversation_service
from api.v1.models.user import User
from api.v1.utils.helpers import stream_agent_response
from api.v1.utils.dependencies import get_db

ai = APIRouter(prefix="/ai", tags=["AI"])


@ai.post("/chat", status_code=status.HTTP_200_OK)
async def chat(
    request: AIRequest,
    user: User = Depends(user_service.get_current_user),
) -> StreamingResponse:
    return StreamingResponse(
        stream_agent_response(request.message, request.thread_id, str(user.id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@ai.get("/threads", status_code=status.HTTP_200_OK)
async def get_threads(
    user: User = Depends(user_service.get_current_user),
    limit: int = 50,
) -> List[ThreadSummary]:
    """
    Get chat history (list of threads with titles).

    Returns a list of conversation threads for the authenticated user,
    ordered by most recent first.
    """
    db = next(get_db())
    try:
        conversations = conversation_service.get_user_conversations(
            user_id=str(user.id), db=db, limit=limit
        )

        return [
            ThreadSummary(
                thread_id=conv.thread_id,
                title=conv.title or "New Conversation",
                created_at=conv.created_at,
            )
            for conv in conversations
        ]
    finally:
        db.close()


@ai.get("/threads/{thread_id}", status_code=status.HTTP_200_OK)
async def get_thread_conversation(
    thread_id: str,
    user: User = Depends(user_service.get_current_user),
) -> ThreadResponse:
    """
    Get the full conversation for a specific thread.

    Returns all messages in the thread ordered chronologically.
    """
    db = next(get_db())
    try:
        # Get conversation by thread_id
        conversation = conversation_service.get_conversation_by_thread_id(
            user_id=str(user.id), thread_id=thread_id, db=db
        )

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Thread not found or you don't have access to it",
            )

        # Get messages for this conversation
        messages = chat_message_service.get_conversation_messages(
            conversation_id=conversation.id, user_id=str(user.id), db=db
        )

        return ThreadResponse(
            thread_id=thread_id,
            title=conversation.title or "New Conversation",
            messages=[MessageResponse(**msg.to_dict()) for msg in messages],
        )
    finally:
        db.close()
