from __future__ import annotations

from typing import Literal, Protocol, cast

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from openai import OpenAI

from phone_agent.config import make_client
from phone_agent.llm import chat_text, parse_json_object
from phone_agent.langgraph_planner.schema import (
    PlannerState,
    PlanStep,
    StepResult,
    WorkItem,
    flatten_plan,
    normalize_plan,
)


class PlanningBackend(Protocol):
    def plan(self, goal: str) -> dict[str, list[PlanStep]]:
        ...

    def execute_step(
        self,
        goal: str,
        step: WorkItem,
        previous_results: list[StepResult],
    ) -> str:
        ...

    def synthesize(
        self,
        goal: str,
        plan: dict[str, list[PlanStep]],
        results: list[StepResult],
    ) -> str:
        ...


class OpenAIPlanningBackend:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.client = client or make_client()

    def plan(self, goal: str) -> dict[str, list[PlanStep]]:
        text = chat_text(
            self.client,
            [
                {
                    "role": "system",
                    "content": (
                        "You are a workflow planner. Decompose the user's goal into "
                        "a tree of main processes, subprocesses, and sub-subprocesses. "
                        "Return only JSON with this shape: "
                        '{"steps":[{"id":"main-1","title":"...","objective":"...",'
                        '"children":[{"id":"sub-1","title":"...","objective":"...",'
                        '"children":[]}]}]}. Keep the plan executable and concise. '
                        "Use the user's language when practical."
                    ),
                },
                {"role": "user", "content": goal},
            ],
        )
        return normalize_plan(parse_json_object(text))

    def execute_step(
        self,
        goal: str,
        step: WorkItem,
        previous_results: list[StepResult],
    ) -> str:
        context = _format_previous_results(previous_results)
        return chat_text(
            self.client,
            [
                {
                    "role": "system",
                    "content": (
                        "You are the executor in a LangGraph planning loop. Execute "
                        "only the current step. Do not rewrite the whole plan. If the "
                        "step requires unavailable external information, state the "
                        "assumption or the next concrete action instead of inventing facts."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Overall goal:\n{goal}\n\n"
                        f"Current step:\n{step}\n\n"
                        f"Previous step results:\n{context}"
                    ),
                },
            ],
        ).strip()

    def synthesize(
        self,
        goal: str,
        plan: dict[str, list[PlanStep]],
        results: list[StepResult],
    ) -> str:
        return chat_text(
            self.client,
            [
                {
                    "role": "system",
                    "content": (
                        "You are the final synthesizer. Produce a compact final answer "
                        "from the workflow plan and executed step results."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Goal:\n{goal}\n\n"
                        f"Plan:\n{plan}\n\n"
                        f"Executed results:\n{results}"
                    ),
                },
            ],
        ).strip()


def build_graph(model: PlanningBackend | None = None):
    backend = model or OpenAIPlanningBackend()
    builder = StateGraph(PlannerState)

    def planner(state: PlannerState) -> PlannerState:
        plan = backend.plan(state["goal"])
        return {
            "plan": plan,
            "stack": flatten_plan(plan),
            "iterations": 0,
            "results": [],
        }

    def scheduler(
        state: PlannerState,
    ) -> Command[Literal["executor", "synthesizer"]]:
        if state.get("iterations", 0) >= state.get("max_iterations", 30):
            return Command(goto="synthesizer")

        stack = state.get("stack", [])
        if not stack:
            return Command(goto="synthesizer")

        current = stack[0]
        rest = stack[1:]
        return Command(update={"current": current, "stack": rest}, goto="executor")

    def executor(state: PlannerState) -> PlannerState:
        current = state["current"]
        output = backend.execute_step(
            goal=state["goal"],
            step=current,
            previous_results=state.get("results", []),
        )
        result: StepResult = {
            "id": current["id"],
            "path": current["path"],
            "title": current["title"],
            "output": output,
        }
        return {
            "results": [result],
            "iterations": state.get("iterations", 0) + 1,
        }

    def synthesizer(state: PlannerState) -> PlannerState:
        final = backend.synthesize(
            goal=state["goal"],
            plan=state.get("plan", {"steps": []}),
            results=state.get("results", []),
        )
        return {"final": final}

    builder.add_node("planner", planner)
    builder.add_node("scheduler", scheduler)
    builder.add_node("executor", executor)
    builder.add_node("synthesizer", synthesizer)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "scheduler")
    builder.add_edge("executor", "scheduler")
    builder.add_edge("synthesizer", END)

    return builder.compile()


def run_planning_loop(
    goal: str,
    max_iterations: int = 30,
    model: PlanningBackend | None = None,
) -> PlannerState:
    graph = build_graph(model)
    recursion_limit = max(25, max_iterations * 3 + 10)
    result = graph.invoke(
        {
            "goal": goal,
            "max_iterations": max_iterations,
        },
        {"recursion_limit": recursion_limit},
    )
    return cast(PlannerState, result)


def _format_previous_results(results: list[StepResult]) -> str:
    if not results:
        return "(none)"
    lines: list[str] = []
    for result in results:
        lines.append(
            f"- {result['path']} {result['title']}: {result['output']}"
        )
    return "\n".join(lines)
