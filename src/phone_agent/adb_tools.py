from __future__ import annotations

import base64
import subprocess
import time
from pathlib import Path
from typing import Any

from phone_agent.config import debug_log


ARTIFACTS_DIR = Path("artifacts")
DEFAULT_SCREENSHOT_PATH = ARTIFACTS_DIR / "phone-screen.png"
DEFAULT_DEVICE_PATH = "/sdcard/phone-agent-screen.png"
DEFAULT_TAP_DELAY_SECONDS = 0.3
DEFAULT_SWIPE_DELAY_SECONDS = 0.8
DEFAULT_KEY_DELAY_SECONDS = 0.5


def run_adb(command: list[str]) -> str:
    ensure_adb_device()
    debug_log("adb.run", command=" ".join(command))
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    output = (result.stdout or result.stderr).strip()
    if output:
        debug_log("adb.out", output=output)
    return output


def expected_screenshot_commands() -> list[list[str]]:
    return [
        ["adb", "shell", "screencap", "-p", DEFAULT_DEVICE_PATH],
        ["adb", "pull", DEFAULT_DEVICE_PATH, str(DEFAULT_SCREENSHOT_PATH)],
    ]


def validate_adb_commands(commands: Any) -> None:
    expected = expected_screenshot_commands()
    if commands != expected:
        raise ValueError(f"Refusing unexpected adb commands: {commands}")


def ensure_adb_device() -> None:
    result = subprocess.run(
        ["adb", "devices"],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines()]
    devices = [line for line in lines if line.endswith("\tdevice")]
    if not devices:
        raise RuntimeError(f"No adb device found:\n{result.stdout}")


def run_adb_commands(commands: list[list[str]]) -> None:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    for command in commands:
        run_adb(command)


def take_screenshot(
    local_path: Path = DEFAULT_SCREENSHOT_PATH,
    device_path: str = DEFAULT_DEVICE_PATH,
) -> Path:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    run_adb(["adb", "shell", "screencap", "-p", device_path])
    run_adb(["adb", "pull", device_path, str(local_path)])
    return local_path


def tap(x: int, y: int) -> str:
    run_adb(["adb", "shell", "input", "tap", str(x), str(y)])
    time.sleep(DEFAULT_TAP_DELAY_SECONDS)
    return f"Tapped at ({x}, {y})"


def swipe(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration_ms: int = 300,
) -> str:
    if duration_ms <= 0:
        duration_ms = auto_swipe_duration_ms(start_x, start_y, end_x, end_y)
    run_adb(
        [
            "adb",
            "shell",
            "input",
            "swipe",
            str(start_x),
            str(start_y),
            str(end_x),
            str(end_y),
            str(duration_ms),
        ]
    )
    time.sleep(DEFAULT_SWIPE_DELAY_SECONDS)
    return f"Swiped from ({start_x}, {start_y}) to ({end_x}, {end_y}) in {duration_ms}ms"


def auto_swipe_duration_ms(start_x: int, start_y: int, end_x: int, end_y: int) -> int:
    dist_sq = (start_x - end_x) ** 2 + (start_y - end_y) ** 2
    duration_ms = int(dist_sq / 1000)
    return max(300, min(duration_ms, 1200))


def press_back() -> str:
    run_adb(["adb", "shell", "input", "keyevent", "KEYCODE_BACK"])
    time.sleep(DEFAULT_KEY_DELAY_SECONDS)
    return "Pressed Back"


def press_home() -> str:
    run_adb(["adb", "shell", "input", "keyevent", "KEYCODE_HOME"])
    time.sleep(DEFAULT_KEY_DELAY_SECONDS)
    return "Pressed Home"


def press_enter() -> str:
    run_adb(["adb", "shell", "input", "keyevent", "KEYCODE_ENTER"])
    time.sleep(DEFAULT_KEY_DELAY_SECONDS)
    return "Pressed Enter"


def input_text(text: str) -> str:
    escaped = text.replace("%", "%s").replace(" ", "%s")
    run_adb(["adb", "shell", "input", "text", escaped])
    time.sleep(DEFAULT_TAP_DELAY_SECONDS)
    return f"Input text: {text}"


def wait(seconds: float = 1.0) -> str:
    time.sleep(seconds)
    return f"Waited {seconds}s"


def is_package_installed(package_name: str) -> bool:
    output = run_adb(["adb", "shell", "pm", "list", "packages", package_name])
    return f"package:{package_name}" in output.splitlines()


def launch_package(package_name: str) -> str:
    if not is_package_installed(package_name):
        return f"Package not installed: {package_name}"
    run_adb(
        [
            "adb",
            "shell",
            "monkey",
            "-p",
            package_name,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ]
    )
    time.sleep(1.0)
    return f"Launched package: {package_name}"


def image_data_url(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"
