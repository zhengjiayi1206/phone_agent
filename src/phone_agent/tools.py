from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from phone_agent import adb_tools
from phone_agent.config import debug_json, debug_log
from phone_agent.screen import create_normalized_screenshot, normalized_to_real_point


@dataclass(frozen=True)
class PhoneTool:
    name: str
    description: str
    handler: Callable[..., str]


class ToolRegistry:
    def __init__(self) -> None:
        self.tools: dict[str, PhoneTool] = {}

    def register(self, tool: PhoneTool) -> "ToolRegistry":
        self.tools[tool.name] = tool
        return self

    def describe(self) -> str:
        lines = ["可用手机工具:"]
        for tool in self.tools.values():
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        tool = self.tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown phone tool: {name}")

        clean_arguments = {key: value for key, value in (arguments or {}).items() if value is not None}
        debug_json("tool.dispatch", {"tool": name, "arguments": clean_arguments})
        output = tool.handler(**clean_arguments)
        debug_json("tool.result", {"tool": name, "output": output})
        return output


def build_tool_registry() -> ToolRegistry:
    return (
        ToolRegistry()
        .register(PhoneTool("screenshot", "截取当前屏幕，并生成 1000x1000 标准化截图。参数: {}", screenshot))
        .register(PhoneTool("tap", '点击 1000x1000 截图坐标。参数: {"element": [x, y]}', tap))
        .register(PhoneTool("swipe", '滑动 1000x1000 截图坐标。参数: {"start": [x,y], "end": [x,y], "duration_ms": 300}', swipe))
        .register(PhoneTool("back", "按 Android 返回键。参数: {}", lambda: adb_tools.press_back()))
        .register(PhoneTool("home", "按 Android Home 键。参数: {}", lambda: adb_tools.press_home()))
        .register(PhoneTool("enter", "按 Android Enter 键。参数: {}", lambda: adb_tools.press_enter()))
        .register(PhoneTool("input_text", '向当前输入框输入文字。参数: {"text": "..."}', input_text))
        .register(PhoneTool("wait", '等待界面稳定。参数: {"seconds": 1}', wait))
    )


def screenshot() -> str:
    debug_log("tool.start", tool="screenshot")
    path = adb_tools.take_screenshot()
    scale = create_normalized_screenshot(path)
    debug_json(
        "tool.screenshot",
        {
            "real_path": str(path),
            "normalized_path": "artifacts/phone-screen-1000.png",
            "source_width": scale.source_width,
            "source_height": scale.source_height,
        },
    )
    return (
        "Screenshot saved. normalized_path=artifacts/phone-screen-1000.png "
        f"source={scale.source_width}x{scale.source_height}"
    )


def tap(**kwargs: Any) -> str:
    x, y = extract_point(kwargs)
    real_x, real_y = normalized_to_real_point(x, y)
    debug_json("tool.tap.map", {"normalized": [x, y], "real": [real_x, real_y]})
    result = adb_tools.tap(real_x, real_y)
    return f"{result}; normalized=({x}, {y}) real=({real_x}, {real_y})"


def swipe(**kwargs: Any) -> str:
    start_x, start_y = extract_point(
        kwargs,
        point_keys=("start", "from", "begin"),
        x_keys=("start_x", "x1"),
        y_keys=("start_y", "y1"),
    )
    end_x, end_y = extract_point(
        kwargs,
        point_keys=("end", "to", "finish"),
        x_keys=("end_x", "x2"),
        y_keys=("end_y", "y2"),
    )
    duration_ms = int(kwargs.get("duration_ms") or kwargs.get("duration") or 300)
    real_start_x, real_start_y = normalized_to_real_point(start_x, start_y)
    real_end_x, real_end_y = normalized_to_real_point(end_x, end_y)
    debug_json(
        "tool.swipe.map",
        {
            "normalized_start": [start_x, start_y],
            "normalized_end": [end_x, end_y],
            "real_start": [real_start_x, real_start_y],
            "real_end": [real_end_x, real_end_y],
            "duration_ms": duration_ms,
        },
    )
    result = adb_tools.swipe(real_start_x, real_start_y, real_end_x, real_end_y, duration_ms)
    return f"{result}; normalized=({start_x}, {start_y})->({end_x}, {end_y})"


def input_text(text: str) -> str:
    return adb_tools.input_text(text)


def wait(seconds: float = 1.0, duration_ms: int | None = None, duration: str | None = None) -> str:
    if duration_ms is not None:
        seconds = duration_ms / 1000
    elif duration is not None:
        seconds = normalize_duration(duration)
    return adb_tools.wait(float(seconds))


def extract_point(
    arguments: dict[str, Any],
    point_keys: tuple[str, ...] = ("element", "point", "position", "coordinate"),
    x_keys: tuple[str, ...] = ("x",),
    y_keys: tuple[str, ...] = ("y",),
) -> tuple[int, int]:
    for key in point_keys:
        value = arguments.get(key)
        if isinstance(value, list | tuple) and len(value) >= 2:
            return int(value[0]), int(value[1])
        if isinstance(value, dict):
            return extract_point(value, x_keys=x_keys, y_keys=y_keys)

    x = first_present(arguments, x_keys)
    y = first_present(arguments, y_keys)
    if x is None or y is None:
        raise ValueError(f"Missing point coordinates in arguments: {arguments}")
    return int(x), int(y)


def first_present(arguments: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in arguments:
            return arguments[key]
    return None


def normalize_duration(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip().lower()
    if text.endswith("ms"):
        return float(text[:-2].strip()) / 1000
    if text.endswith("s"):
        return float(text[:-1].strip())
    return float(text)


DEFAULT_REGISTRY = build_tool_registry()


def run_ui_phone_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
    return DEFAULT_REGISTRY.execute(name, arguments)


def describe_phone_tools() -> str:
    return DEFAULT_REGISTRY.describe()
