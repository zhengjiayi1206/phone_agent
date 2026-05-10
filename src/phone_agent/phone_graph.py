from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from phone_agent.answer import AnswerBuilder
from phone_agent.config import debug_log
from phone_agent.loop import PhoneLoopController
from phone_agent.problem import ProblemInterpreter
from phone_agent.types import AgentState
from phone_agent.vision import VisionDecisionMaker


class PhoneAgentGraph:
    def __init__(self, max_loops: int = 5) -> None:
        self.problem = ProblemInterpreter()
        self.loop = PhoneLoopController(max_loops=max_loops)
        self.vision = VisionDecisionMaker()
        self.answer_builder = AnswerBuilder()

    def build(self):
        debug_log("graph", action="build")
        graph = StateGraph(AgentState)

        # 主流程只保留三件事：
        # 1. 明确问题并判断是否需要操作手机
        # 2. phone_loop：截图、判断、执行一个动作
        # 3. answer：完成或达到循环上限后输出结果
        graph.add_node("clarify_problem", self.problem.clarify)
        graph.add_node("phone_loop", self.phone_loop)
        graph.add_node("answer", self.answer_builder.answer)

        graph.add_edge(START, "clarify_problem")
        graph.add_conditional_edges(
            "clarify_problem",
            self.loop.route_after_problem,
            {"phone_loop": "phone_loop", "answer": "answer"},
        )
        graph.add_conditional_edges(
            "phone_loop",
            self.loop.route_after_loop,
            {"phone_loop": "phone_loop", "answer": "answer"},
        )
        graph.add_edge("answer", END)
        return graph.compile()

    def phone_loop(self, state: AgentState) -> AgentState:
        debug_log("enter", node="phone_loop", iteration=state.get("loop_count", 0) + 1)
        state = self.loop.ensure_started(state)
        state = self.vision.perceive_and_decide(state)

        if self.loop.should_execute_action(state):
            state = self.loop.execute_action(state)
        else:
            debug_log(
                "action.skip",
                iteration=state.get("loop_count", 0),
                done=state["action_decision"].done,
                tool=state["action_decision"].tool or "none",
            )

        return state


def build_graph():
    return PhoneAgentGraph().build()


def run_phone_plan(task: str) -> str:
    debug_log("run", action="start", task=task)
    app = build_graph()
    result = app.invoke({"user_input": task})
    debug_log("run", action="end")
    return result["final"]
