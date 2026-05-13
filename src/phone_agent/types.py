from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Role = Literal["user", "assistant", "tool"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str
    name: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True)
class AssistantDecision:
    done: bool
    answer: str
    observation: str
    reason: str
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class ToolResult:
    name: str
    arguments: dict[str, Any]
    output: str
    is_error: bool = False


@dataclass(frozen=True)
class TurnSummary:
    task: str
    done: bool
    answer: str
    iterations: int
    messages: list[Message]
    tool_results: list[ToolResult]
    session_path: str
    memory_path: str
