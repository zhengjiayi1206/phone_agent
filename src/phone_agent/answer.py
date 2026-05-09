from __future__ import annotations

from phone_agent.config import debug_log, make_client
from phone_agent.llm import chat_text
from phone_agent.types import AgentState


class AnswerBuilder:
    def answer(self, state: AgentState) -> AgentState:
        debug_log("enter", node="answer")
        problem = state["problem"].problem
        decision = state["decision"]

        if not decision.need_plan:
            final = self._direct_answer(problem)
            debug_log("answer", mode="direct", chars=len(final))
            return {**state, "final": final}

        final = self._loop_answer(state, problem)
        debug_log("answer", mode="loop", chars=len(final))
        return {**state, "final": final}

    def _direct_answer(self, problem: str) -> str:
        client = make_client()
        direct = chat_text(
            client,
            [
                {"role": "system", "content": "You answer directly and concisely."},
                {
                    "role": "user",
                    "content": f"""/no_think
这个任务不需要操作手机，请直接回答。

问题：
{problem}
""",
                },
            ],
        )
        return f"不需要操作手机。\n问题：{problem}\n回答：{direct.strip()}"

    def _loop_answer(self, state: AgentState, problem: str) -> str:
        action_decision = state.get("action_decision")
        lines = [
            "执行结束。",
            f"目标：{problem}",
            f"是否完成：{bool(action_decision.done) if action_decision else False}",
            f"循环次数：{state.get('loop_count', 0)}/{state.get('max_loops', 5)}",
            "",
            "循环记录:",
        ]
        for result in state.get("loop_results", []):
            lines.append(f"{result.iteration}. observation={result.observation}")
            lines.append(f"   action={result.action}")
            lines.append(f"   output={result.output}")

        if action_decision:
            lines.append("")
            lines.append("最后观察:")
            lines.append(action_decision.observation)
            lines.append("最后判断:")
            lines.append(action_decision.reason)

        return "\n".join(lines)
