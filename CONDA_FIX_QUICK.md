# 快速修复：Tmux 模式下 Conda 环境激活

## 问题
在 tmux 模式下，ducc 命令找不到，因为没有激活 conda 环境。

## 解决方案 ✅

**已修复！** 脚本现在会自动激活 conda 环境。

## 使用方法

### 1. 激活你的 conda 环境

```bash
conda activate dejavu
```

### 2. 运行脚本（会自动在 tmux 中激活相同环境）

```bash
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate
```

### 3. 查看输出确认激活成功

```
✓ tmux session 已创建
  检测到 conda 环境: dejavu
  ✓ 使用 conda.sh 初始化: /path/to/conda/etc/profile.d/conda.sh
  ✓ conda 环境激活成功
✓ ducc 命令已发送
```

## 工作原理

脚本会自动：

1. 检测当前 conda 环境（`$CONDA_DEFAULT_ENV`）
2. 找到 `conda.sh` 初始化脚本
3. 在 tmux 中执行：`source conda.sh && conda activate dejavu`
4. 验证环境激活成功

## 故障排查

### 如果还是找不到 ducc

#### 方案 1: 使用绝对路径（最可靠）

```bash
# 1. 找到 ducc 路径
conda activate dejavu
which ducc
# 输出: /home/user/anaconda3/envs/dejavu/bin/ducc

# 2. 设置环境变量
export DUCC_BIN="/home/user/anaconda3/envs/dejavu/bin/ducc"

# 3. 运行脚本
python3 test_tmux_cc_experience.py --use-tmux --index 0
```

#### 方案 2: 检查 conda.sh

```bash
# 确认 conda.sh 存在
conda_base=$(conda info --base)
ls -la $conda_base/etc/profile.d/conda.sh

# 如果不存在，运行
conda init bash  # 或 zsh
source ~/.bashrc
```

#### 方案 3: 使用直接模式（不用 tmux）

```bash
# 直接模式会继承当前 shell 环境，没有 conda 问题
python3 test_tmux_cc_experience.py --max-tasks 2 --no-validate
```

## 手动测试 tmux 中的 conda

```bash
# 1. 创建测试 session
tmux new-session -s test

# 2. 在 tmux 中手动激活
source ~/anaconda3/etc/profile.d/conda.sh
conda activate dejavu

# 3. 验证
echo $CONDA_DEFAULT_ENV
which ducc

# 4. 退出测试
# Ctrl-b d (断开)
# tmux kill-session -t test (关闭)
```

## 快速检查清单

运行前确认：

```bash
# ✅ Conda 环境已激活
echo $CONDA_DEFAULT_ENV
# 应输出: dejavu

# ✅ ducc 可用
which ducc
# 应输出: /path/to/conda/envs/dejavu/bin/ducc

# ✅ conda.sh 存在
ls $(conda info --base)/etc/profile.d/conda.sh
# 应输出文件路径

# ✅ tmux 可用
tmux -V
# 应输出版本号
```

如果全部通过 ✅，脚本应该能正常工作！

## 相关文档

详细说明请查看：`CONDA_ACTIVATION_FIX.md`
