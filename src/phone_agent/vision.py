from __future__ import annotations

from pathlib import Path
from typing import Any

from phone_agent.adb_tools import DEFAULT_SCREENSHOT_PATH, image_data_url
from phone_agent.config import debug_json, debug_log, debug_verbose, make_client, no_think_extra_body, vision_model
from phone_agent.llm import parse_json_object
from phone_agent.screen import NORMALIZED_SCREENSHOT_PATH, current_screen_scale
from phone_agent.tools import describe_phone_tools, run_ui_phone_tool
from phone_agent.types import ActionDecision, AgentState, LoopResult


class VisionDecisionMaker:
    def __init__(self) -> None:
        self.coordinate_resolver = CoordinateResolver()

    def perceive_and_decide(self, state: AgentState) -> AgentState:
        iteration = state.get("loop_count", 0) + 1
        debug_log(
            "enter",
            node="perceive_and_decide",
            iteration=iteration,
            previous_actions=len(state.get("loop_results", [])),
            max_loops=state.get("max_loops", 5),
        )

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
        decision = self.coordinate_resolver.resolve_if_needed(state, iteration, screenshot_path, decision)
        debug_json(
            "llm.action",
            {
                "iteration": iteration,
                "done": decision.done,
                "tool": decision.tool,
                "arguments": decision.arguments,
                "target": decision.target,
                "observation": decision.observation,
                "reason": decision.reason,
            },
        )
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
        prompt = self._build_prompt(state, iteration, previous_results, screenshot_output)
        debug_log(
            "vision.start",
            iteration=iteration,
            model=model,
            prompt_chars=len(prompt),
            history_chars=len(previous_results),
            screenshot=str(screenshot_path),
        )
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
                            "text": prompt,
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

你必须把“之前执行记录”当作当前上下文记忆：
- 不要重复进入已经判断过“不包含目标”的文件夹、页面或方向。
- 如果上一轮 observation/reason 说明走错了，下一步应先返回或换方向。
- 你的 reason 必须引用相关历史，例如“上一轮进入旅游与商务文件夹未找到淘宝，所以本轮先返回”。

可用工具：
{describe_phone_tools()}

规则：
- 必须像人一样通过界面操作。
- 禁止使用包名、pm list packages、monkey、am start、dumpsys 等系统捷径。
- 坐标全部基于 1000x1000 图片：左上角 (0,0)，右下角 (1000,1000)。
- 如果任务已经完成，输出 done=true，tool=null。
- 如果没有完成，只输出一个下一步 action。
- 如果下一步是 tap 或 swipe，主任务只需要描述 target，不要自己猜精确坐标；坐标会由单独的定位模型获取。
- 打开应用类任务：优先回到桌面/应用列表，通过截图寻找图标；看不到就滑动或使用界面上的搜索入口。

