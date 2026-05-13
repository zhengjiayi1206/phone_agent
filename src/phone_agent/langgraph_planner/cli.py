from __future__ import annotations

import argparse
import json

from phone_agent.config import load_config
from phone_agent.langgraph_planner.graph import run_planning_loop
from phone_agent.langgraph_planner.schema import format_plan_tree


def main() -> None:
    load_config()

    parser = argparse.ArgumentParser(
        description="Run an AI-generated plan through a fixed LangGraph loop."
    )
    parser.add_argument("goal", nargs="*", help="Goal to plan and execute.")
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument("--json", action="store_true", help="Print raw graph state.")
    parser.add_argument(
        "--show-results",
        action="store_true",
        help="Print each executed step result before the final answer.",
    )
    args = parser.parse_args()

    goal = " ".join(args.goal).strip()
    if not goal:
        goal = input("Goal> ").strip()

    result = run_planning_loop(goal, max_iterations=args.max_iterations)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    plan = result.get("plan", {"steps": []})
    print("计划：")
    print(format_plan_tree(plan["steps"]))

    if args.show_results:
        print()
        print("执行轨迹：")
        for item in result.get("results", []):
            print(f"- {item['path']} {item['title']}: {item['output']}")

    print()
    print("最终结果：")
    print(result.get("final", ""))
