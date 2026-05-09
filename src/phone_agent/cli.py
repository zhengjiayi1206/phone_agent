from __future__ import annotations

import argparse

from phone_agent.config import load_config
from phone_agent.phone_graph import run_phone_plan


def main() -> None:
    load_config()

    parser = argparse.ArgumentParser(description="Simple LangGraph phone planner.")
    parser.add_argument("task", nargs="*", help="Phone task text.")
    args = parser.parse_args()

    task = " ".join(args.task).strip()
    if not task:
        task = input("Phone task> ").strip()

    print(run_phone_plan(task))
