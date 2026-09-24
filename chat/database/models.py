"""
models.py
---------
SQLAlchemy models for the Chat feature's persistent memory.

Two tables:

  conversations  — one row per chat thread. Holds the auto-generated
                   title, and the ROLLING SUMMARY used to compress old
                   history (see memory.py for how this is maintained).

  messages       — one row per user/assistant turn. Full audit trail,
                   never deleted or overwritten — this is what powers
                   "scroll up and see the whole conversation" in the UI.
                   The sliding-window/summarization logic in memory.py
                   only affects what gets SENT to the LLM on a given
                   turn, never what's stored here.

Design note: `conversations.summary` + `conversations.summarized_through`
together let memory.py answer "what's already been folded into the
summary, and what's still raw and needs to be re-summarized?" without
having to store the summary as a fake message row mixed in with real
user/assistant turns.
"""

import uuid
from sqlalchemy import Column, String, Text, TIMESTAMP, Boolean, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    title = Column(String, nullable=True)          # auto-generated after first turn
    is_archived = Column(Boolean, default=False, nullable=False)

    # Rolling summary of everything older than the sliding window.
    # NULL until the conversation first exceeds the message-count
    # threshold defined in memory.py.
    summary = Column(Text, nullable=True)

    # The created_at timestamp of the last message folded into `summary`.
    # Messages with created_at <= this value are considered "already
    # summarized" and are excluded from the raw sliding window.
    summarized_through = Column(TIMESTAMP(timezone=True), nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    __table_args__ = (
        # Powers the sidebar's "most recent conversations first" query.
        Index("ix_conversations_user_updated", "user_id", "updated_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    role = Column(String, nullable=False)   # "user" | "assistant"
    content = Column(Text, nullable=False)

    # Optional audit trail of which tools were called to produce this
    # message (assistant turns only). Never replayed back to the model
    # as conversation history — only the clean text in `content` is.
    tool_calls = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        # Powers the one query that matters most: "give me all messages
        # in this conversation, in order."
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )
