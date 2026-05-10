from __future__ import annotations

from phone_agent.config import debug_json, debug_log, debug_verbose, make_client
from phone_agent.llm import chat_text, parse_json_object
from phone_agent.types import AgentState, ClarifiedProblem, ProblemDecision


class ProblemInterpreter:
    def clarify(self, state: AgentState) -> AgentState:
        debug_log("enter", node="clarify_problem")
        client = make_client()
        raw = chat_text(
            client,
            [
                {"role": "system", "content": "You only return valid JSON."},
                {
                    "role": "user",
                    "content": f"""/no_think
请明确用户的问题，把口语化输入改写成一个清晰任务，并判断是否需要操作手机界面。

需要操作手机的情况：
- 需要查看手机当前界面
- 需要打开应用、点击、滑动、返回、输入
- 需要检查手机上是否存在某个图标或页面状态

不需要操作手机的情况：
- 普通问答
- 可以直接用已有信息回答

只输出 JSON，不要 Markdown。
格式：
{{
  "problem": "清晰的问题描述",
  "need_phone_loop": true,
  "reason": "是否需要操作手机的简短原因"
}}

用户输入：
{state["user_input"]}
""",
                },
            ],
        )
        debug_verbose("llm.raw", node="clarify_problem", raw=raw)
        data = parse_json_object(raw)
        debug_json("problem.parsed", data)
        problem = ClarifiedProblem(
            original_input=state["user_input"],
            problem=str(data.get("problem") or state["user_input"]),
        )
        decision = ProblemDecision(
            need_phone_loop=bool(data.get("need_phone_loop")),
            reason=str(data.get("reason") or ""),
        )
        debug_log("problem", text=problem.problem)
        debug_log("decision", need_phone_loop=decision.need_phone_loop, reason=decision.reason)
        return {**state, "problem": problem, "decision": decision}
