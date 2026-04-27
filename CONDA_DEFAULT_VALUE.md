# Conda 环境默认值配置

## 问题

如果没有激活任何 conda 环境（`CONDA_DEFAULT_ENV` 未设置），tmux 模式下会找不到 ducc。

## 解决方案 ✅

**现在有默认值了！** 如果未激活 conda 环境，脚本会自动尝试激活 `dejavu` 环境。

## 使用场景

### 场景 1：已激活 conda 环境（推荐）

```bash
# 激活你的环境
conda activate dejavu

# 运行脚本（会使用当前环境）
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate

# 输出：
#   检测到当前 conda 环境: dejavu
#   ✓ conda 环境激活成功: dejavu
```

### 场景 2：未激活环境（使用默认值）

```bash
# 没有激活任何环境
# 直接运行脚本（会自动尝试激活 dejavu）
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate

# 输出：
# 💡 将使用默认 conda 环境: dejavu
#   使用默认 conda 环境: dejavu
#   ✓ conda 环境激活成功: dejavu
```

### 场景 3：指定其他默认环境

```bash
# 指定使用 myenv 环境
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate \
  --conda-env myenv

# 输出：
# 💡 将使用默认 conda 环境: myenv
#   使用默认 conda 环境: myenv
#   ✓ conda 环境激活成功: myenv
```

## 环境优先级

脚本按以下优先级选择 conda 环境：

```
1. CONDA_DEFAULT_ENV（当前激活的环境）    ← 最高优先级
2. --conda-env 参数（命令行指定）
3. 硬编码默认值 'dejavu'                   ← 最低优先级
```

### 示例

```bash
# 1. 已激活环境 → 使用 current_env
conda activate current_env
python3 test_tmux_cc_experience.py --use-tmux --index 0 --conda-env myenv
# 结果: 使用 current_env（忽略 --conda-env）

# 2. 未激活环境 + 指定参数 → 使用 myenv
python3 test_tmux_cc_experience.py --use-tmux --index 0 --conda-env myenv
# 结果: 使用 myenv

# 3. 未激活环境 + 不指定参数 → 使用 dejavu
python3 test_tmux_cc_experience.py --use-tmux --index 0
# 结果: 使用 dejavu（默认值）
```

## 命令行参数

### --conda-env

指定 tmux 模式下使用的 conda 环境名称。

```bash
# 语法
python3 test_tmux_cc_experience.py --use-tmux --conda-env <环境名> [其他参数]

# 示例
python3 test_tmux_cc_experience.py --use-tmux --conda-env myenv --index 0 --no-validate
```

**默认值**：`dejavu`

**何时生效**：
- ✅ 使用 `--use-tmux` 参数时
- ✅ 当前未激活任何 conda 环境时
- ❌ 已激活环境时无效（会使用已激活的环境）

## 配置方法

### 方法 1：使用命令行参数（推荐）

```bash
# 指定环境名
python3 test_tmux_cc_experience.py --use-tmux --conda-env your_env --index 0
```

### 方法 2：修改代码中的默认值

编辑 `test_tmux_cc_experience.py`：

```python
# 找到这一行（约第 1429 行）
parser.add_argument('--conda-env', type=str, default='dejavu',

# 修改为你的默认环境
parser.add_argument('--conda-env', type=str, default='your_env',
```

### 方法 3：设置环境变量

```bash
# 临时设置
export DEFAULT_CONDA_ENV=your_env
python3 test_tmux_cc_experience.py --use-tmux --index 0

# 永久设置（添加到 ~/.bashrc 或 ~/.zshrc）
echo 'export DEFAULT_CONDA_ENV=your_env' >> ~/.bashrc
source ~/.bashrc
```

## 完整示例

### 示例 1：推荐的使用方式

```bash
# 激活你的工作环境
conda activate dejavu

# 运行脚本（会自动使用 dejavu）
python3 test_tmux_cc_experience.py --max-tasks 2 --use-tmux --no-validate

# 查看 tmux session
tmux list-sessions
tmux attach -t swe_bench_xxx
```

### 示例 2：快速测试（不激活环境）

```bash
# 直接运行（会尝试激活默认的 dejavu 环境）
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate

# 如果 dejavu 环境存在且包含 ducc，会正常工作
```

### 示例 3：使用不同环境