只输出 JSON，不要 Markdown。
格式：
{{
  "done": false,
  "observation": "当前界面观察",
  "reason": "为什么这样判断/操作",
  "action": {{
    "tool": "tap",
    "target": "要点击的页面组件，例如淘宝图标、搜索框、返回按钮",
    "arguments": {{}}
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
        debug_json("llm.parsed", data)
        action = data.get("action") if isinstance(data.get("action"), dict) else {}
        tool = normalize_tool_name(action.get("tool"))
        arguments = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
        target = str(action.get("target") or data.get("target") or "")
        return ActionDecision(
            done=bool(data.get("done")),
            observation=str(data.get("observation") or ""),
            reason=str(data.get("reason") or ""),
            tool=tool,
            arguments=arguments,
            target=target,
        )


class CoordinateResolver:
    COORDINATE_TOOLS = {"tap", "swipe"}

    def resolve_if_needed(
        self,
        state: AgentState,
        iteration: int,
        screenshot_path: Path,
        decision: ActionDecision,
    ) -> ActionDecision:
        if decision.done or decision.tool not in self.COORDINATE_TOOLS:
            return decision

        debug_log(
            "coordinate.resolve.start",
            iteration=iteration,
            tool=decision.tool,
            target=decision.target,
            existing_args=decision.arguments,
        )
        raw = self._ask_coordinate_model(state, iteration, screenshot_path, decision)
        debug_verbose("llm.raw", node="coordinate_resolver", iteration=iteration, raw=raw)
        data = parse_json_object(raw)
        debug_json("coordinate.parsed", data)
        arguments = self._arguments_from_coordinate_response(decision.tool, data)
        debug_json(
            "coordinate.resolved",
            {
                "iteration": iteration,
                "tool": decision.tool,
                "target": decision.target,
                "arguments": arguments,
            },
        )
        return ActionDecision(
            done=decision.done,
            observation=decision.observation,
            reason=decision.reason,
            tool=decision.tool,
            arguments=arguments,
            target=decision.target,
        )

    def _ask_coordinate_model(
        self,
        state: AgentState,
        iteration: int,
        screenshot_path: Path,
        decision: ActionDecision,
    ) -> str:
        client = make_client()
        model = vision_model()
        prompt = self._build_coordinate_prompt(state, iteration, decision)
        debug_log(
            "coordinate.vision.start",
            iteration=iteration,
            model=model,
            tool=decision.tool,
            prompt_chars=len(prompt),
            screenshot=str(screenshot_path),
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You locate UI coordinates on a 1000x1000 Android screenshot. You only return valid JSON.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
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

    def _build_coordinate_prompt(
        self,
        state: AgentState,
        iteration: int,
        decision: ActionDecision,
    ) -> str:
        previous_results = format_loop_results(state.get("loop_results", []))
        if decision.tool == "tap":
            schema = """{
  "element": [x, y],
  "confidence": 0.0,
  "reason": "为什么这个坐标准确"
}"""
        else:
            schema = """{
  "start": [x1, y1],
  "end": [x2, y2],
  "duration_ms": 300,
  "confidence": 0.0,
  "reason": "为什么这个滑动坐标准确"
}"""

        return f"""/no_think
你看到的是 1000x1000 标准化手机截图。你的唯一任务是为下一步操作提供精确坐标。

总体任务：
{state["problem"].problem}

当前第 {iteration} 轮。

当前界面观察：
{decision.observation}

需要执行的工具：
{decision.tool}

要定位的目标：
{decision.target or decision.reason}

历史上下文：
{previous_results or "无"}

坐标规则：
- 左上角是 (0,0)，右下角是 (1000,1000)。
- 点击坐标要落在目标组件中心区域，不要落在边缘。
- 如果目标是应用图标，点图标主体中心，不要点文字标签。
- 如果目标是返回/关闭按钮，点按钮视觉中心。
- 如果是滑动，start/end 要避开底部手势区和顶部状态栏。

只输出 JSON，不要 Markdown。
格式：
{schema}
"""

    def _arguments_from_coordinate_response(self, tool: str, data: dict[str, Any]) -> dict[str, Any]:
        if tool == "tap":
            element = data.get("element") or data.get("point") or data.get("coordinate")
            if not isinstance(element, list | tuple) or len(element) < 2:
                raise ValueError(f"Coordinate resolver did not return element: {data}")
            return {"element": [int(element[0]), int(element[1])]}

        start = data.get("start")
        end = data.get("end")
        if not isinstance(start, list | tuple) or len(start) < 2:
            raise ValueError(f"Coordinate resolver did not return start: {data}")
        if not isinstance(end, list | tuple) or len(end) < 2:
            raise ValueError(f"Coordinate resolver did not return end: {data}")
        return {
            "start": [int(start[0]), int(start[1])],
            "end": [int(end[0]), int(end[1])],
            "duration_ms": int(data.get("duration_ms") or 300),
        }


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
        lines.extend(
            [
                f"第 {result.iteration} 轮：",
                f"- observation: {result.observation}",
                f"- reason: {result.reason}",
                f"- action: {result.action}",
                f"- arguments: {result.arguments}",
                f"- output: {result.output}",
            ]
        )
    return "\n".join(lines)
