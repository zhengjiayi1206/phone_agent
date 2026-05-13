from __future__ import annotations

from pathlib import Path
from typing import Any

from phone_agent.adb_tools import image_data_url
from phone_agent.config import debug_json, debug_log, debug_verbose, make_client, no_think_extra_body, vision_model
from phone_agent.llm import parse_json_object
from phone_agent.screen import NORMALIZED_SCREENSHOT_PATH
from phone_agent.session import PhoneSession
from phone_agent.tools import ToolRegistry
from phone_agent.types import AssistantDecision, ToolCall


class PhoneModel:
    def decide(
        self,
        session: PhoneSession,
        tools: ToolRegistry,
        iteration: int,
        max_iterations: int,
    ) -> AssistantDecision:
        screenshot_path = NORMALIZED_SCREENSHOT_PATH
        if not screenshot_path.exists():
            raise FileNotFoundError(f"Missing normalized screenshot: {screenshot_path}")

        prompt = self._build_prompt(session, tools, iteration, max_iterations)
        debug_log(
            "model.start",
            iteration=iteration,
            model=vision_model(),
            prompt_chars=len(prompt),
            screenshot=str(screenshot_path),
        )
        raw = self._call_vision(prompt, screenshot_path)
        debug_verbose("model.raw", raw=raw)
        decision = self._parse_decision(raw)
        debug_json(
            "model.decision",
            {
                "done": decision.done,
                "answer": decision.answer,
                "observation": decision.observation,
                "reason": decision.reason,
                "tool_calls": [call.__dict__ for call in decision.tool_calls],
            },
        )
        return decision

    def _call_vision(self, prompt: str, screenshot_path: Path) -> str:
        client = make_client()
        response = client.chat.completions.create(
            model=vision_model(),
            messages=[
                {
                    "role": "system",
                    "content": "You are a phone UI agent. Return only valid JSON.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url(screenshot_path)}},
                    ],
                },
            ],
            temperature=0,
            extra_body=no_think_extra_body(),
        )
        return response.choices[0].message.content or ""

    def _build_prompt(
        self,
        session: PhoneSession,
        tools: ToolRegistry,
        iteration: int,
        max_iterations: int,
    ) -> str:
        return f"""/no_think
你是一个通过 Android 手机界面完成任务的 agent。
你每轮都会看到一张 1000x1000 标准化截图。

当前任务：
{session.task}

当前轮次：
{iteration}/{max_iterations}

上下文历史：
{session.recent_context()}

工具列表：
{tools.describe()}

执行规则：
- 这不是一次性 plan。你每轮只决定下一步；工具结果会进入下一轮上下文。
- 坐标必须基于 1000x1000 截图：左上角 (0,0)，右下角 (1000,1000)。
- 如果任务已经完成，输出 done=true，不要调用工具。
- 如果还没完成，输出一个或多个 tool_calls。
- 如果用户只是问“当前界面是什么/帮我看看界面”，截图识别后就 done=true。
- 禁止使用包名、pm list packages、monkey、am start、dumpsys 等系统捷径。
- 像人一样操作手机：截图、点击、滑动、返回、Home、输入、等待。
- 不要重复进入历史中已经判断失败的页面或文件夹。

只输出 JSON，不要 Markdown。

完成时格式：
{{
  "done": true,
  "answer": "给用户的最终回答",
  "observation": "当前截图观察",
  "reason": "为什么认为任务完成",
  "tool_calls": []
}}

需要继续时格式：
{{
  "done": false,
  "answer": "",
  "observation": "当前截图观察",
  "reason": "为什么下一步要这样做",
  "tool_calls": [
    {{
      "name": "tap",
      "arguments": {{"element": [500, 500]}},
      "reason": "点击目标"
    }}
  ]
}}
"""

    def _parse_decision(self, raw: str) -> AssistantDecision:
        data = parse_json_object(raw)
        calls = []
        for item in data.get("tool_calls") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            arguments = item.get("arguments") if isinstance(item.get("arguments"), dict) else {}
            calls.append(
                ToolCall(
                    name=name,
                    arguments=arguments,
                    reason=str(item.get("reason") or ""),
                )
            )

        return AssistantDecision(
            done=bool(data.get("done")),
            answer=str(data.get("answer") or ""),
            observation=str(data.get("observation") or ""),
            reason=str(data.get("reason") or ""),
            tool_calls=calls,
        )
