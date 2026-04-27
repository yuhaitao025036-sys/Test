# Tmux CC Experience - 使用指南

## 简介

`test_tmux_cc.py` 是一个独立的脚本，可以让你通过 tmux 实时监控 ducc（Claude Coding CLI）的执行过程。

## 主要特性

1. **实时监控**: 通过 tmux session 实时查看 ducc 的执行情况
2. **自动确认**: 自动处理 "Trust this folder" 等提示
3. **批处理模式**: 支持非交互式批处理执行
4. **工作空间隔离**: 为每个任务创建独立的工作空间
5. **完全独立**: 不依赖 Experience 代码库的任何代码

## 安装依赖

```bash
# 确保已安装 tmux
brew install tmux  # macOS
# 或
apt-get install tmux  # Linux
```

## 基础用法

### 1. 交互模式（推荐）

交互模式会创建一个 tmux session，你可以 attach 到这个 session 查看 ducc 的实时执行情况：

```bash
# 基础用法
python test_tmux_cc.py --interactive --prompt "创建一个 hello world Python 脚本"

# 指定工作目录
python test_tmux_cc.py --interactive --cwd /tmp/my_workspace --prompt "列出所有 Python 文件"

# 自定义 session 名称
python test_tmux_cc.py --interactive --tmux-session my_task --prompt "重构代码"

# 指定模型
python test_tmux_cc.py --interactive --model claude-3-5-sonnet-20241022 --prompt "任务描述"
```

### 2. 批处理模式

批处理模式不使用 tmux，直接在命令行中执行并返回结果：

```bash
python test_tmux_cc.py --prompt "列出当前目录下的所有文件"
```

## 实时监控

当你在交互模式下运行脚本后，会看到类似的输出：

```
============================================================
Running ducc in interactive mode
============================================================
Session: ducc_experience_1735286400
Working directory: /tmp/ducc_workspace_xyz
Prompt: 创建一个 hello world Python 脚本

To watch execution in real-time, run:
  tmux attach -t ducc_experience_1735286400
============================================================
```

### 连接到 tmux session

在另一个终端窗口中运行：

```bash
tmux attach -t ducc_experience_1735286400
```

你会看到 ducc 正在执行的实时界面，包括：
- 正在使用的工具（Read, Write, Edit）
- 思考过程
- 文件操作
- 执行结果

### 断开连接（不终止 session）

在 tmux 内部按：`Ctrl-b` 然后按 `d`

### 关闭 session

```bash
tmux kill-session -t ducc_experience_1735286400
```

## 高级选项

### 完整参数列表

```bash
python test_tmux_cc.py --help
```

主要参数：

- `--prompt, -p`: 任务提示（必需）
- `--interactive`: 启用交互模式（使用 tmux）
- `--tmux-session`: 自定义 tmux session 名称
- `--cwd`: 工作目录（默认使用临时目录）
- `--no-auto-confirm`: 禁用自动确认提示
- `--model`: 指定模型名称
- `--ducc-bin`: ducc 二进制文件路径（默认自动检测）
- `--permission-mode`: 权限模式（默认: bypassPermissions）
- `--allowed-tools`: 允许的工具列表（默认: Read,Edit,Write）
- `--effort`: 执行努力程度（low/medium/high，默认: low）

## 配置 ducc 路径

脚本会按以下优先级查找 ducc 二进制文件：

1. `DUCC_BIN` 环境变量
2. PATH 中的 `ducc` 命令
3. `~/.comate/extensions/baidu-cc/dist/agent`
4. `/usr/local/bin/ducc`

### 设置环境变量

```bash
export DUCC_BIN=/path/to/your/ducc
python test_tmux_cc.py --interactive --prompt "任务"
```

或在命令行中直接指定：

```bash
python test_tmux_cc.py --ducc-bin /path/to/ducc --interactive --prompt "任务"
```

## 使用场景示例

