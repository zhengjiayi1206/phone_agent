# phone-agent

一个用 `uv` 管理的最小 Python agent 项目。

它故意只保留核心结构：

```text
用户输入
  -> 模型判断是否需要工具
  -> Python 执行工具
  -> 工具结果返回给模型
  -> 模型输出最终回答
```

## 运行

先进入项目目录：

```bash
cd /Users/zhengjiayi/PythonProjects/phone-agent
```

不设置 API key 时，会走本地演示模式：

```bash
uv run phone-agent "list files"
uv run phone-agent "read pyproject"
```

测试模型配置是否能连通：

```bash
uv run python scripts/test_model_call.py
```

运行正式的 LangGraph 手机 planner：

```bash
uv run phone-plan "帮我看看手机当前界面是什么"
```

它会先明确问题，再判断是否需要操作手机。如果需要操作手机，会进入最多 5 轮的闭环：

```text
截图 -> 把 1000x1000 图片给 LLM -> LLM 判断是否完成
  -> 未完成则输出一个 UI action
  -> 执行动作
  -> 再截图检查
```

截图会同时生成：

```text
artifacts/phone-screen.png       # 手机真实截图
artifacts/phone-screen-1000.png  # 给 LLM 看和标坐标用的 1000x1000 标准图
```

LLM 只需要输出 1000x1000 标准图坐标，`tap` / `swipe` 工具会自动把坐标转换成真实手机像素。

默认会输出简洁 debug 路由日志，例如当前第几轮、截图路径、模型判断、下一步 action 和执行结果。关闭 debug：

```bash
PHONE_AGENT_DEBUG=0 uv run phone-plan "帮我看看手机当前界面是什么"
```

如果需要排查模型 JSON 原文，再打开 verbose：

```bash
PHONE_AGENT_DEBUG_VERBOSE=1 uv run phone-plan "帮我看看手机当前界面是什么"
```

如果文本模型和视觉模型不是同一个，可以设置：

```bash
PHONE_AGENT_VISION_MODEL=qwen3-vl-plus
```

如果卡在视觉模型请求，可以缩短或调长超时：

```bash
OPENAI_TIMEOUT=30
```

设置 API key、Base URL 和模型后，会走真实模型调用：

```bash
cp .env.example .env
# 然后编辑 .env，填入自己的真实 API key
uv run phone-agent "看看这个项目里有哪些文件"
```

如果使用阿里云百炼 / DashScope 的 OpenAI 兼容接口，`.env` 里通常是：

```bash
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen3.6-plus-2026-04-02
OPENAI_TIMEOUT=30
PHONE_AGENT_DEBUG=1
PHONE_AGENT_DEBUG_VERBOSE=0
```

也可以指定模型：

```bash
uv run phone-agent --model gpt-4.1-mini "read pyproject.toml and summarize it"
```

## 代码入口

- `src/phone_agent/__init__.py`
  - `main()`：命令行入口
  - `run_openai_agent()`：真实 agent 主循环
  - `list_files()` / `read_file()`：两个本地工具
  - `run_local_demo()`：没有 API key 时的教学演示
- `src/phone_agent/cli.py`
  - `phone-plan` 的命令行入口
- `src/phone_agent/phone_graph.py`
  - `PhoneAgentGraph`：LangGraph 装配入口
- `src/phone_agent/problem.py`
  - `ProblemInterpreter`：明确问题、判断是否需要手机操作
- `src/phone_agent/vision.py`
  - `VisionDecisionMaker`：截图输入、视觉判断是否完成、决定下一步 action
- `src/phone_agent/loop.py`
  - `PhoneLoopController`：最多 5 轮的循环状态、路由和 action 执行
- `src/phone_agent/answer.py`
  - `AnswerBuilder`：直接回答或汇总循环结果
- `src/phone_agent/types.py`
  - 明确问题、是否需要手机操作、每轮 action 判断、循环结果这些数据对象
- `src/phone_agent/adb_tools.py`
  - adb 截图工具
- `src/phone_agent/tools.py`
  - 手机 UI 操作 tool 描述和执行入口：截图、点击、滑动、返回、Home、输入文本、等待
- `src/phone_agent/apps.py`
  - 常见 App 名称到 Android 包名的映射
- `src/phone_agent/screen.py`
  - 1000x1000 标准截图生成，以及标准坐标到真实手机坐标的转换
- `src/phone_agent/config.py`
  - 环境变量、模型和 OpenAI-compatible client 配置
