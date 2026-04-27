# 测试 Tmux 集成的修改

## 修改内容总结

已成功将 `test_tmux_cc_experience.py` 与 `tmux_cc/test_tmux_cc.py` 集成，现在支持两种运行模式：

### 1. 直接模式（原有方式）
- 直接调用 ducc 命令行
- 适合批量评测
- 运行效率高

### 2. Tmux 模式（新增）
- 在 tmux session 中运行 ducc
- 可以实时查看执行过程
- 适合调试和学习

## 主要修改

### 文件：`test_tmux_cc_experience.py`

#### 1. 修改了 `SimpleDuccEvaluator.__init__()` 方法
添加了 `use_tmux` 参数：
```python
def __init__(self, use_tmux=False):
    self.docker_client = None
    self._container_cache = {}
    self.ducc_bin = find_ducc_binary()
    self.use_tmux = use_tmux  # 新增
```

#### 2. 重构了 `call_ducc()` 方法
现在支持两种调用方式：
```python
def call_ducc(self, prompt: str, workspace: str, timeout: int = 600, 
              use_tmux: bool = False, instance_id: str = "") -> str:
    if use_tmux:
        return self._call_ducc_tmux(prompt, workspace, timeout, instance_id)
    else:
        return self._call_ducc_direct(prompt, workspace, timeout)
```

#### 3. 新增了 `_call_ducc_direct()` 方法
保留原有的直接调用逻辑

#### 4. 新增了 `_call_ducc_tmux()` 方法
实现 tmux 模式调用：
- 创建 tmux session
- 启动 ducc
- 自动确认提示
- 发送 prompt
- 监控执行完成

#### 5. 新增了辅助方法
- `_tmux_capture_pane()`: 捕获 tmux 内容
- `_wait_for_ducc_completion()`: 等待 ducc 完成执行

#### 6. 更新了命令行参数
添加了 `--use-tmux` 参数：
```python
parser.add_argument('--use-tmux', action='store_true',
                   help='使用 tmux 模式运行 ducc (可通过 tmux attach 查看实时执行)')
```

## 使用方法

### 快速测试语法

```bash
# 检查语法是否正确
python3 -m py_compile test_tmux_cc_experience.py

# 查看帮助信息（需要先安装依赖）
python3 test_tmux_cc_experience.py --help
```

### 运行示例

#### 直接模式（原有方式）
```bash
python3 test_tmux_cc_experience.py --max-tasks 2 --no-validate
```

#### Tmux 模式（新增）
```bash
# Terminal 1: 运行脚本
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate

# Terminal 2: 查看执行过程
tmux attach -t swe_bench_<instance_id>
```

## 验证清单

### ✅ 已完成的修改

1. [x] 分析 `tmux_cc/test_tmux_cc.py` 的实现方式
2. [x] 修改 `SimpleDuccEvaluator` 类支持 tmux 模式
3. [x] 实现 `_call_ducc_tmux()` 方法
4. [x] 实现 tmux 监控和自动确认机制
5. [x] 更新命令行参数
6. [x] 更新文档和帮助信息
7. [x] 语法检查通过

### 📋 需要实际测试的功能

由于需要完整的运行环境（Docker、数据集等），以下功能需要在实际环境中测试：

1. [ ] 直接模式是否正常工作（回归测试）
2. [ ] Tmux 模式能否正确创建 session
3. [ ] Tmux 模式能否正确启动 ducc
4. [ ] 自动确认机制是否工作
5. [ ] Prompt 是否正确发送
6. [ ] 执行监控是否准确检测完成
7. [ ] 输出是否正确捕获和提取

## 测试建议

### 环境准备

```bash
# 1. 安装依赖
pip install docker datasets

# 2. 确保 tmux 已安装
tmux -V

# 3. 确保 ducc 可用
which ducc
# 或
export DUCC_BIN=/path/to/ducc

# 4. 准备数据集
export SWE_BENCH_DATASET=/path/to/dataset.parquet

# 5. 确保 Docker 运行
docker ps
```

### 测试步骤

#### 测试 1: 验证命令行参数

```bash
cd /Users/yuhaitao01/dev/baidu/explore/test

# 查看帮助
python3 test_tmux_cc_experience.py --help

# 应该看到 --use-tmux 参数说明
```

