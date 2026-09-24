import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from chat.chat_agent import chat_turn_stream
from chat.database.memory import get_all_messages, get_user_conversations

from ..deps import get_current_user_id
from ..sse import stream_events

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str
    response_style: str = "balanced"


def _parse_conversation_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid conversation_id: {raw!r}"
        )


@router.get("/conversations")
async def list_conversations(user_id: uuid.UUID = Depends(get_current_user_id)):
    try:
        conversations = await get_user_conversations(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Chat history is unavailable: {e}"
        )

    return [
        {
            "id": str(c.id),
            "title": c.title,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}/messages")
async def list_messages(conversation_id: str):
    parsed = _parse_conversation_id(conversation_id)
    try:
        messages = await get_all_messages(parsed)
    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Chat history is unavailable: {e}"
        )

    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


@router.post("/stream")
async def stream_chat(
    payload: ChatRequest, user_id: uuid.UUID = Depends(get_current_user_id)
):
    conversation_id = (
        _parse_conversation_id(payload.conversation_id)
        if payload.conversation_id
        else None
    )

    return stream_events(
        chat_turn_stream(
            user_id, conversation_id, payload.message, payload.response_style
        )
    )
