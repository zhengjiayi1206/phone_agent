from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


@dataclass(frozen=True)
class ClarifiedProblem:
    original_input: str
    problem: str


@dataclass(frozen=True)
class PlanDecision:
    need_plan: bool
    reason: str


@dataclass(frozen=True)
class PlanStep:
    index: int
    title: str
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionPlan:
    goal: str
    need_adb: bool
    steps: list[PlanStep]


@dataclass(frozen=True)
class PlanStepResult:
    step_index: int
    title: str
    output: str


@dataclass(frozen=True)
class ActionDecision:
    done: bool
    observation: str
    reason: str
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LoopResult:
    iteration: int
    observation: str
    action: str
    output: str


class AgentState(TypedDict, total=False):
    user_input: str
    problem: ClarifiedProblem
    decision: PlanDecision
    plan: ExecutionPlan
    current_step_index: int
    step_results: list[PlanStepResult]
    loop_count: int
    max_loops: int
    action_decision: ActionDecision
    loop_results: list[LoopResult]
    done: bool
    final: str
