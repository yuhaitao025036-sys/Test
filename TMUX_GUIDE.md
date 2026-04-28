# 使用 Tmux 运行批处理 - 快速指南

## 🎯 为什么用 Tmux 而不是 Nohup？

| 特性 | Tmux | Nohup |
|------|------|-------|
| **实时查看输出** | ✅ 随时 attach 查看 | ❌ 只能看日志文件 |
| **断线保护** | ✅ 断线后继续运行 | ✅ 断线后继续运行 |
| **交互控制** | ✅ 可以发送命令 | ❌ 无法交互 |
| **多窗口支持** | ✅ 可以分屏、多窗口 | ❌ 单一输出流 |
| **灵活性** | ✅ 可暂停、恢复、调试 | ❌ 启动后无法控制 |
| **学习曲线** | ⚠️ 需要学习基础命令 | ✅ 简单直接 |

---

## 🚀 快速开始

### 方法 1: 使用封装脚本（推荐）

```bash
# 1. 赋予执行权限
chmod +x run_with_tmux.sh batch_manager.sh

# 2. 运行单个批次（0-50）
./run_with_tmux.sh batch_0_50 0 50

# 3. 查看运行情况
tmux attach -t batch_0_50

# 4. 退出查看（任务继续运行）
# 按 Ctrl+B，然后按 D
```

### 方法 2: 使用批量管理器

```bash
# 启动批处理（100个任务，每批50个）
./batch_manager.sh start 100 50

# 查看所有批次状态
./batch_manager.sh status

# 连接到某个批次
./batch_manager.sh attach batch_0_50

# 查看整体进度
./batch_manager.sh progress
```

---

## 📚 完整使用流程

### 1. 启动批处理任务

```bash
# 方式 A: 使用脚本（推荐）
./run_with_tmux.sh batch_0_50 0 50 --no-validate

# 方式 B: 手动创建 tmux session
tmux new-session -d -s batch_0_50
tmux send-keys -t batch_0_50 "python test_tmux_cc_experience.py --start-index 0 --end-index 50" C-m
```

**脚本会自动：**
- ✅ 创建 tmux session
- ✅ 运行 Python 脚本
- ✅ 保存日志到 `logs/batch_0_50.log`
- ✅ 询问是否立即查看

### 2. 查看运行情况

```bash
# 连接到 session
tmux attach -t batch_0_50

# 或使用管理器
./batch_manager.sh attach batch_0_50
```

**在 tmux 中：**
- 可以看到实时输出
- 可以向上滚动查看历史
- 可以复制内容

### 3. 退出查看（不终止任务）

**重要！** 不要直接 Ctrl+C，会终止任务！

正确退出方式：
```
按 Ctrl+B
然后按 D
```

这样你就 **detach** 了，任务继续在后台运行。

### 4. 检查任务状态

```bash
# 列出所有 tmux sessions
tmux ls

# 查看所有批次的详细状态
./batch_manager.sh status

# 查看日志文件
tail -f logs/batch_0_50.log

# 或使用管理器
./batch_manager.sh logs batch_0_50 -f
```

### 5. 多批次并行运行

```bash
# 启动多个批次
./run_with_tmux.sh batch_0_50   0   50  --no-validate
./run_with_tmux.sh batch_50_100 50  100 --no-validate
./run_with_tmux.sh batch_100_150 100 150 --no-validate

# 或使用批量管理器一次启动
./batch_manager.sh start 150 50 --no-validate

# 查看所有批次
tmux ls
```

### 6. 停止任务

```bash
# 停止特定批次
tmux kill-session -t batch_0_50

# 或使用管理器
./batch_manager.sh stop batch_0_50

# 停止所有批次
./batch_manager.sh stopall
```

---

## 🎮 Tmux 必备快捷键

### 基础操作

| 快捷键 | 说明 |
|--------|------|
| `Ctrl+B D` | **退出查看**（不终止任务） |
| `Ctrl+B [` | 进入滚动模式（可以翻页） |
| `Ctrl+B ]` | 粘贴缓冲区内容 |
| `Ctrl+B ?` | 显示所有快捷键 |

