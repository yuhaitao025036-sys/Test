# 快速开始指南

## 修改完成 ✅

已成功将 `test_tmux_cc_experience.py` 与 tmux 集成，现在可以实时查看 ducc 的执行过程！

## 新增功能

### 1. Tmux 模式
通过添加 `--use-tmux` 参数，你可以：
- 🔍 实时查看 ducc 的执行过程
- 📊 观察 ducc 的思考和文件操作
- 🐛 方便调试和理解执行逻辑

### 2. 保持原有功能
不使用 `--use-tmux` 时，脚本行为完全不变（直接模式）

## 使用方法

### 方式一：直接模式（原有方式）

```bash
# 批量运行，不需要查看执行过程
python3 test_tmux_cc_experience.py --max-tasks 2 --no-validate
```

### 方式二：Tmux 模式（新增）⭐

```bash
# Terminal 1: 运行脚本
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate

# 会显示类似以下信息：
# ============================================================
# 启动 tmux session: swe_bench_django__django_12345_1735286400
# 工作目录: /tmp/swe_bench_xyz/workspace
# 查看执行过程: tmux attach -t swe_bench_django__django_12345_1735286400
# ============================================================
```

```bash
# Terminal 2: 连接查看实时执行
tmux attach -t swe_bench_django__django_12345_1735286400

# 你会看到 ducc 的实时界面：
# - Thinking...（思考中）
# - Reading file.py...（读取文件）
# - Editing file.py...（编辑文件）
# - 生成的 patch
```

### 断开连接（不中断执行）

在 tmux 窗口内按：`Ctrl-b` 然后按 `d`

### 查看所有活跃的任务

```bash
tmux list-sessions
```

### 关闭 session

```bash
# 关闭特定任务
tmux kill-session -t swe_bench_django__django_12345

# 关闭所有 swe_bench 任务
tmux list-sessions | grep swe_bench | cut -d: -f1 | xargs -I {} tmux kill-session -t {}
```

## 完整命令示例

```bash
# 1. 直接模式运行（原有方式）
python3 test_tmux_cc_experience.py --max-tasks 2 --no-validate

# 2. Tmux 模式运行单个任务（推荐用于调试）
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate

# 3. Tmux 模式 + 验证
python3 test_tmux_cc_experience.py --index 0 --use-tmux

# 4. 批量 + Tmux 模式（会创建多个 session）
python3 test_tmux_cc_experience.py --max-tasks 5 --use-tmux --no-validate
```

## 查看帮助

```bash
python3 test_tmux_cc_experience.py --help
```

## 文档

已创建以下文档供参考：

1. **SWE_BENCH_TMUX_USAGE.md** - 详细使用指南
   - 安装说明
   - 完整使用教程
   - 常见问题解答
   - 高级技巧

2. **TEST_TMUX_INTEGRATION.md** - 技术文档
   - 修改内容总结
   - 测试指南
   - 代码审查要点

## 推荐使用场景

### 场景 1: 调试单个失败任务
```bash
python3 test_tmux_cc_experience.py --index 5 --use-tmux --no-validate
# 然后连接查看为什么失败
tmux attach -t swe_bench_xxx
```

### 场景 2: 学习 ducc 的工作方式
```bash
# 选一个简单任务，观察 ducc 如何分析和修复
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate
tmux attach -t swe_bench_xxx
```

### 场景 3: 批量评测
```bash
# 使用直接模式，效率更高
python3 test_tmux_cc_experience.py --max-tasks 10 --no-validate
```

## 对比

| 特性 | 直接模式 | Tmux 模式 |
|------|---------|----------|
| 实时查看 | ❌ | ✅ |
| 批量运行 | ✅ 推荐 | ⚠️ 会创建多个 session |
| 调试方便 | ❌ | ✅ |
| 运行效率 | 快 | 略慢 |

## 环境要求

- Python 3.x
- tmux（使用 tmux 模式时需要）
- Docker
- ducc 或 baidu-cc

## 安装 tmux

```bash
# macOS
brew install tmux

# Ubuntu/Debian
sudo apt-get install tmux

# CentOS/RHEL
sudo yum install tmux
```

## 常见问题

### Q: 找不到 ducc？
```bash
export DUCC_BIN=/path/to/your/ducc
```

### Q: Session 不会自动关闭？
这是设计行为，方便你查看结果。手动关闭：
```bash
tmux kill-session -t swe_bench_xxx
```

### Q: 如何查看历史输出？
在 tmux 内按 `Ctrl-b [` 进入滚动模式，用方向键查看，按 `q` 退出。

## 总结

现在你可以：
- ✅ 使用原有的直接模式批量运行
- ✅ 使用新的 tmux 模式实时查看执行
- ✅ 在两种模式间灵活切换

开始使用：

```bash
# 快速体验 tmux 模式
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate

# 在另一个终端查看
tmux attach -t swe_bench_<显示的_session_name>
```

享受实时监控 ducc 执行的体验！ 🚀
