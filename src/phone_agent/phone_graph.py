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
        graph.add_node("clarify_problem", self.problem.clarify)
        graph.add_node("decide_plan", self.problem.decide_phone_loop)
        graph.add_node("init_loop", self.loop.init_loop)
        graph.add_node("perceive_and_decide", self.vision.perceive_and_decide)
        graph.add_node("execute_action", self.loop.execute_action)
        graph.add_node("answer", self.answer_builder.answer)

        graph.add_edge(START, "clarify_problem")
        graph.add_edge("clarify_problem", "decide_plan")
        graph.add_conditional_edges(
            "decide_plan",
            self.loop.route_after_decision,
            {
                "init_loop": "init_loop",
                "answer": "answer",
            },
        )
        graph.add_edge("init_loop", "perceive_and_decide")
        graph.add_conditional_edges(
            "perceive_and_decide",
            self.loop.route_after_perception,
            {
                "execute_action": "execute_action",
                "answer": "answer",
            },
        )
        graph.add_conditional_edges(
            "execute_action",
            self.loop.route_after_action,
            {
                "perceive_and_decide": "perceive_and_decide",
                "answer": "answer",
            },
        )
        graph.add_edge("answer", END)
        return graph.compile()


def build_graph():
    return PhoneAgentGraph().build()


def run_phone_plan(task: str) -> str:
    debug_log("run", action="start", task=task)
    app = build_graph()
    result = app.invoke({"user_input": task})
    debug_log("run", action="end")
    return result["final"]
