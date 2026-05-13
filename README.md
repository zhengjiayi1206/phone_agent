# phone-agent

一个模仿 Claw Code / Claude Code 执行方式的手机界面 agent。

核心不是“一次性 plan 完再按步骤执行”，而是：

```text
用户输入
  -> 构建唯一 PhoneSession
  -> 构建 System Prompt / Tool Registry / PhoneRuntime
  -> run_turn(user_input)
      -> 用户消息写入 session
      -> loop:
          -> 自动截图
          -> 调视觉模型
          -> 模型输出 done 或 tool_calls
          -> assistant 决策写入 session
          -> 如果 done 或无 tool_calls：结束
          -> 执行每个 phone tool
          -> tool_result 写回 session
          -> 进入下一轮
  -> 本地保存 session / memory
  -> 输出结果
```

## 运行

```bash
cd /Users/zhengjiayi/PythonProjects/phone-agent
uv run phone-plan "帮我看看手机当前界面是什么"
```

测试模型配置：

```bash
uv run python scripts/test_model_call.py
```

测试 ADB 工具：

```bash
uv run python scripts/test_adb_phone_actions.py --dry-run
uv run python scripts/test_adb_phone_actions.py
```

## 本地文件

运行时会生成：

```text
artifacts/phone-screen.png       # 原始手机截图
artifacts/phone-screen-1000.png  # 给模型看的 1000x1000 标准截图
.phone_agent/session.jsonl       # 当前唯一用户 session
.phone_agent/memory.jsonl        # 长期本地记忆/事件记录
```

这些都不会提交到 git。

## 环境变量

```bash
cp .env.example .env
```

`.env` 示例：

```bash
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen3.6-plus-2026-04-02
PHONE_AGENT_VISION_MODEL=qwen3.6-plus-2026-04-02
OPENAI_TIMEOUT=30
PHONE_AGENT_DEBUG=1
PHONE_AGENT_DEBUG_VERBOSE=0
```

## 调试

关闭 debug：

```bash
PHONE_AGENT_DEBUG=0 uv run phone-plan "帮我看看手机当前界面是什么"
```

看模型原文：

```bash
PHONE_AGENT_DEBUG_VERBOSE=1 uv run phone-plan "帮我看看手机当前界面是什么"
```

过滤关键日志：

```bash
uv run phone-plan "帮我看看手机当前界面是什么" 2>&1 | grep -E "runtime|model.decision|tool.call|tool.result"
```

## 代码结构

- `src/phone_agent/runtime.py`
  - `PhoneRuntime.run_turn()`：Claw 风格主循环。
- `src/phone_agent/session.py`
  - `PhoneSession`：唯一 session，本地 JSONL 持久化。
- `src/phone_agent/model.py`
  - `PhoneModel`：截图 + 历史 + 工具列表 -> 模型决策 JSON。
- `src/phone_agent/tools.py`
  - `ToolRegistry` 和手机工具执行。
- `src/phone_agent/adb_tools.py`
  - ADB 底层命令。
- `src/phone_agent/screen.py`
  - 1000x1000 标准截图和坐标转换。
- `src/phone_agent/cli.py`
  - `phone-plan` / `phone-agent` 命令入口。
