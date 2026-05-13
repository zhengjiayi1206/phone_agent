from __future__ import annotations

import operator
from typing import Annotated, Any, NotRequired, TypedDict


class PlanStep(TypedDict):
    id: str
    title: str
    objective: str
    children: NotRequired[list["PlanStep"]]


class WorkItem(TypedDict):
    id: str
    path: str
    title: str
    objective: str
    parent_path: str | None


class StepResult(TypedDict):
    id: str
    path: str
    title: str
    output: str


class PlannerState(TypedDict, total=False):
    goal: str
    plan: dict[str, list[PlanStep]]
    stack: list[WorkItem]
    current: WorkItem
    results: Annotated[list[StepResult], operator.add]
    iterations: int
    max_iterations: int
    final: str


def normalize_plan(value: dict[str, Any]) -> dict[str, list[PlanStep]]:
    steps_value = value.get("steps")
    if not isinstance(steps_value, list) or not steps_value:
        raise ValueError("Plan JSON must contain a non-empty 'steps' list.")

    return {
        "steps": [
            _normalize_step(step_value, fallback_id=f"main-{index}")
            for index, step_value in enumerate(steps_value, start=1)
        ]
    }


def flatten_plan(plan: dict[str, list[PlanStep]]) -> list[WorkItem]:
    return _flatten_steps(plan["steps"])


def format_plan_tree(steps: list[PlanStep], indent: int = 0) -> str:
    lines: list[str] = []
    prefix = "  " * indent
    for step in steps:
        lines.append(f"{prefix}- {step['id']} {step['title']}: {step['objective']}")
        children = step.get("children", [])
        if children:
            lines.append(format_plan_tree(children, indent + 1))
    return "\n".join(lines)


def _normalize_step(value: Any, fallback_id: str) -> PlanStep:
    if not isinstance(value, dict):
        raise ValueError(f"Plan step must be an object: {value!r}")

    children_value = value.get("children", [])
    if children_value is None:
        children_value = []
    if not isinstance(children_value, list):
        raise ValueError(f"Plan step children must be a list: {value!r}")

    step: PlanStep = {
        "id": _text(value.get("id"), fallback_id),
        "title": _text(value.get("title"), fallback_id),
        "objective": _text(
            value.get("objective"),
            _text(value.get("title"), fallback_id),
        ),
    }
    children = [
        _normalize_step(child_value, fallback_id=f"{step['id']}.{index}")
        for index, child_value in enumerate(children_value, start=1)
    ]
    if children:
        step["children"] = children
    return step


def _flatten_steps(
    steps: list[PlanStep],
    prefix: str = "",
    parent_path: str | None = None,
) -> list[WorkItem]:
    items: list[WorkItem] = []
    for index, step in enumerate(steps, start=1):
        path = f"{prefix}{index}"
        items.append(
            {
                "id": step["id"],
                "path": path,
                "title": step["title"],
                "objective": step["objective"],
                "parent_path": parent_path,
            }
        )
        children = step.get("children", [])
        if children:
            items.extend(
                _flatten_steps(children, prefix=f"{path}.", parent_path=path)
            )
    return items


def _text(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback
