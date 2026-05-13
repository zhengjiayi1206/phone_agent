# LangGraph Planner Loop

这个目录演示的是：

```text
用户目标
  -> planner: AI 生成树形流程计划
  -> scheduler: 从计划栈取下一个步骤
  -> executor: 执行当前步骤
  -> scheduler: 继续 loop
  -> synthesizer: 汇总最终结果
```

关键点是：LangGraph 的图结构是固定的，AI 只生成计划数据。

```text
AI 生成：
- 主流程
- 子流程
- 子子流程

LangGraph 控制：
- 状态
- 路由
- loop
- 最大迭代次数
- 汇总结束
```

运行：

```bash
uv run phone-flow-plan "帮我规划并执行一个市场调研任务" --show-results
```

也可以直接运行模块：

```bash
uv run python -m phone_agent.langgraph_planner.cli "帮我规划一个新产品调研流程"
```

主要文件：

- `schema.py`: 定义计划树、执行栈、状态结构。
- `graph.py`: 定义 LangGraph 节点和 loop。
- `cli.py`: 命令行入口。
