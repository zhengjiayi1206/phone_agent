from __future__ import annotations

import os
import sys
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_MODEL = "qwen3.6-plus-2026-04-02"


def load_config() -> None:
    load_dotenv()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def make_client() -> OpenAI:
    return OpenAI(
        api_key=require_env("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        timeout=request_timeout(),
    )


def text_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def vision_model() -> str:
    return os.getenv("PHONE_AGENT_VISION_MODEL", text_model())


def request_timeout() -> float:
    return float(os.getenv("OPENAI_TIMEOUT", "30"))


def no_think_extra_body() -> dict[str, bool]:
    # DashScope/Qwen uses this non-standard OpenAI-compatible parameter.
    return {"enable_thinking": False}


def debug_enabled() -> bool:
    value = os.getenv("PHONE_AGENT_DEBUG", "1").lower()
    return value not in {"0", "false", "no", "off"}


def debug_verbose_enabled() -> bool:
    value = os.getenv("PHONE_AGENT_DEBUG_VERBOSE", "0").lower()
    return value not in {"0", "false", "no", "off"}


def debug_log(event: str, **fields: Any) -> None:
    if not debug_enabled():
        return

    parts = [f"[debug] {event}"]
    for key, value in fields.items():
        if isinstance(value, str) and len(value) > 160:
            value = f"{value[:157]}..."
        parts.append(f"{key}={value}")
    print(" ".join(parts), file=sys.stderr)


def debug_verbose(event: str, **fields: Any) -> None:
    if not debug_verbose_enabled():
        return
    debug_log(event, **fields)
