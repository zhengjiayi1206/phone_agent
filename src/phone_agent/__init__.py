from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


SYSTEM_PROMPT = """You are a small coding assistant.
Use tools when you need to inspect local files. Keep answers concise."""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory under the current project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path, relative to the current project.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file under the current project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path, relative to the current project.",
                    }
                },
                "required": ["path"],
            },
        },
    },
]


def project_path(path: str) -> Path:
    root = Path.cwd().resolve()
    target = (root / path).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"path escapes project: {path}")
    return target


def list_files(path: str) -> str:
    target = project_path(path)
    if not target.exists():
        return f"Not found: {path}"
    if not target.is_dir():
        return f"Not a directory: {path}"

    entries = []
    for child in sorted(target.iterdir(), key=lambda item: item.name):
        suffix = "/" if child.is_dir() else ""
        entries.append(f"{child.name}{suffix}")
    return "\n".join(entries) or "(empty directory)"


def read_file(path: str) -> str:
    target = project_path(path)
    if not target.exists():
        return f"Not found: {path}"
    if not target.is_file():
        return f"Not a file: {path}"
    return target.read_text(encoding="utf-8")


TOOLS: dict[str, Callable[..., str]] = {
    "list_files": list_files,
    "read_file": read_file,
}


def run_local_demo(prompt: str) -> str:
    """A tiny fake planner so the project works without an API key."""
    lower_prompt = prompt.lower()
    if "read" in lower_prompt and "pyproject" in lower_prompt:
        return read_file("pyproject.toml")
    if "list" in lower_prompt or "files" in lower_prompt or "目录" in prompt:
        return list_files(".")
    return (
        "Local demo mode: set OPENAI_API_KEY to use the real model loop.\n"
        "Try: uv run phone-agent \"list files\""
    )


def run_openai_agent(prompt: str, model: str) -> str:
    client = OpenAI()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    for _ in range(5):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            return message.content or ""

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            raw_args = tool_call.function.arguments or "{}"
            args = json.loads(raw_args)
            tool = TOOLS.get(name)
            result = tool(**args) if tool else f"Unknown tool: {name}"
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    return "Stopped after too many tool calls."


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="A minimal Python agent.")
    parser.add_argument("prompt", nargs="*", help="Task for the agent.")
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        help="OpenAI model name. Defaults to OPENAI_MODEL or gpt-4.1-mini.",
    )
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip()
    if not prompt:
        prompt = input("Ask phone-agent> ").strip()

    if os.getenv("OPENAI_API_KEY"):
        print(run_openai_agent(prompt, args.model))
    else:
        print(run_local_demo(prompt))