### 在滚动模式中

进入滚动模式后（`Ctrl+B [`），可以：

| 按键 | 说明 |
|------|------|
| `↑↓` | 上下滚动 |
| `PageUp/PageDown` | 翻页 |
| `Space` | 开始选择文本 |
| `Enter` | 复制选中文本 |
| `q` | 退出滚动模式 |

### 窗口管理（进阶）

| 快捷键 | 说明 |
|--------|------|
| `Ctrl+B C` | 创建新窗口 |
| `Ctrl+B N` | 切换到下一个窗口 |
| `Ctrl+B P` | 切换到上一个窗口 |
| `Ctrl+B %` | 垂直分屏 |
| `Ctrl+B "` | 水平分屏 |
| `Ctrl+B 方向键` | 在分屏间切换 |

---

## 📊 监控和调试

### 实时监控

```bash
# 方法 1: 直接 attach 到 session
tmux attach -t batch_0_50

# 方法 2: 实时查看日志
tail -f logs/batch_0_50.log

# 方法 3: 使用 watch 命令
watch -n 5 'tail -20 logs/batch_0_50.log'

# 方法 4: 使用管理器
./batch_manager.sh logs batch_0_50 -f
```

### 查看进度

```bash
# 查看所有批次状态
./batch_manager.sh status

# 查看整体进度
./batch_manager.sh progress

# 手动统计已完成任务
ls -1 ./swe_bench_output_ducc/tasks/ | wc -l
```

### 调试问题

```bash
# 1. 连接到有问题的 session
tmux attach -t batch_0_50

# 2. 进入滚动模式查看历史
Ctrl+B [

# 3. 搜索错误（在滚动模式中）
Ctrl+S (然后输入搜索内容)

# 4. 查看完整日志
less logs/batch_0_50.log

# 5. 搜索特定错误
grep -i "error" logs/batch_0_50.log
grep "OSError" logs/batch_0_50.log
```

---

## 🔧 高级技巧

### 1. 在 Tmux 中运行命令

```bash
# 向 session 发送命令（不需要 attach）
tmux send-keys -t batch_0_50 "echo 'Hello'" C-m

# 获取 session 的输出
tmux capture-pane -t batch_0_50 -p

# 保存输出到文件
tmux capture-pane -t batch_0_50 -p > output.txt
```

### 2. 创建多窗口布局

```bash
# 创建带多个窗口的 session
tmux new-session -d -s monitoring
tmux split-window -h -t monitoring  # 垂直分屏
tmux split-window -v -t monitoring  # 水平分屏

# 在不同窗口运行命令
tmux send-keys -t monitoring:0.0 "tail -f logs/batch_0_50.log" C-m
tmux send-keys -t monitoring:0.1 "watch -n 5 'ls -1 ./swe_bench_output_ducc/tasks/ | wc -l'" C-m
tmux send-keys -t monitoring:0.2 "htop" C-m

# 连接查看
tmux attach -t monitoring
```

### 3. Session 配置文件

创建 `~/.tmux.conf`:

```bash
# 启用鼠标支持
set -g mouse on

# 增加历史缓冲区大小
set-option -g history-limit 50000

# 使用更友好的前缀键（可选）
# unbind C-b
# set-option -g prefix C-a
# bind-key C-a send-prefix

# 窗口编号从1开始
set -g base-index 1

# 快速重载配置
bind r source-file ~/.tmux.conf \; display "配置已重载！"
```

重载配置：
```bash
tmux source-file ~/.tmux.conf
```

---

## 📝 常见场景示例

### 场景 1: 长时间运行任务

```bash
# 1. 启动任务
./run_with_tmux.sh long_batch 0 100

# 2. 退出查看（按 Ctrl+B D）

# 3. 关闭 SSH 连接或关闭终端 - 任务继续运行！

# 4. 稍后重新连接
ssh user@server
tmux attach -t long_batch

# 5. 查看进度，然后再次退出
Ctrl+B D
```

