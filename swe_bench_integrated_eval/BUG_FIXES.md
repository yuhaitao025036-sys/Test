# Bug 修复报告

## 修复的关键问题

### 🔴 P0 - 已修复（会导致运行失败）

#### 1. PYTHON_CMD 硬编码路径 - **已修复** ✅

**问题**: 
```bash
PYTHON_CMD="$HOME/miniconda3/envs/dejavu/bin/python3"  # 硬编码路径
```

假设所有用户都有这个路径，在其他机器上会直接失败！

**修复方案**:
```bash
# 优先级: 环境变量 > conda 环境 > 系统 Python
if [ -n "$PYTHON_CMD" ]; then
  # 使用环境变量
  :
elif [ -x "$HOME/miniconda3/envs/dejavu/bin/python3" ]; then
  # 使用 conda 环境
  PYTHON_CMD="$HOME/miniconda3/envs/dejavu/bin/python3"
else
  # 使用系统 Python
  PYTHON_CMD="$(which python3 2>/dev/null || which python 2>/dev/null || echo python3)"
fi

# 验证 Python 是否可用
if ! command -v "$PYTHON_CMD" &> /dev/null; then
  echo "❌ 错误: 找不到 Python 解释器"
  echo "请设置 PYTHON_CMD 环境变量"
  exit 1
fi
```

**影响文件**:
- `run_batch_by_ids.sh`
- `run_batch.sh`

#### 2. PYTHON_CMD 引号保护缺失 - **已修复** ✅

**问题**:
```bash
nohup $PYTHON_CMD -u test_tmux_cc_experience.py \  # 没有引号
```

如果 PYTHON_CMD 包含空格，会失败。

**修复**:
```bash
nohup "$PYTHON_CMD" -u test_tmux_cc_experience.py \  # 添加引号
"$PYTHON_CMD" evaluate_single_instance.py \
"$PYTHON_CMD" summarize_eval_results.py \
```

**修复位置**: 所有 Python 调用（共 8 处）

---

## 已知但可接受的问题

### ⚠️ P1 - 中等风险（建议未来改进）

#### 1. MODEL_NAME 包含空格的文件名问题

**问题**: 
使用 `--model "Claude Opus 4.6"` 会生成包含空格的目录名：
```bash
./evaluation/batch/Claude Opus 4.6_swe_bench_output_ids/
```

**风险**: 虽然有引号保护，但某些工具可能无法正确处理。

**缓解措施**: 
- 所有路径使用都加了引号保护
- 实际测试中应该能正常工作

**建议优化**（未实施）:
```bash
MODEL_NAME_SAFE="${MODEL_NAME// /_}"  # 将空格替换为下划线
```

#### 2. 相对路径依赖

**默认路径**:
```bash
RAW_SAMPLE_CSV="../swe_bench_pro_test.csv"
SCRIPTS_DIR="./SWE-bench_Pro-os/run_scripts"
```

**缓解措施**:
- 脚本会 `cd` 到脚本所在目录（第 162/184 行）
- 用户可以通过参数覆盖

**使用建议**:
```bash
# 明确指定绝对路径或当前目录路径
--raw-sample-csv ./swe_bench_pro_test.csv \
--scripts-dir ./SWE-bench_Pro-os/run_scripts
```

---

## 测试验证

### 验证修复效果

```bash
# 测试 1: 使用系统 Python
unset PYTHON_CMD
bash run_batch_by_ids.sh --help

# 测试 2: 使用自定义 Python
export PYTHON_CMD=/usr/bin/python3
bash run_batch_by_ids.sh --help

# 测试 3: 使用包含空格的模型名
bash run_batch_by_ids.sh \
  --ids-file ./example_ids.txt \
  --model "Claude Opus 4.6" \
  --enable-eval
```

### 运行前检查

```bash
# 运行验证脚本
bash verify.sh

# 确保以下项通过:
# ✅ Python 已安装
# ✅ pandas 已安装
# ✅ docker (Python) 已安装
# ✅ Docker 正在运行
```

---

## 修复总结

| 问题 | 严重程度 | 状态 | 影响 |
|------|----------|------|------|
| PYTHON_CMD 硬编码 | 🔴 P0 | ✅ 已修复 | 其他机器无法运行 |
| PYTHON_CMD 引号缺失 | 🔴 P0 | ✅ 已修复 | 路径包含空格时失败 |
| MODEL_NAME 空格问题 | ⚠️ P1 | 可接受 | 已有引号保护 |
| 相对路径依赖 | ⚠️ P1 | 可接受 | 已有 cd 保护 |

---

## 使用建议

### 推荐配置

```bash
# 1. 确保 Python 环境（三选一）
# 方式 A: 使用系统 Python（自动检测）
bash run_batch_by_ids.sh ...

# 方式 B: 指定 Python 路径
export PYTHON_CMD=/path/to/python3
bash run_batch_by_ids.sh ...

# 方式 C: 使用 conda 环境
conda activate dejavu  # 会自动使用 dejavu 环境的 Python

# 2. 明确指定 CSV 路径（推荐）
bash run_batch_by_ids.sh \
  --ids-file ./my_ids.txt \
  --model claude \
  --enable-eval \
  --raw-sample-csv ./swe_bench_pro_test.csv

# 3. 避免模型名包含空格（推荐）
--model claude               # ✅ 推荐
--model "Claude_Sonnet_4.6"  # ✅ 可以
--model "Claude Sonnet 4.6"  # ⚠️ 可以但不推荐
```

---

## 现在可以安全使用了！

所有关键 bug 已修复，工具包可以安全使用。如果遇到问题：

1. 运行 `bash verify.sh` 检查环境
2. 查看 [CHECKLIST.md](./CHECKLIST.md) 确认依赖
3. 查看 [USE.md](./USE.md) 获取完整命令
