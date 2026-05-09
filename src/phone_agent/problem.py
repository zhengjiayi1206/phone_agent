from __future__ import annotations

from phone_agent.config import debug_log, debug_verbose, make_client
from phone_agent.llm import chat_text, parse_json_object
from phone_agent.types import AgentState, ClarifiedProblem, PlanDecision


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
请明确用户的问题，把口语化输入改写成一个清晰任务。

只输出 JSON，不要 Markdown。
格式：
{{
  "problem": "清晰的问题描述"
}}

用户输入：
{state["user_input"]}
""",
                },
            ],
        )
        debug_verbose("llm.raw", node="clarify_problem", raw=raw)
        data = parse_json_object(raw)
        problem = ClarifiedProblem(
            original_input=state["user_input"],
            problem=str(data.get("problem") or state["user_input"]),
        )
        debug_log("problem", text=problem.problem)
        return {**state, "problem": problem}

    def decide_phone_loop(self, state: AgentState) -> AgentState:
        debug_log("enter", node="decide_plan")
        client = make_client()
        problem = state["problem"].problem
        raw = chat_text(
            client,
            [
                {"role": "system", "content": "You only return valid JSON."},
                {
                    "role": "user",
                    "content": f"""/no_think
判断这个任务是否需要操作手机界面。

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
  "need_plan": true,
  "reason": "简短原因"
}}

任务：
{problem}
""",
                },
            ],
        )
        debug_verbose("llm.raw", node="decide_plan", raw=raw)
        data = parse_json_object(raw)
        decision = PlanDecision(
            need_plan=bool(data.get("need_plan")),
            reason=str(data.get("reason") or ""),
        )
        debug_log("decision", need_phone_loop=decision.need_plan, reason=decision.reason)
        return {**state, "decision": decision}
