from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from phone_agent.types import Message, ToolResult


DEFAULT_STATE_DIR = Path(".phone_agent")
DEFAULT_SESSION_PATH = DEFAULT_STATE_DIR / "session.jsonl"
DEFAULT_MEMORY_PATH = DEFAULT_STATE_DIR / "memory.jsonl"


@dataclass
class PhoneSession:
    task: str
    session_id: str = field(default_factory=lambda: uuid4().hex)
    messages: list[Message] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    done: bool = False
    answer: str = ""
    session_path: Path = DEFAULT_SESSION_PATH
    memory_path: Path = DEFAULT_MEMORY_PATH

    @classmethod
    def start(cls, task: str) -> "PhoneSession":
        session = cls(task=task)
        session.session_path.parent.mkdir(parents=True, exist_ok=True)
        session.add_message(Message(role="user", content=task))
        return session

    def add_message(self, message: Message) -> None:
        self.messages.append(message)
        self.append_jsonl(
            self.session_path,
            {
                "type": "message",
                "session_id": self.session_id,
                "timestamp": timestamp(),
                **asdict(message),
            },
        )

    def add_tool_result(self, result: ToolResult) -> None:
        self.tool_results.append(result)
        self.add_message(
            Message(
                role="tool",
                name=result.name,
                content=result.output,
                data={
                    "arguments": result.arguments,
                    "is_error": result.is_error,
                },
            )
        )

    def remember(self, event: str, payload: dict[str, Any]) -> None:
        self.append_jsonl(
            self.memory_path,
            {
                "event": event,
                "session_id": self.session_id,
                "timestamp": timestamp(),
                **payload,
            },
        )

    def recent_context(self, limit: int = 12) -> str:
        lines = []
        for message in self.messages[-limit:]:
            name = f":{message.name}" if message.name else ""
            lines.append(f"{message.role}{name}: {message.content}")
        return "\n".join(lines) if lines else "无"

    @staticmethod
    def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")
