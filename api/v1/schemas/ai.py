from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class AIRequest(BaseModel):
    message: str = Field(
        ..., min_length=1, description="User message to the AI assistant"
    )
    thread_id: str = Field(
        default="", description="Optional thread ID for conversation continuity"
    )


class ThreadSummary(BaseModel):
    thread_id: str = Field(..., description="Thread identifier")
    title: str = Field(..., description="Thread title")
    created_at: Optional[datetime] = Field(
        None, description="Thread creation timestamp"
    )


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    parent_message_id: Optional[str] = None
    role: str
    content: str
    model: Optional[str] = None
    temperature: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    status: str
    finish_reason: Optional[str] = None
    latency_ms: Optional[int] = None
    metadata: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ThreadResponse(BaseModel):
    thread_id: str
    title: Optional[str] = None
    messages: List[MessageResponse]
