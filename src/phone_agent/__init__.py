from __future__ import annotations

__all__ = ["main"]


def main() -> None:
    from phone_agent.cli import main as cli_main

    cli_main()
