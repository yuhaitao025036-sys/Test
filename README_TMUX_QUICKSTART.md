# 🚀 快速开始：使用 Tmux 运行批处理

> **TL;DR**: Tmux 比 nohup 更好用！可以随时查看输出，不用再盯着日志文件。

---

## ⚡ 30秒快速开始

```bash
# 1. 赋予执行权限（只需一次）
chmod +x run_with_tmux.sh batch_manager.sh

# 2. 运行第一批任务（0-50）
./run_with_tmux.sh batch_0_50 0 50

# 3. 想看输出？随时连接
tmux attach -t batch_0_50

# 4. 不想看了？按 Ctrl+B 然后按 D
# 任务继续在后台运行！
```

**就这么简单！** 🎉

---

## 📚 三种使用方式

### 方式 1: 单个批次（最简单）

```bash
# 运行任务 0-50
./run_with_tmux.sh batch_0_50 0 50

# 查看运行情况
tmux attach -t batch_0_50
```

### 方式 2: 多个批次（推荐）

```bash
# 自动启动多个批次（100个任务，每批50个）
./batch_manager.sh start 100 50

# 查看所有批次状态
./batch_manager.sh status

# 连接到任意批次
./batch_manager.sh attach batch_0_50
```

### 方式 3: 自定义批次

```bash
# 第一批
./run_with_tmux.sh my_batch1 0 30 --no-validate

# 第二批
./run_with_tmux.sh my_batch2 30 60 --timeout 1800

# 第三批
./run_with_tmux.sh my_batch3 60 100
```

---

## 🎮 必记的3个快捷键

| 操作 | 快捷键 | 说明 |
|------|--------|------|
| **退出查看** | `Ctrl+B` 然后 `D` | 最重要！不会终止任务 |
| **向上滚动** | `Ctrl+B` 然后 `[` | 查看历史输出 |
| **退出滚动** | `q` | 返回正常模式 |

**注意：** 不要用 `Ctrl+C`，会终止任务！

---

## 📋 常用命令

### 查看和管理

```bash
# 列出所有运行中的批次
tmux ls

# 或使用管理器
./batch_manager.sh list

# 查看批次状态
./batch_manager.sh status

# 查看日志
./batch_manager.sh logs batch_0_50

# 实时查看日志
./batch_manager.sh logs batch_0_50 -f
```

### 停止任务

```bash
# 停止特定批次
./batch_manager.sh stop batch_0_50

# 或
tmux kill-session -t batch_0_50

# 停止所有批次
./batch_manager.sh stopall
```

---

## 💪 与 Nohup 对比

### 之前（Nohup）

```bash
# 启动
nohup python ... > batch.log 2>&1 &

# 想看进度
tail -f batch.log  # 😢 只能看日志文件，没有颜色

# 想停止
ps aux | grep python
kill 12345  # 😢 需要找 PID
```

### 现在（Tmux）

```bash
# 启动
./run_with_tmux.sh batch_0_50 0 50

# 想看进度
tmux attach -t batch_0_50  # 😊 真实终端，有颜色！

# 想停止
./batch_manager.sh stop batch_0_50  # 😊 简单直接
```

**更简单、更强大、更友好！**

---

## 🔥 实战示例

### 示例 1: 运行单个批次并监控

```bash
# 启动
./run_with_tmux.sh batch_0_50 0 50

# 去做其他事情...

# 稍后查看进度
tmux attach -t batch_0_50

# 看完了，退出（按 Ctrl+B D）

# 任务继续运行！
```

### 示例 2: 并行运行多个批次

```bash
# 启动3个批次
./batch_manager.sh start 150 50

# 查看状态
./batch_manager.sh status

# 输出示例:
# Session              任务范围        状态       最近日志
# --------------------------------------------------------------------------------
# batch_0_50          [0-50)         运行中     ✓ 处理完成: 25/50
# batch_50_100        [50-100)       运行中     正在提取代码库...
# batch_100_150       [100-150)      运行中     ✓ Patch 已保存

# 查看某个批次
./batch_manager.sh attach batch_0_50
```

