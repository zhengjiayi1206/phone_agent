from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phone_agent.adb_tools import ensure_adb_device
from phone_agent.config import load_config
from phone_agent.tools import run_ui_phone_tool


@dataclass(frozen=True)
class ActionCase:
    name: str
    tool: str
    arguments: dict[str, Any]
    description: str


def build_cases(include_text: bool) -> list[ActionCase]:
    cases = [
        ActionCase("device", "wait", {"seconds": 0.1}, "检查脚本和工具链是否可调用"),
        ActionCase("home", "home", {}, "返回桌面"),
        ActionCase("screenshot", "screenshot", {}, "截图并生成 1000x1000 标准化图片"),
        ActionCase(
            "swipe_left",
            "swipe",
            {"start": [820, 520], "end": [220, 520], "duration_ms": 450},
            "向左滑动桌面或当前页面",
        ),
        ActionCase("wait_after_swipe", "wait", {"seconds": 0.5}, "等待滑动动画结束"),
        ActionCase(
            "swipe_right",
            "swipe",
            {"start": [220, 520], "end": [820, 520], "duration_ms": 450},
            "向右滑动回到原位置",
        ),
        ActionCase("tap_center", "tap", {"element": [500, 500]}, "点击屏幕中心"),
        ActionCase("back", "back", {}, "按返回键"),
        ActionCase("home_again", "home", {}, "再次返回桌面"),
        ActionCase("enter", "enter", {}, "按 Enter 键"),
    ]

    if include_text:
        cases.append(
            ActionCase(
                "input_text",
                "input_text",
                {"text": "phone-agent-test"},
                "向当前输入框输入测试文本；只有确认当前焦点在安全输入框时才建议开启",
            )
        )

    return cases


def run_case(case: ActionCase, dry_run: bool) -> bool:
    print(f"[test] {case.name}: {case.description}")
    print(f"       tool={case.tool} arguments={case.arguments}")

    if dry_run:
        print("       result=DRY_RUN")
        return True

    try:
        output = run_ui_phone_tool(case.tool, case.arguments)
    except Exception as exc:
        print(f"       status=FAIL error={type(exc).__name__}: {exc}")
        return False

    print(f"       status=PASS output={output}")
    return True


def main() -> int:
    load_config()

    parser = argparse.ArgumentParser(description="Test basic ADB phone UI actions.")
    parser.add_argument("--include-text", action="store_true", help="Also test input_text. Use only in a safe text field.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without running adb commands.")
    parser.add_argument("--pause", type=float, default=0.3, help="Seconds to pause between actions.")
    args = parser.parse_args()

    if not args.dry_run:
        print("[test] checking adb device")
        ensure_adb_device()
        print("[test] adb device found")

    passed = 0
    failed = 0
    for case in build_cases(include_text=args.include_text):
        if run_case(case, dry_run=args.dry_run):
            passed += 1
        else:
            failed += 1
        time.sleep(args.pause)

    print(f"[test] summary passed={passed} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
