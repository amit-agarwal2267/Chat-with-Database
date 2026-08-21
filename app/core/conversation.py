import uuid
from dataclasses import dataclass, field
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage
from app.logger import get_logger

logger = get_logger(__name__)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Message:
    id: str
    role: str
    content: str
    data: list[dict] | None = None


@dataclass
class Conversation:
    id: str
    title: str = "New conversation"
    messages: list[Message] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def add(self, role: str, content: str, data=None) -> Message:
        msg = Message(id=new_id(), role=role, content=content, data=data)
        self.messages.append(msg)
        if role == "user" and self.title == "New conversation":
            self.title = content[:40] + ("…" if len(content) > 40 else "")
        return msg

    def to_lc_messages(self):
        return [
            HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
            for m in self.messages
        ]

    def branch_from(self, message_id: str) -> int | None:
        """
        Drop the message with message_id and everything after it, effectively
        starting a new branch from that point. Returns the truncation index.
        """
        idx = next((i for i, m in enumerate(self.messages) if m.id == message_id), None)
        if idx is None:
            logger.warning("branch_from: message_id %s not found in conversation %s", message_id, self.id)
            return None
        removed = len(self.messages) - idx
        self.messages = self.messages[:idx]
        logger.info("Branched conversation %s at message %s — dropped %d message(s)", self.id, message_id, removed)
        return idx