```bash
# 方式 A: 激活环境后运行
conda activate myenv
python3 test_tmux_cc_experience.py --use-tmux --index 0

# 方式 B: 不激活，但指定环境
python3 test_tmux_cc_experience.py --use-tmux --conda-env myenv --index 0
```

## 检查环境是否可用

在运行前，可以先检查环境是否存在：

```bash
# 列出所有 conda 环境
conda env list

# 检查特定环境
conda env list | grep dejavu

# 激活并检查 ducc
conda activate dejavu
which ducc
ducc --version
```

## 故障排查

### 问题 1：环境不存在

**错误信息**：
```
⚠️  环境激活可能失败，继续尝试...
Could not find conda environment: dejavu
```

**解决方案**：
```bash
# 方案 A: 创建 dejavu 环境
conda create -n dejavu python=3.9
conda activate dejavu
# 安装 ducc...

# 方案 B: 使用现有环境
conda env list  # 查看可用环境
python3 test_tmux_cc_experience.py --use-tmux --conda-env your_existing_env --index 0
```

### 问题 2：环境中没有 ducc

**错误信息**：
```
✓ conda 环境激活成功: dejavu
ducc: command not found
```

**解决方案**：
```bash
# 在环境中安装 ducc
conda activate dejavu
# 安装 ducc 的命令...

# 或使用绝对路径
export DUCC_BIN="/path/to/ducc"
python3 test_tmux_cc_experience.py --use-tmux --index 0
```

### 问题 3：想在直接模式下使用

**说明**：`--conda-env` 参数只在 tmux 模式下有效。

```bash
# ✅ tmux 模式 - 参数生效
python3 test_tmux_cc_experience.py --use-tmux --conda-env myenv --index 0

# ❌ 直接模式 - 参数被忽略（使用当前 shell 环境）
python3 test_tmux_cc_experience.py --conda-env myenv --index 0
```

在直接模式下，请先激活环境：
```bash
conda activate myenv
python3 test_tmux_cc_experience.py --index 0
```

## 工作流程图

```
开始运行 --use-tmux
    ↓
检查 CONDA_DEFAULT_ENV
    ↓
是否已设置？
    ├─ 是 → 使用当前环境
    └─ 否 → 检查 --conda-env 参数
              ├─ 已指定 → 使用指定环境
              └─ 未指定 → 使用默认值 'dejavu'
    ↓
在 tmux 中激活环境
    ↓
验证激活成功
    ↓
运行 ducc
```

## 最佳实践

### ✅ 推荐做法

1. **明确激活环境**（最可靠）
   ```bash
   conda activate dejavu
   python3 test_tmux_cc_experience.py --use-tmux --index 0
   ```

2. **使用命令行参数**（灵活）
   ```bash
   python3 test_tmux_cc_experience.py --use-tmux --conda-env myenv --index 0
   ```

3. **批量处理时设置环境**
   ```bash
   conda activate dejavu
   for i in {0..9}; do
       python3 test_tmux_cc_experience.py --use-tmux --index $i --no-validate
   done
   ```

### ⚠️ 注意事项

1. **环境必须存在**：确保指定的环境已创建
2. **环境必须包含 ducc**：确保在环境中安装了 ducc
3. **验证环境**：首次使用前手动测试环境

## 快速测试

```bash
# 1. 测试当前环境
conda activate dejavu
which ducc
ducc --version

# 2. 测试脚本
python3 test_directory_creation.py  # 不需要真实运行

# 3. 运行一个简单任务
python3 test_tmux_cc_experience.py --use-tmux --index 0 --no-validate

# 4. 查看 tmux
tmux list-sessions
tmux attach -t swe_bench_xxx
```

## 总结

### 主要改进

1. ✅ **自动使用默认环境**：未激活时自动尝试 `dejavu`
2. ✅ **命令行可配置**：可通过 `--conda-env` 指定其他环境
3. ✅ **智能优先级**：已激活环境 > 命令行参数 > 默认值
4. ✅ **清晰的日志**：明确显示使用哪个环境

### 使用建议

```bash
# 最简单的方式（依赖默认值）
python3 test_tmux_cc_experience.py --use-tmux --index 0

# 最可靠的方式（明确激活）
conda activate dejavu
python3 test_tmux_cc_experience.py --use-tmux --index 0

# 最灵活的方式（指定环境）
python3 test_tmux_cc_experience.py --use-tmux --conda-env myenv --index 0
```

现在即使不设置 `CONDA_DEFAULT_ENV`，脚本也会自动尝试使用 `dejavu` 环境！
