# SWE-bench Pro DUCC 评测工具 - Tmux 模式使用指南

## 概述

本工具是 SWE-bench Pro 数据集的评测脚本，支持通过 **tmux 模式**实时查看 ducc 的执行过程。与传统的直接调用方式相比，tmux 模式让你能够：

- ✅ **实时监控**: 通过 tmux session 查看 ducc 的执行细节
- ✅ **调试方便**: 可以看到 ducc 的思考过程、文件读写操作
- ✅ **并行操作**: 在一个终端运行脚本，在另一个终端查看执行
- ✅ **会话保持**: 任务完成后 session 仍保持活跃，方便查看结果

## 安装依赖

### 1. 安装 tmux

```bash
# macOS
brew install tmux

# Ubuntu/Debian
sudo apt-get install tmux

# CentOS/RHEL
sudo yum install tmux
```

### 2. 安装 Python 依赖

```bash
pip install docker datasets
```

### 3. 安装 ducc

确保已安装 ducc 或 baidu-cc：

```bash
# 通过安装脚本
bash <(curl -fsSL http://baidu-cc-client.bj.bcebos.com/baidu-cc/install.sh)

# 或设置环境变量
export DUCC_BIN=/path/to/your/ducc
```

## 快速开始

### 方式一：直接模式（原有方式）

适用于批量运行，不需要实时查看执行过程：

```bash
# 运行单个任务
python test_tmux_cc_experience.py --index 0 --no-validate

# 批量运行前2个任务
python test_tmux_cc_experience.py --max-tasks 2 --no-validate
```

### 方式二：Tmux 模式（推荐）

适用于需要实时查看 ducc 执行过程的场景：

```bash
# 运行单个任务（tmux模式）
python test_tmux_cc_experience.py --index 0 --use-tmux --no-validate
```

运行后会显示：

```
============================================================
启动 tmux session: swe_bench_django__django_12345_1735286400
工作目录: /tmp/swe_bench_xyz/workspace
查看执行过程: tmux attach -t swe_bench_django__django_12345_1735286400
============================================================
```

### 实时查看执行

在另一个终端窗口中：

```bash
# 连接到 tmux session
tmux attach -t swe_bench_django__django_12345_1735286400

# 你会看到 ducc 的实时执行界面：
# - 思考过程 (Thinking...)
# - 文件读取 (Reading file.py...)
# - 代码编辑 (Editing file.py...)
# - 生成 patch
```

### 断开查看（不中断执行）

在 tmux 窗口内按：

```
Ctrl-b 然后按 d
```

这会断开连接但不会停止任务执行。

### 查看所有活跃的 session

```bash
tmux list-sessions
```

输出示例：

```
swe_bench_django__django_12345: 1 windows (created Mon Apr 27 10:30:00 2026)
swe_bench_flask__flask_67890: 1 windows (created Mon Apr 27 10:35:00 2026)
```

### 关闭 session

```bash
# 关闭特定 session
tmux kill-session -t swe_bench_django__django_12345

# 关闭所有 swe_bench 相关的 session
tmux list-sessions | grep swe_bench | cut -d: -f1 | xargs -I {} tmux kill-session -t {}
```

## 命令参数说明

### 必需参数（二选一）

- `--index N`: 运行第 N 个任务（从 0 开始）
- `--max-tasks N`: 运行前 N 个任务

### 可选参数

- `--use-tmux`: 启用 tmux 模式（推荐用于调试和学习）
- `--no-validate`: 跳过验证，只生成 patch（更快）
- `--output-dir DIR`: 输出目录，默认 `./swe_bench_output_ducc`

### 环境变量

- `DUCC_BIN`: ducc 二进制文件路径
- `SWE_BENCH_DATASET`: 数据集路径
- `DOCKER_IMAGE_PREFIX`: Docker 镜像前缀

## 使用场景

### 场景 1：调试单个任务

当某个任务失败时，使用 tmux 模式查看详细执行过程：

```bash
# 运行特定任务并实时查看
python test_tmux_cc_experience.py --index 5 --use-tmux --no-validate

# 在另一个终端连接查看
tmux attach -t swe_bench_xxx
```

### 场景 2：批量评测（直接模式）

批量运行时使用直接模式效率更高：

```bash
# 运行前 10 个任务，不验证
python test_tmux_cc_experience.py --max-tasks 10 --no-validate

# 运行前 5 个任务，包含验证
python test_tmux_cc_experience.py --max-tasks 5
```

### 场景 3：学习和理解 ducc 行为

使用 tmux 模式观察 ducc 如何处理问题：