### 示例 3: 断线后恢复

```bash
# 在服务器上启动任务
./run_with_tmux.sh long_task 0 100

# SSH 断线了！别担心，任务还在运行

# 重新连接服务器
ssh user@server

# 恢复查看
tmux attach -t long_task

# 继续工作！
```

---

## 🆘 常见问题

### Q: 如何退出 tmux 不终止任务？

**A:** 按 `Ctrl+B`，然后按 `D`

**错误方式:** 直接 `Ctrl+C`（会终止任务）

### Q: 如何查看历史输出？

**A:** 
1. 按 `Ctrl+B` 然后按 `[` 进入滚动模式
2. 使用方向键或 PageUp/PageDown 滚动
3. 按 `q` 退出滚动模式

### Q: 忘记了 session 名称怎么办？

**A:** 
```bash
# 列出所有 sessions
tmux ls

# 或
./batch_manager.sh list
```

### Q: 如何同时监控多个批次？

**A:** 
```bash
# 方法1: 使用管理器查看状态
./batch_manager.sh status

# 方法2: 创建监控窗口（高级）
tmux new -s monitor
tmux split-window -h
# 在不同窗格运行 attach 命令
```

### Q: Tmux 是否比 Nohup 更占资源？

**A:** 几乎没有额外开销。Tmux 本身非常轻量级。

---

## 📖 详细文档

- **完整 Tmux 指南**: [TMUX_GUIDE.md](TMUX_GUIDE.md)
- **Nohup 对比**: [NOHUP_VS_TMUX.md](NOHUP_VS_TMUX.md)
- **批处理指南**: [BATCH_PROCESSING_GUIDE.md](BATCH_PROCESSING_GUIDE.md)

---

## 🎯 最佳实践

### ✅ 推荐做法

1. **使用语义化的 session 名称**
   ```bash
   ./run_with_tmux.sh batch_0_50 0 50  # 好
   tmux new -s s1  # 不好
   ```

2. **使用管理脚本**
   ```bash
   ./batch_manager.sh start 100 50  # 简单
   ```

3. **定期查看状态**
   ```bash
   ./batch_manager.sh status
   ```

4. **保存日志**
   - 脚本自动保存到 `logs/` 目录
   - 无需手动重定向

### ❌ 避免的做法

1. **不要用 Ctrl+C 退出查看**
   - 正确方式：`Ctrl+B` 然后 `D`

2. **不要直接 kill 进程**
   ```bash
   # ❌ 不好
   ps aux | grep python
   kill 12345
   
   # ✅ 好
   ./batch_manager.sh stop batch_0_50
   ```

3. **不要忘记退出滚动模式**
   - 如果按键没反应，可能在滚动模式
   - 按 `q` 退出

---

## 🚀 现在就开始！

```bash
# 1. 测试单个任务
./run_with_tmux.sh test_batch 0 5

# 2. 查看运行情况
tmux attach -t test_batch

# 3. 退出查看（Ctrl+B D）

# 4. 确认无误后，运行完整批次
./batch_manager.sh start 100 50

# 5. 享受更好的批处理体验！
```

---

## 🎁 额外工具

我们还提供了这些工具：

### 1. 失败分析工具
```bash
python analyze_failures.py --log batch.log --preds all_preds.jsonl
```

查看哪些任务失败了，失败原因是什么。

### 2. 进度监控
```bash
./batch_manager.sh progress
```

查看整体进度和各批次状态。

---

## 💬 需要帮助？

```bash
# 查看帮助
./batch_manager.sh help

# 查看 Tmux 帮助
man tmux

# 或在 Tmux 中按
Ctrl+B ?
```

---

**Happy Batching! 🎉**

*有任何问题？查看 [TMUX_GUIDE.md](TMUX_GUIDE.md) 获取详细教程。*
