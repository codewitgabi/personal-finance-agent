from pydantic import BaseModel, Field


class AIRequest(BaseModel):
    message: str = Field(
        ..., min_length=1, description="User message to the AI assistant"
    )
    thread_id: str = Field(
        default="", description="Optional thread ID for conversation continuity"
    )