```bash
# 选一个简单任务
python test_tmux_cc_experience.py --index 0 --use-tmux --no-validate

# 观察 ducc 的执行流程：
# 1. 如何探索代码库
# 2. 读取哪些文件
# 3. 如何分析问题
# 4. 如何生成修复
```

### 场景 4：混合模式

可以同时运行多个任务，部分使用 tmux 查看：

```bash
# Terminal 1: 批量运行
python test_tmux_cc_experience.py --max-tasks 5 --no-validate

# Terminal 2: 单独用 tmux 模式查看某个任务
python test_tmux_cc_experience.py --index 3 --use-tmux --no-validate

# Terminal 3: 连接查看
tmux attach -t swe_bench_xxx
```

## 输出文件结构

运行后会在输出目录生成以下文件：

```
swe_bench_output_ducc/
├── predictions/                    # SWE-bench 标准格式
│   ├── instance_001.json
│   ├── instance_002.json
│   └── ...
├── instance_001_full.json          # 完整结果（含验证信息）
├── instance_002_full.json
├── all_preds.jsonl                 # 所有预测汇总（JSONL格式）
└── report.json                     # 评测报告
```

### 查看结果

```bash
# 查看报告
cat swe_bench_output_ducc/report.json

# 查看单个任务的完整信息
cat swe_bench_output_ducc/instance_xxx_full.json | jq .

# 统计成功率
cat swe_bench_output_ducc/report.json | jq '.resolve_rate'
```

## Tmux 常用命令

### 基础命令

```bash
# 列出所有 session
tmux list-sessions
tmux ls

# 连接到 session
tmux attach -t <session_name>
tmux a -t <session_name>

# 新建 session
tmux new-session -s <name>

# 重命名 session
tmux rename-session -t <old_name> <new_name>

# 关闭 session
tmux kill-session -t <session_name>
```

### 在 tmux 内部的快捷键

所有命令都以 `Ctrl-b` 开头（称为 prefix）

```
Ctrl-b d         断开连接（detach）
Ctrl-b [         进入滚动模式（可以上下翻页查看历史）
  q              退出滚动模式
Ctrl-b ?         显示所有快捷键
Ctrl-b :         进入命令模式
```

### 滚动和查看历史

在 tmux session 内：

1. 按 `Ctrl-b [` 进入滚动模式
2. 使用方向键或 Page Up/Down 滚动
3. 按 `q` 退出滚动模式

## 工作原理

### 直接模式流程

```
1. 从 Docker 容器提取代码库到本地临时目录
2. 调用 ducc 命令行，传入 prompt
3. ducc 在本地目录执行，输出结果到 stdout
4. 解析输出，提取 patch
5. （可选）在 Docker 容器内验证 patch
6. 保存结果到文件
```

### Tmux 模式流程

```
1. 从 Docker 容器提取代码库到本地临时目录
2. 创建 tmux session
3. 在 tmux 中启动 ducc
4. 自动确认 "Trust this folder" 等提示
5. 发送 prompt 给 ducc
6. 监控 ducc 执行：
   - 检测任务开始（工具调用）
   - 检测执行中（Thinking, Reading, Writing 等）
   - 检测完成（Done 或空闲状态）
7. 捕获 tmux 输出，提取 patch
8. 保持 session 活跃（方便用户查看）
9. （可选）验证 patch
10. 保存结果
```

### 自动确认机制

tmux 模式会自动处理以下提示：

- "Do you want to proceed" → 自动按 Enter
- "Yes, I trust this folder" → 自动按 Enter  
- "allow all edits during this session" → 自动按 Down Enter
- "Press Enter to continue" → 自动按 Enter

## 对比两种模式

| 特性 | 直接模式 | Tmux 模式 |
|------|---------|----------|
| 执行速度 | 快 | 略慢（需要创建和监控 session） |
| 实时查看 | ❌ | ✅ |
| 批量运行 | ✅ 推荐 | ⚠️ 会创建多个 session |
| 调试方便 | ❌ | ✅ |
| 资源占用 | 低 | 稍高（保持 session） |
| 学习价值 | 低 | 高（可观察执行过程） |

**推荐使用策略**：

- 🔍 **调试/学习**: 使用 tmux 模式
- 🚀 **批量评测**: 使用直接模式
- 🧪 **测试新 prompt**: 使用 tmux 模式观察效果

## 常见问题

### 1. 找不到 ducc 二进制文件

```
Error: 找不到 ducc 或 baidu-cc!
```

**解决方案**：

```bash
# 方式1: 设置环境变量
export DUCC_BIN=/path/to/your/ducc

# 方式2: 安装 ducc
bash <(curl -fsSL http://baidu-cc-client.bj.bcebos.com/baidu-cc/install.sh)

# 验证安装
which ducc
```

