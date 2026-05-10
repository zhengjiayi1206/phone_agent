from __future__ import annotations

from typing import Literal

from phone_agent.config import debug_json, debug_log
from phone_agent.tools import run_ui_phone_tool
from phone_agent.types import AgentState, LoopResult


class PhoneLoopController:
    def __init__(self, max_loops: int = 5) -> None:
        self.max_loops = max_loops

    def ensure_started(self, state: AgentState) -> AgentState:
        if "loop_count" in state:
            return state

        debug_log("loop.init", max_loops=self.max_loops)
        return {
            **state,
            "loop_count": 0,
            "max_loops": self.max_loops,
            "loop_results": [],
            "done": False,
        }

    def route_after_problem(self, state: AgentState) -> Literal["phone_loop", "answer"]:
        route = "phone_loop" if state["decision"].need_phone_loop else "answer"
        debug_log("route", path=f"clarify_problem -> {route}")
        return route

    def should_execute_action(self, state: AgentState) -> bool:
        decision = state["action_decision"]
        if decision.done:
            return False
        if not decision.tool:
            return False
        return True

    def execute_action(self, state: AgentState) -> AgentState:
        decision = state["action_decision"]
        iteration = state.get("loop_count", 0)
        debug_log(
            "enter",
            node="execute_action",
            iteration=iteration,
            tool=decision.tool or "none",
        )
        debug_json("action.input", {"iteration": iteration, "tool": decision.tool, "arguments": decision.arguments})
        if decision.target:
            debug_log("action.target", iteration=iteration, target=decision.target)

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
            reason=decision.reason,
            action=decision.tool or "none",
            arguments=decision.arguments,
            output=output,
        )
        results = [*state.get("loop_results", []), result]
        debug_json(
            "action.output",
            {
                "iteration": iteration,
                "action": decision.tool or "none",
                "output": output,
                "result_count": len(results),
            },
        )
        return {**state, "loop_results": results}

    def route_after_loop(self, state: AgentState) -> Literal["phone_loop", "answer"]:
        decision = state.get("action_decision")
        iteration = state.get("loop_count", 0)
        max_loops = state.get("max_loops", self.max_loops)

        if decision and decision.done:
            route = "answer"
            debug_log("task.stop", reason="done", iteration=iteration)
        elif iteration >= max_loops:
            route = "answer"
            debug_log("task.stop", reason="max_loops", iteration=iteration, max_loops=max_loops)
        elif decision and decision.tool:
            route = "phone_loop"
        else:
            route = "answer"
            debug_log("task.stop", reason="no_action", iteration=iteration)

        debug_log(
            "route",
            path=f"phone_loop -> {route}",
            iteration=iteration,
            done=bool(decision.done) if decision else False,
            tool=(decision.tool if decision and decision.tool else "none"),
        )
        return route
