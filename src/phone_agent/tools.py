from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from phone_agent import adb_tools
from phone_agent.apps import resolve_app_package
from phone_agent.screen import create_normalized_screenshot, normalized_to_real_point


@dataclass(frozen=True)
class PhoneTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., str]

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def screenshot() -> str:
    path = adb_tools.take_screenshot()
    scale = create_normalized_screenshot(path)
    return (
        f"Screenshot saved to {path}; normalized screenshot saved to artifacts/phone-screen-1000.png; "
        f"coordinate mapping: model sees 1000x1000, real screen is {scale.source_width}x{scale.source_height}"
    )


def tap_normalized(x: int, y: int) -> str:
    real_x, real_y = normalized_to_real_point(x, y)
    result = adb_tools.tap(real_x, real_y)
    return f"{result}; normalized ({x}, {y}) -> real ({real_x}, {real_y})"


def tap_from_model_args(**kwargs: Any) -> str:
    x, y = extract_point(kwargs, x_keys=("x",), y_keys=("y",))
    return tap_normalized(x, y)


def swipe_normalized(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration_ms: int = 300,
) -> str:
    real_start_x, real_start_y = normalized_to_real_point(start_x, start_y)
    real_end_x, real_end_y = normalized_to_real_point(end_x, end_y)
    result = adb_tools.swipe(real_start_x, real_start_y, real_end_x, real_end_y, duration_ms)
    return (
        f"{result}; normalized ({start_x}, {start_y}) -> ({end_x}, {end_y}) "
        f"mapped to real ({real_start_x}, {real_start_y}) -> ({real_end_x}, {real_end_y})"
    )


def swipe_from_model_args(**kwargs: Any) -> str:
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
    return swipe_normalized(start_x, start_y, end_x, end_y, duration_ms)


def find_app(app_name: str) -> str:
    package_name = resolve_app_package(app_name)
    if not package_name:
        return f"Unknown app name: {app_name}"
    installed = adb_tools.is_package_installed(package_name)
    return f"App {app_name} package={package_name} installed={installed}"


def launch_app(app_name: str) -> str:
    package_name = resolve_app_package(app_name)
    if not package_name:
        return f"Unknown app name: {app_name}"
    return adb_tools.launch_package(package_name)


