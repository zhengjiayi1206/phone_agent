from __future__ import annotations

from pathlib import Path
from typing import Any

from phone_agent.adb_tools import DEFAULT_SCREENSHOT_PATH, image_data_url
from phone_agent.config import debug_log, debug_verbose, make_client, no_think_extra_body, vision_model
from phone_agent.llm import parse_json_object
from phone_agent.screen import NORMALIZED_SCREENSHOT_PATH, current_screen_scale
from phone_agent.tools import describe_phone_tools, run_ui_phone_tool
from phone_agent.types import ActionDecision, AgentState, LoopResult


class VisionDecisionMaker:
    def perceive_and_decide(self, state: AgentState) -> AgentState:
        iteration = state.get("loop_count", 0) + 1
        debug_log("enter", node="perceive_and_decide", iteration=iteration)

        screenshot_output = self._take_screenshot()
        screenshot_path = NORMALIZED_SCREENSHOT_PATH
        real_screenshot_path = DEFAULT_SCREENSHOT_PATH
        if not screenshot_path.exists():
            raise RuntimeError(f"Normalized screenshot file not found: {screenshot_path}")

        scale = current_screen_scale(real_screenshot_path)
        debug_log(
            "perception.screenshot",
            iteration=iteration,
            source=f"{scale.source_width}x{scale.source_height}",
            normalized="1000x1000",
            path=str(screenshot_path),
        )

        raw = self._ask_vision_model(state, iteration, screenshot_output, screenshot_path)
        debug_verbose("llm.raw", node="perceive_and_decide", iteration=iteration, raw=raw)
        decision = self._parse_action_decision(raw)
        debug_log(
            "loop.decision",
            iteration=iteration,
            done=decision.done,
            tool=decision.tool or "none",
            observation=decision.observation,
            reason=decision.reason,
        )
        if decision.done:
            debug_log(
                "task.complete",
                iteration=iteration,
                task=state["problem"].problem,
                evidence=decision.observation,
                reason=decision.reason,
            )
        return {
            **state,
            "loop_count": iteration,
            "action_decision": decision,
            "done": decision.done,
        }

    def _take_screenshot(self) -> str:
        return run_ui_phone_tool("screenshot", {})

    def _ask_vision_model(
        self,
        state: AgentState,
        iteration: int,
        screenshot_output: str,
        screenshot_path: Path,
    ) -> str:
        previous_results = format_loop_results(state.get("loop_results", []))
        client = make_client()
        model = vision_model()
        debug_log("vision.start", iteration=iteration, model=model)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a human-like Android UI operation agent. You only return valid JSON.",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": self._build_prompt(state, iteration, previous_results, screenshot_output),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url(Path(screenshot_path))},
                        },
                    ],
                },
            ],
            temperature=0,
            extra_body=no_think_extra_body(),
        )
        return response.choices[0].message.content or ""

    def _build_prompt(
        self,
        state: AgentState,
        iteration: int,
        previous_results: str,
        screenshot_output: str,
    ) -> str:
        return f"""/no_think
你正在通过手机界面完成任务。你看到的是 1000x1000 标准化截图。

任务：
{state["problem"].problem}

当前是第 {iteration} 轮，最多 {state.get("max_loops", 5)} 轮。

之前执行记录：
{previous_results or "无"}

可用工具：
{describe_phone_tools()}

规则：
- 必须像人一样通过界面操作。
- 禁止使用包名、pm list packages、monkey、am start、dumpsys 等系统捷径。
- 坐标全部基于 1000x1000 图片：左上角 (0,0)，右下角 (1000,1000)。
- 如果任务已经完成，输出 done=true，tool=null。
- 如果没有完成，只输出一个下一步 action。
- 打开应用类任务：优先回到桌面/应用列表，通过截图寻找图标；看不到就滑动或使用界面上的搜索入口。

只输出 JSON，不要 Markdown。
格式：
{{
  "done": false,
  "observation": "当前界面观察",
  "reason": "为什么这样判断/操作",
  "action": {{
    "tool": "tap",
    "arguments": {{"element": [500, 500]}}
  }}
}}

如果完成：
{{
  "done": true,
  "observation": "已经完成的证据",
  "reason": "为什么认为完成",
  "action": null
}}

截图工具刚刚执行结果：
{screenshot_output}
"""

    def _parse_action_decision(self, raw: str) -> ActionDecision:
        data = parse_json_object(raw)
        action = data.get("action") if isinstance(data.get("action"), dict) else {}
        tool = normalize_tool_name(action.get("tool"))
        arguments = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
        return ActionDecision(
            done=bool(data.get("done")),
            observation=str(data.get("observation") or ""),
            reason=str(data.get("reason") or ""),
            tool=tool,
            arguments=arguments,
        )


def normalize_tool_name(value: Any) -> str | None:
    if value is None:
        return None
    tool = str(value).strip()
    if not tool or tool.lower() in {"none", "null", "no_tool"}:
        return None
    return tool


def format_loop_results(results: list[LoopResult]) -> str:
    lines = []
    for result in results:
        lines.append(
            f"{result.iteration}. observation={result.observation}; "
            f"action={result.action}; output={result.output}"
        )
    return "\n".join(lines)
