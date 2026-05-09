from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from phone_agent.config import no_think_extra_body, text_model


def chat_text(client: OpenAI, messages: list[dict[str, Any]]) -> str:
    response = client.chat.completions.create(
        model=text_model(),
        messages=messages,
        temperature=0,
        extra_body=no_think_extra_body(),
    )
    return response.choices[0].message.content or ""


def parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Model did not return a JSON object: {text}")
    return json.loads(text[start : end + 1])
