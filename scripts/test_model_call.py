from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> None:
    load_dotenv()

    api_key = require_env("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    print("Testing model call...")
    print(f"OPENAI_API_KEY={mask_secret(api_key)}")
    print(f"OPENAI_BASE_URL={base_url or '(default OpenAI endpoint)'}")
    print(f"OPENAI_MODEL={model}")
    print()

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "Reply with exactly: model call ok"},
        ],
        temperature=0,
    )

    message = response.choices[0].message.content
    print("Model response:")
    print(message)


if __name__ == "__main__":
    main()
