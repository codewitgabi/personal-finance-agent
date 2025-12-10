from fastapi import APIRouter, status, Depends
from fastapi.responses import StreamingResponse
from api.v1.schemas.ai import AIRequest
from api.v1.services.user import user_service
from api.v1.models.user import User
from api.v1.utils.helpers import stream_agent_response

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
