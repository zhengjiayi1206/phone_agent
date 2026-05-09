from __future__ import annotations

from typing import Literal

from phone_agent.config import debug_log
from phone_agent.tools import run_ui_phone_tool
from phone_agent.types import AgentState, LoopResult


class PhoneLoopController:
    def __init__(self, max_loops: int = 5) -> None:
        self.max_loops = max_loops

    def init_loop(self, state: AgentState) -> AgentState:
        debug_log("enter", node="init_loop", max_loops=self.max_loops)
        return {
            **state,
            "loop_count": 0,
            "max_loops": self.max_loops,
            "loop_results": [],
            "done": False,
        }

    def route_after_decision(self, state: AgentState) -> Literal["init_loop", "answer"]:
        route = "init_loop" if state["decision"].need_plan else "answer"
        debug_log("route", path=f"decide_plan -> {route}")
        return route

    def route_after_perception(self, state: AgentState) -> Literal["execute_action", "answer"]:
        decision = state["action_decision"]
        if decision.done:
            route = "answer"
            debug_log("task.stop", reason="done", iteration=state.get("loop_count", 0))
        elif state.get("loop_count", 0) >= state.get("max_loops", self.max_loops):
            route = "answer"
            debug_log("task.stop", reason="max_loops", iteration=state.get("loop_count", 0))
        elif decision.tool:
            route = "execute_action"
        else:
            route = "answer"
            debug_log("task.stop", reason="no_action", iteration=state.get("loop_count", 0))
        debug_log(
            "route",
            path=f"perceive_and_decide -> {route}",
            iteration=state.get("loop_count", 0),
            done=decision.done,
            tool=decision.tool or "none",
        )
        return route

    def execute_action(self, state: AgentState) -> AgentState:
        decision = state["action_decision"]
        iteration = state.get("loop_count", 0)
        debug_log(
            "enter",
            node="execute_action",
            iteration=iteration,
            tool=decision.tool or "none",
            arguments=decision.arguments,
        )

        if not decision.tool:
            output = "No action selected."
        else:
            try:
                output = run_ui_phone_tool(decision.tool, decision.arguments)
            except Exception as exc:
                output = f"Action failed: {type(exc).__name__}: {exc}"
                debug_log("action.error", iteration=iteration, error=f"{type(exc).__name__}: {exc}")

        result = LoopResult(
            iteration=iteration,
            observation=decision.observation,
            action=decision.tool or "none",
            output=output,
        )
        results = [*state.get("loop_results", []), result]
        debug_log("action.done", iteration=iteration, action=decision.tool or "none", output=output)
        return {**state, "loop_results": results}

    def route_after_action(self, state: AgentState) -> Literal["perceive_and_decide", "answer"]:
        if state.get("loop_count", 0) >= state.get("max_loops", self.max_loops):
            route = "answer"
        else:
            route = "perceive_and_decide"
        debug_log("route", path=f"execute_action -> {route}", iteration=state.get("loop_count", 0))
        return route