#### 测试 2: 直接模式（确保没有破坏原有功能）

```bash
# 运行一个简单任务
python3 test_tmux_cc_experience.py --index 0 --no-validate

# 检查输出目录
ls -la swe_bench_output_ducc/
```

#### 测试 3: Tmux 模式基础功能

```bash
# Terminal 1: 启动任务
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate

# 观察输出，应该看到：
# - "启动 tmux session: swe_bench_xxx"
# - "查看执行过程: tmux attach -t swe_bench_xxx"
```

```bash
# Terminal 2: 连接到 session
tmux attach -t swe_bench_xxx

# 应该能看到 ducc 的执行界面
```

#### 测试 4: 检查 Session 状态

```bash
# 列出所有活跃的 session
tmux list-sessions

# 应该看到 swe_bench_ 开头的 session
```

#### 测试 5: 验证输出

```bash
# 检查是否生成了结果文件
cat swe_bench_output_ducc/<instance_id>_full.json | jq .

# 检查 patch 是否被正确提取
cat swe_bench_output_ducc/<instance_id>_full.json | jq '.patch'
```

#### 测试 6: 清理

```bash
# 关闭测试的 session
tmux kill-session -t swe_bench_xxx
```

## 常见问题排查

### 问题 1: ModuleNotFoundError: No module named 'docker'

```bash
pip install docker
```

### 问题 2: ModuleNotFoundError: No module named 'datasets'

```bash
pip install datasets
```

### 问题 3: tmux: command not found

```bash
# macOS
brew install tmux

# Ubuntu/Debian
sudo apt-get install tmux
```

### 问题 4: 找不到 ducc

```bash
# 设置环境变量
export DUCC_BIN=/path/to/ducc

# 或安装 ducc
bash <(curl -fsSL http://baidu-cc-client.bj.bcebos.com/baidu-cc/install.sh)
```

### 问题 5: 找不到数据集

```bash
# 下载数据集或设置路径
export SWE_BENCH_DATASET=/path/to/test-00000-of-00001.parquet
```

### 问题 6: Session 创建失败

```bash
# 检查是否有同名 session
tmux list-sessions

# 如有冲突，关闭旧的
tmux kill-session -t <session_name>
```

## 代码审查要点

### 关键修改点

1. **向后兼容**: 默认不使用 tmux，保持原有行为
2. **错误处理**: tmux 模式失败时有适当的错误信息
3. **资源清理**: session 保持活跃供用户查看（这是设计决策）
4. **超时控制**: tmux 模式也有超时机制
5. **输出格式**: 两种模式的输出格式应该一致

### 潜在改进

1. **Session 自动清理**: 可以添加选项在任务完成后自动关闭 session
2. **并发控制**: 批量运行时限制同时打开的 session 数量
3. **日志记录**: 将 tmux 输出保存到文件供后续分析
4. **错误恢复**: 如果 tmux 意外断开，能够重连或恢复

## 文档

已创建以下文档：

1. **SWE_BENCH_TMUX_USAGE.md**: 详细的使用指南
   - 安装说明
   - 快速开始
   - 使用场景
   - 常见问题
   - 高级技巧

2. **TEST_TMUX_INTEGRATION.md**: 本文档
   - 修改总结
   - 测试指南
   - 问题排查

## 下一步

建议按以下顺序测试：

1. ✅ 语法检查（已通过）
2. ⏳ 安装依赖
3. ⏳ 测试命令行参数
4. ⏳ 测试直接模式（回归测试）
5. ⏳ 测试 tmux 模式基础功能
6. ⏳ 测试完整流程（含验证）
7. ⏳ 性能测试（批量任务）

## 总结

本次修改成功将 tmux 集成功能添加到 SWE-bench 评测脚本中，在保持原有功能的同时，提供了实时监控 ducc 执行的能力。这对于调试、学习和理解 ducc 的行为非常有帮助。

主要特点：
- ✅ 向后兼容
- ✅ 灵活切换（直接/tmux 模式）
- ✅ 自动确认机制
- ✅ 完整文档
- ✅ 语法正确

可以通过以下命令开始使用：

```bash
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate
```
