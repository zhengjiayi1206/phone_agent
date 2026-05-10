from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


@dataclass(frozen=True)
class ClarifiedProblem:
    original_input: str
    problem: str


@dataclass(frozen=True)
class ProblemDecision:
    need_phone_loop: bool
    reason: str


@dataclass(frozen=True)
class ActionDecision:
    done: bool
    observation: str
    reason: str
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    target: str = ""


@dataclass(frozen=True)
class LoopResult:
    iteration: int
    observation: str
    reason: str
    action: str
    output: str
    arguments: dict[str, Any] = field(default_factory=dict)


class AgentState(TypedDict, total=False):
    user_input: str
    problem: ClarifiedProblem
    decision: ProblemDecision
    loop_count: int
    max_loops: int
    action_decision: ActionDecision
    loop_results: list[LoopResult]
    done: bool
    final: str