### 场景 2: 调试失败的任务

```bash
# 1. 启动任务
./run_with_tmux.sh debug_batch 0 10 --use-tmux

# 2. 实时观察输出
tmux attach -t debug_batch

# 3. 发现错误后，向上滚动查看
Ctrl+B [
# 使用方向键或 PageUp 查看

# 4. 复制错误信息
Space (开始选择)
Enter (复制)

# 5. 粘贴到其他地方
Ctrl+B ]
```

### 场景 3: 同时监控多个批次

```bash
# 创建监控 session
tmux new-session -d -s monitor

# 分成3个窗格
tmux split-window -h -t monitor
tmux split-window -v -t monitor:0.0

# 在每个窗格显示不同批次的日志
tmux send-keys -t monitor:0.0 "tail -f logs/batch_0_50.log" C-m
tmux send-keys -t monitor:0.1 "tail -f logs/batch_50_100.log" C-m
tmux send-keys -t monitor:0.2 "./batch_manager.sh status" C-m

# 连接查看
tmux attach -t monitor
```

---

## 🆚 Nohup vs Tmux - 使用对比

### Nohup 方式（旧）

```bash
# 启动
nohup python test_tmux_cc_experience.py --start-index 0 --end-index 50 > batch.log 2>&1 &

# 查看输出
tail -f batch.log  # 只能看日志文件

# 无法交互
# 无法看到实时彩色输出
# 无法方便地停止
```

### Tmux 方式（新 - 推荐）

```bash
# 启动
./run_with_tmux.sh batch_0_50 0 50

# 查看输出
tmux attach -t batch_0_50  # 看到真实的终端输出

# 可以交互
# 可以看到彩色输出
# 可以随时 Ctrl+C 停止
# 可以发送命令
```

---

## 🎓 学习资源

### Tmux 速查表

```bash
# Session 管理
tmux new -s mysession    # 创建 session
tmux ls                  # 列出 sessions
tmux attach -t mysession # 连接到 session
tmux kill-session -t mysession  # 终止 session

# Detach（最重要！）
Ctrl+B D                 # 退出但保持运行

# 窗口管理
Ctrl+B C                 # 新窗口
Ctrl+B ,                 # 重命名窗口
Ctrl+B W                 # 列出窗口
Ctrl+B N/P               # 下一个/上一个窗口

# 分屏
Ctrl+B %                 # 垂直分屏
Ctrl+B "                 # 水平分屏
Ctrl+B 方向键            # 切换分屏
Ctrl+B X                 # 关闭当前分屏
```

### 在线资源

- **官方文档**: `man tmux`
- **速查表**: https://tmuxcheatsheet.com
- **教程**: https://github.com/tmux/tmux/wiki

---

## ✅ 最佳实践总结

1. **✅ 使用有意义的 session 名称**
   ```bash
   # 好
   ./run_with_tmux.sh batch_0_50 0 50
   
   # 不好
   tmux new -s s1
   ```

2. **✅ 定期查看状态**
   ```bash
   ./batch_manager.sh status
   ```

3. **✅ 保存日志**
   - 脚本自动保存到 `logs/` 目录
   - 便于事后分析

4. **✅ 退出时用 Ctrl+B D**
   - 不要用 Ctrl+C（会终止任务）

5. **✅ 使用管理脚本**
   ```bash
   ./batch_manager.sh start 100 50
   ```

6. **✅ 多批次并行**
   - 充分利用资源
   - 注意监控资源使用

---

## 🚀 现在开始！

```bash
# 1. 赋予执行权限
chmod +x run_with_tmux.sh batch_manager.sh

# 2. 测试单个任务
./run_with_tmux.sh test_batch 0 5

# 3. 查看运行情况
tmux attach -t test_batch

# 4. 退出查看（Ctrl+B D）

# 5. 运行完整批次
./batch_manager.sh start 100 50 --no-validate

# 6. 享受更好的批处理体验！
```

**祝你使用愉快！** 🎉

有问题？使用 `./batch_manager.sh help` 查看帮助。