def wait_from_model_args(**kwargs: Any) -> str:
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
        description=(
            "Capture the current Android phone screen, save the real screenshot to artifacts/phone-screen.png, "
            "and save a 1000x1000 normalized image to artifacts/phone-screen-1000.png. "
            "All later tap/swipe coordinates should be based on this 1000x1000 image."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        handler=screenshot,
    ),
    "tap": PhoneTool(
        name="tap",
        description=(
            "Tap a point using coordinates from the 1000x1000 normalized screenshot. "
            "Preferred arguments: {\"element\": [x, y]}. Also accepts {\"x\": x, \"y\": y}. "
            "Python converts normalized coordinates to real device pixels."
        ),
        parameters={
            "type": "object",
            "properties": {
                "element": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": "Preferred [x, y] coordinate on the 1000x1000 screenshot.",
                },
                "x": {"type": "integer", "description": "Horizontal coordinate on the 1000x1000 screenshot."},
                "y": {"type": "integer", "description": "Vertical coordinate on the 1000x1000 screenshot."},
            },
            "additionalProperties": False,
        },
        handler=tap_from_model_args,
    ),
    "find_app": PhoneTool(
        name="find_app",
        description="Check whether an Android app is installed using adb package manager. Prefer this over visual icon search when the user asks whether an app exists.",
        parameters={
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Chinese app name or Android package name, e.g. 淘宝 or com.taobao.taobao.",
                },
            },
            "required": ["app_name"],
            "additionalProperties": False,
        },
        handler=find_app,
    ),
    "launch_app": PhoneTool(
        name="launch_app",
        description="Launch an installed Android app by app name or package name using adb monkey.",
        parameters={
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Chinese app name or Android package name, e.g. 淘宝 or com.taobao.taobao.",
                },
            },
            "required": ["app_name"],
            "additionalProperties": False,
        },
        handler=launch_app,
    ),
    "swipe": PhoneTool(
        name="swipe",
        description=(
            "Swipe using coordinates from the 1000x1000 normalized screenshot. "
            "Preferred arguments: {\"start\": [x1, y1], \"end\": [x2, y2]}. "
            "Also accepts x1/y1/x2/y2 or start_x/start_y/end_x/end_y."
        ),
        parameters={
            "type": "object",
            "properties": {
                "start": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": "Preferred [x, y] start coordinate on the 1000x1000 screenshot.",
                },
                "end": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": "Preferred [x, y] end coordinate on the 1000x1000 screenshot.",
                },
                "start_x": {"type": "integer", "description": "Start horizontal coordinate on the 1000x1000 screenshot."},
                "start_y": {"type": "integer", "description": "Start vertical coordinate on the 1000x1000 screenshot."},
                "end_x": {"type": "integer", "description": "End horizontal coordinate on the 1000x1000 screenshot."},
                "end_y": {"type": "integer", "description": "End vertical coordinate on the 1000x1000 screenshot."},
                "x1": {"type": "integer", "description": "Alias for start_x."},
                "y1": {"type": "integer", "description": "Alias for start_y."},
                "x2": {"type": "integer", "description": "Alias for end_x."},
                "y2": {"type": "integer", "description": "Alias for end_y."},
                "duration_ms": {
                    "type": "integer",
                    "description": "Swipe duration in milliseconds. Use 300 for a normal swipe.",
                    "default": 300,
                },
            },
            "additionalProperties": False,
        },
        handler=swipe_from_model_args,
    ),
    "back": PhoneTool(
        name="back",
        description="Press the Android Back button.",
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        handler=adb_tools.press_back,
    ),
    "home": PhoneTool(
        name="home",
        description="Press the Android Home button.",
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        handler=adb_tools.press_home,
    ),
    "enter": PhoneTool(
        name="enter",
        description="Press the Android Enter key.",
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        handler=adb_tools.press_enter,
    ),
    "input_text": PhoneTool(
        name="input_text",
        description="Type text into the focused Android input field. Tap the input field first if needed.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to type into the focused field."},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
        handler=adb_tools.input_text,
    ),
    "wait": PhoneTool(
        name="wait",
        description="Wait for the phone UI to settle after an action. Accepts seconds, duration_ms, or duration.",
        parameters={
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": "Seconds to wait.",
                    "default": 1.0,
                },
                "duration_ms": {
                    "type": "integer",
                    "description": "Milliseconds to wait.",
                },
                "duration": {
                    "type": "string",
                    "description": "Duration string, e.g. 1s, 500ms, or 1 seconds.",
                },
            },
            "additionalProperties": False,
        },
        handler=wait_from_model_args,
    ),
}

UI_TOOL_NAMES = (
    "screenshot",
    "tap",
    "swipe",
    "back",
    "home",
    "enter",
    "input_text",
    "wait",
)


def phone_tool_schemas() -> list[dict[str, Any]]:
    return [tool.openai_schema() for tool in PHONE_TOOLS.values()]


def run_phone_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
    tool = PHONE_TOOLS.get(name)
    if tool is None:
        raise ValueError(f"Unknown phone tool: {name}")
    return tool.handler(**sanitize_arguments(arguments or {}))


def run_ui_phone_tool(name: str, arguments: dict[str, Any] | None = None) -> str:
    if name not in UI_TOOL_NAMES:
        raise ValueError(f"Tool is not allowed in human-like UI mode: {name}")
    return run_phone_tool(name, arguments)


def sanitize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in arguments.items() if value is not None}


def describe_phone_tools() -> str:
    lines = ["Available phone tools:"]
    for name in UI_TOOL_NAMES:
        tool = PHONE_TOOLS[name]
        lines.append(f"- {tool.name}: {tool.description}")
    return "\n".join(lines)
