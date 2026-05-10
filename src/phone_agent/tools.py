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
        f"Screenshot saved to {path}; normalized screenshot saved to artifacts/phone-screen-1000.png; "
        f"coordinate mapping: model sees 1000x1000, real screen is {scale.source_width}x{scale.source_height}"
    )


def tap_from_model_args(**kwargs: Any) -> str:
    debug_json("tool.tap.args", kwargs)
    x, y = extract_point(kwargs)
    real_x, real_y = normalized_to_real_point(x, y)
    debug_json("tool.tap.map", {"normalized": [x, y], "real": [real_x, real_y]})
    result = adb_tools.tap(real_x, real_y)
    return f"{result}; normalized ({x}, {y}) -> real ({real_x}, {real_y})"


def swipe_from_model_args(**kwargs: Any) -> str:
    debug_json("tool.swipe.args", kwargs)
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
    return (
        f"{result}; normalized ({start_x}, {start_y}) -> ({end_x}, {end_y}) "
        f"mapped to real ({real_start_x}, {real_start_y}) -> ({real_end_x}, {real_end_y})"
    )


def wait_from_model_args(**kwargs: Any) -> str:
    debug_json("tool.wait.args", kwargs)
    seconds = kwargs.get("seconds")
    if seconds is None and "duration_ms" in kwargs:
        seconds = float(kwargs["duration_ms"]) / 1000
    if seconds is None and "duration" in kwargs:
        seconds = normalize_duration(kwargs["duration"])
    if seconds is None:
        seconds = 1.0
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
    if text.endswith("milliseconds"):
        return float(text[: -len("milliseconds")].strip()) / 1000
    if text.endswith("seconds"):
        return float(text[: -len("seconds")].strip())
    if text.endswith("second"):
        return float(text[: -len("second")].strip())
    if text.endswith("s"):
        return float(text[:-1].strip())
    return float(text)


PHONE_TOOLS: dict[str, PhoneTool] = {
    "screenshot": PhoneTool(
        name="screenshot",
        description="截图并生成 1000x1000 标准化图片，后续点击/滑动坐标都基于这张图。",
        handler=screenshot,
    ),
    "tap": PhoneTool(
        name="tap",
        description='点击 1000x1000 图片上的位置，参数使用 {"element": [x, y]}。',
        handler=tap_from_model_args,
    ),
    "swipe": PhoneTool(
        name="swipe",
        description='滑动 1000x1000 图片上的区域，参数使用 {"start": [x1, y1], "end": [x2, y2]}。',
        handler=swipe_from_model_args,
    ),
    "back": PhoneTool(
        name="back",
        description="按 Android 返回键。",
        handler=adb_tools.press_back,
    ),
    "home": PhoneTool(
        name="home",
        description="按 Android Home 键。",
        handler=adb_tools.press_home,
    ),
    "enter": PhoneTool(
        name="enter",
        description="按 Android Enter 键。",
        handler=adb_tools.press_enter,
    ),
    "input_text": PhoneTool(
        name="input_text",
        description='向当前输入框输入文字，参数使用 {"text": "..."}。',
        handler=adb_tools.input_text,
    ),
    "wait": PhoneTool(
        name="wait",
        description='等待界面稳定，参数可用 {"seconds": 1} 或 {"duration_ms": 1000}。',
        handler=wait_from_model_args,
    ),
}


def run_ui_phone_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
    tool = PHONE_TOOLS.get(name)
    if tool is None:
        raise ValueError(f"Unknown phone tool: {name}")

    clean_arguments = {key: value for key, value in (arguments or {}).items() if value is not None}
    debug_json("tool.dispatch", {"tool": name, "arguments": clean_arguments})
    output = tool.handler(**clean_arguments)
    debug_json("tool.result", {"tool": name, "output": output})
    return output


def describe_phone_tools() -> str:
    lines = ["Available phone tools:"]
    for tool in PHONE_TOOLS.values():
        lines.append(f"- {tool.name}: {tool.description}")
    return "\n".join(lines)