### 场景 1: 调试代码生成

```bash
# 启动交互模式
python test_tmux_cc.py --interactive \
  --cwd /path/to/project \
  --prompt "修复 main.py 中的类型错误"

# 在另一个终端监控
tmux attach -t ducc_experience_xxx
```

### 场景 2: 批量处理多个任务

创建一个脚本 `run_tasks.sh`:

```bash
#!/bin/bash

tasks=(
  "生成单元测试"
  "重构函数"
  "添加文档字符串"
)

for task in "${tasks[@]}"; do
  echo "执行: $task"
  python test_tmux_cc.py --prompt "$task" --cwd /tmp/project
done
```

### 场景 3: 与现有工作流集成

```python
import subprocess
import sys

def run_ducc_with_tmux(prompt, workspace):
    """在 Python 中调用 ducc"""
    cmd = [
        "python", "test_tmux_cc.py",
        "--interactive",
        "--cwd", workspace,
        "--prompt", prompt
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        return False
    return True

# 使用
if __name__ == "__main__":
    run_ducc_with_tmux(
        prompt="重构所有测试文件",
        workspace="/tmp/my_project"
    )
```

## 工作原理

脚本的核心流程：

1. **创建 tmux session**: 在指定的工作目录创建一个独立的 tmux session
2. **启动 ducc**: 在 tmux 中启动 ducc 命令
3. **自动确认**: 监控屏幕内容，自动处理常见提示
4. **发送任务**: 将用户的 prompt 发送给 ducc
5. **监控执行**: 
   - 检测任务开始（工具调用、Thinking 等指示器）
   - 检测任务完成（Done、空闲状态等）
   - 处理超时和异常情况
6. **保持 session**: 任务完成后保持 session 活跃，方便查看结果

## 故障排除

### 问题 1: 找不到 ducc

```
Error: Cannot find ducc binary. Please either:
  1. Set DUCC_BIN environment variable
  2. Install ducc and add it to your PATH
  3. Install baidu-cc extension in ~/.comate/extensions/
```

**解决方案**: 设置 `DUCC_BIN` 环境变量或使用 `--ducc-bin` 参数

### 问题 2: tmux 未安装

```
Error: tmux is not available. Please install tmux.
```

**解决方案**: 安装 tmux

```bash
brew install tmux  # macOS
apt-get install tmux  # Linux
```

### 问题 3: Session 一直运行不结束

可能是自动检测失败。可以手动连接到 session 查看：

```bash
tmux attach -t session_name
```

或者强制终止：

```bash
tmux kill-session -t session_name
```

### 问题 4: 自动确认不工作

使用 `--no-auto-confirm` 禁用自动确认，手动操作：

```bash
python test_tmux_cc.py --interactive --no-auto-confirm --prompt "任务"
tmux attach -t session_name  # 手动处理提示
```

## 与原有代码的区别

这个脚本从 `experience/llm_client/tmux_cc_task_handler.py` 和 `experience/example/code_auto_encoder/test_baseline.py` 借鉴了 tmux 集成的核心思想，但做了以下改进：

1. **完全独立**: 不依赖 Experience 代码库的任何模块
2. **简化接口**: 提供简单的命令行接口，不需要理解 AgentTask 等复杂概念
3. **更清晰的职责**: 专注于 tmux 集成和实时监控
4. **更好的用户体验**: 提供清晰的提示和错误信息

## 总结

`test_tmux_cc.py` 让你能够：

- ✅ 实时查看 ducc 的执行过程
- ✅ 在独立的工作空间中运行任务
- ✅ 自动处理常见的交互提示
- ✅ 轻松集成到现有工作流
- ✅ 完全独立，不依赖其他代码

开始使用：

```bash
python test_tmux_cc.py --interactive --prompt "你的任务"
```

然后在另一个终端中：

```bash
tmux attach -t ducc_experience_xxx
```

享受实时监控 ducc 执行的体验！