### 2. tmux 未安装

```
Error: tmux is not available
```

**解决方案**：

```bash
# macOS
brew install tmux

# Ubuntu/Debian
sudo apt-get install tmux
```

### 3. Session 已存在

如果看到 session 名称冲突：

```bash
# 查看现有 session
tmux ls

# 关闭冲突的 session
tmux kill-session -t <session_name>
```

### 4. Session 不会自动结束

这是设计行为，session 会保持活跃方便查看结果。手动关闭：

```bash
# 关闭特定 session
tmux kill-session -t swe_bench_xxx

# 或批量关闭
tmux list-sessions | grep swe_bench | cut -d: -f1 | xargs -I {} tmux kill-session -t {}
```

### 5. 任务执行超时

默认超时 600 秒（10 分钟），可以修改代码中的 `timeout` 参数。

### 6. Docker 镜像拉取失败

```bash
# 检查 Docker 是否运行
docker ps

# 手动拉取镜像
docker pull jefzda/sweap-images:<tag>

# 或使用其他镜像源
export DOCKER_IMAGE_PREFIX="aorwall/swe-bench"
```

### 7. 内存不足

```bash
# 清理未使用的容器和镜像
docker system prune -a

# 查看当前占用
docker stats
```

## 高级技巧

### 技巧 1: 自定义 tmux 配置

创建 `~/.tmux.conf`：

```bash
# 增加历史缓冲区大小
set-option -g history-limit 50000

# 使用鼠标滚动
set -g mouse on

# 更好的颜色支持
set -g default-terminal "screen-256color"
```

### 技巧 2: 保存 tmux 输出到文件

```bash
# 在 tmux session 内
tmux capture-pane -p -S - > /tmp/ducc_output.txt
```

### 技巧 3: 分屏查看

可以在一个终端同时查看代码和 ducc 执行：

```bash
# 连接到 session
tmux attach -t swe_bench_xxx

# 在 tmux 内部分屏
Ctrl-b %    # 垂直分屏
Ctrl-b "    # 水平分屏
Ctrl-b o    # 切换窗格
```

### 技巧 4: 批量查看多个任务

```bash
#!/bin/bash
# watch_all.sh - 监控所有活跃的 swe_bench session

for session in $(tmux list-sessions | grep swe_bench | cut -d: -f1); do
    echo "=== Session: $session ==="
    tmux capture-pane -p -t $session | tail -20
    echo ""
done
```

## 示例：完整工作流

### 步骤 1: 准备环境

```bash
# 进入工作目录
cd /Users/yuhaitao01/dev/baidu/explore/test

# 检查环境
python test_tmux_cc_experience.py --help
tmux -V
docker --version
```

### 步骤 2: 运行单个任务（tmux 模式）

```bash
# Terminal 1: 运行任务
python test_tmux_cc_experience.py --index 0 --use-tmux --no-validate
```

### 步骤 3: 实时查看执行

```bash
# Terminal 2: 连接查看
tmux attach -t swe_bench_<instance_id>

# 你会看到：
# ✓ tmux session 已创建
# ✓ ducc 命令已发送
# ✓ 任务已开始 (检测到: Read()
#   ducc 正在工作...
#   屏幕无变化 (1/3)
#   屏幕无变化 (2/3)
#   屏幕无变化 (3/3)
# ✓ 任务完成
```

### 步骤 4: 查看结果

```bash
# 查看生成的 patch
cat swe_bench_output_ducc/<instance_id>_full.json | jq '.patch'

# 查看验证结果（如果启用了验证）
cat swe_bench_output_ducc/<instance_id>_full.json | jq '.validation'
```

### 步骤 5: 清理

```bash
# 关闭 tmux session
tmux kill-session -t swe_bench_<instance_id>

# 或者保留 session 供以后查看
```

## 参考资料

- [SWE-bench 官方网站](https://www.swebench.com/)
- [tmux 官方文档](https://github.com/tmux/tmux/wiki)
- [Docker Python SDK](https://docker-py.readthedocs.io/)

## 总结

本工具提供了两种运行模式：

1. **直接模式**：适合批量评测，效率高
2. **Tmux 模式**：适合调试和学习，可实时查看执行过程

根据你的需求选择合适的模式。推荐在开始时使用 tmux 模式熟悉工具行为，然后使用直接模式进行大规模评测。

开始使用：

```bash
# 快速体验 tmux 模式
python test_tmux_cc_experience.py --index 0 --use-tmux --no-validate

# 在另一个终端
tmux attach -t swe_bench_<instance_id>
```

祝评测顺利！ 🚀
