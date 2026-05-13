from __future__ import annotations

from dataclasses import asdict

from phone_agent.config import debug_json, debug_log
from phone_agent.model import PhoneModel
from phone_agent.session import PhoneSession
from phone_agent.tools import ToolRegistry, build_tool_registry
from phone_agent.types import Message, ToolResult, TurnSummary


class PhoneRuntime:
    def __init__(
        self,
        model: PhoneModel | None = None,
        tools: ToolRegistry | None = None,
        max_iterations: int = 20,
    ) -> None:
        self.model = model or PhoneModel()
        self.tools = tools or build_tool_registry()
        self.max_iterations = max_iterations

    def run_turn(self, user_input: str) -> TurnSummary:
        debug_log("runtime.start", task=user_input, max_iterations=self.max_iterations)
        session = PhoneSession.start(user_input)

        for iteration in range(1, self.max_iterations + 1):
            debug_log("runtime.iteration", iteration=iteration)

            screenshot_output = self._execute_tool("screenshot", {}, session)
            debug_log("runtime.screenshot", iteration=iteration, output=screenshot_output.output)
            if screenshot_output.is_error:
                session.done = False
                session.answer = f"截图失败，无法继续观察手机界面：{screenshot_output.output}"
                debug_log("runtime.stop", reason="screenshot_error", iteration=iteration)
                break

            decision = self.model.decide(session, self.tools, iteration, self.max_iterations)
            session.add_message(
                Message(
                    role="assistant",
                    content=decision.answer or decision.reason,
                    data={
                        "done": decision.done,
                        "observation": decision.observation,
                        "reason": decision.reason,
                        "tool_calls": [asdict(call) for call in decision.tool_calls],
                    },
                )
            )
            session.remember(
                "assistant_decision",
                {
                    "iteration": iteration,
                    "done": decision.done,
                    "observation": decision.observation,
                    "reason": decision.reason,
                    "tool_calls": [asdict(call) for call in decision.tool_calls],
                },
            )

            if decision.done or not decision.tool_calls:
                session.done = True
                session.answer = decision.answer or decision.observation or decision.reason
                debug_log("runtime.stop", reason="done" if decision.done else "no_tool_calls", iteration=iteration)
                break

            for tool_call in decision.tool_calls:
                self._execute_tool(tool_call.name, tool_call.arguments, session)
        else:
            session.answer = "达到最大循环次数，任务未确认完成。"
            debug_log("runtime.stop", reason="max_iterations", iteration=self.max_iterations)

        summary = TurnSummary(
            task=session.task,
            done=session.done,
            answer=session.answer,
            iterations=min(len([m for m in session.messages if m.role == "assistant"]), self.max_iterations),
            messages=session.messages,
            tool_results=session.tool_results,
            session_path=str(session.session_path),
            memory_path=str(session.memory_path),
        )
        debug_json(
            "runtime.summary",
            {
                "done": summary.done,
                "iterations": summary.iterations,
                "tool_results": len(summary.tool_results),
                "session_path": summary.session_path,
                "memory_path": summary.memory_path,
            },
        )
        return summary

    def _execute_tool(self, name: str, arguments: dict, session: PhoneSession) -> ToolResult:
        debug_json("tool.call", {"name": name, "arguments": arguments})
        try:
            output = self.tools.execute(name, arguments)
            result = ToolResult(name=name, arguments=arguments, output=output, is_error=False)
        except Exception as exc:
            result = ToolResult(
                name=name,
                arguments=arguments,
                output=f"{type(exc).__name__}: {exc}",
                is_error=True,
            )
            debug_log("tool.error", tool=name, error=result.output)

        session.add_tool_result(result)
        session.remember(
            "tool_result",
            {
                "tool": result.name,
                "arguments": result.arguments,
                "output": result.output,
                "is_error": result.is_error,
            },
        )
        return result


def format_summary(summary: TurnSummary) -> str:
    lines = [
        "执行结束。",
        f"任务：{summary.task}",
        f"是否完成：{summary.done}",
        f"循环次数：{summary.iterations}",
        f"Session：{summary.session_path}",
        f"Memory：{summary.memory_path}",
        "",
        "最终回答：",
        summary.answer or "(无)",
        "",
        "工具调用：",
    ]
    for index, result in enumerate(summary.tool_results, start=1):
        status = "error" if result.is_error else "ok"
        lines.append(f"{index}. {result.name} status={status} args={result.arguments}")
        lines.append(f"   {result.output}")
    return "\n".join(lines)


def run_phone_plan(task: str) -> str:
    summary = PhoneRuntime().run_turn(task)
    return format_summary(summary)
