# Conda 环境激活问题修复

## 问题描述

在 tmux 模式下运行时，ducc 命令找不到，因为：
1. Tmux 创建新 session 时不会自动继承当前的 conda 环境
2. 需要在 tmux 中手动激活 conda 环境

## 错误现象

```bash
# 在 tmux session 中
$ ducc --version
ducc: command not found
```

## 解决方案

### 已实现的自动激活逻辑

修改后的脚本会自动：

1. **检测当前 conda 环境**
   ```python
   conda_env = os.environ.get('CONDA_DEFAULT_ENV')  # 例如: 'dejavu'
   ```

2. **找到 conda 安装路径**
   ```python
   conda_exe = shutil.which('conda')
   conda_base = os.path.dirname(os.path.dirname(conda_exe))
   ```

3. **在 tmux 中激活环境**
   ```bash
   # 方法A: 使用 conda.sh（推荐）
   source /path/to/conda/etc/profile.d/conda.sh && conda activate dejavu
   
   # 方法B: 直接调用（如果 shell 已初始化 conda）
   conda activate dejavu
   ```

4. **验证激活成功**
   ```bash
   echo 'ENV: '$CONDA_DEFAULT_ENV
   # 输出: ENV: dejavu
   ```

## 使用方法

### 不需要任何额外操作！

脚本会自动处理 conda 环境激活：

```bash
# 在已激活 conda 环境的终端运行
conda activate dejavu

# 运行脚本（会自动在 tmux 中激活相同环境）
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate

# 输出会显示：
# ✓ tmux session 已创建
#   检测到 conda 环境: dejavu
#   ✓ 使用 conda.sh 初始化: /path/to/conda/etc/profile.d/conda.sh
#   ✓ conda 环境激活成功
# ✓ ducc 命令已发送
```

## 工作原理

### 1. 环境检测

```python
conda_env = os.environ.get('CONDA_DEFAULT_ENV')
if conda_env:
    print(f"检测到 conda 环境: {conda_env}")
```

### 2. 初始化脚本定位

```python
conda_exe = shutil.which('conda')  # 找到 conda 命令
conda_base = os.path.dirname(os.path.dirname(conda_exe))  # 获取基础路径
conda_sh = os.path.join(conda_base, 'etc/profile.d/conda.sh')  # conda.sh 路径
```

### 3. Tmux 中激活

```python
# 组合命令：初始化 + 激活
init_and_activate = f'source {conda_sh} && conda activate {conda_env}'

# 发送到 tmux
subprocess.run(
    ["tmux", "send-keys", "-t", session_name, init_and_activate, "Enter"],
    check=True
)
```

### 4. 验证

```python
# 检查环境变量
subprocess.run(
    ["tmux", "send-keys", "-t", session_name, "echo 'ENV: '$CONDA_DEFAULT_ENV", "Enter"]
)

# 捕获输出验证
content = self._tmux_capture_pane(session_name)
if conda_env in content:
    print("✓ conda 环境激活成功")
```

## 支持的场景

### ✅ 场景 1: 标准 conda 安装

```bash
conda activate dejavu
python3 test_tmux_cc_experience.py --use-tmux --index 0
```

**效果**：自动使用 `conda.sh` 初始化并激活 dejavu 环境

### ✅ 场景 2: Miniconda

```bash
conda activate myenv
python3 test_tmux_cc_experience.py --use-tmux --index 0
```

**效果**：同样支持

### ✅ 场景 3: Shell 已初始化 conda

如果你的 `.bashrc` 或 `.zshrc` 中已经有：
```bash
# >>> conda initialize >>>
...
# <<< conda initialize <<<
```

脚本会直接调用 `conda activate`

### ⚠️ 场景 4: 没有 conda 环境

```bash
# 未激活任何 conda 环境
python3 test_tmux_cc_experience.py --use-tmux --index 0
```

**效果**：使用系统默认 PATH（需要 ducc 在系统 PATH 中）

## 手动验证

### 测试 conda 激活

```bash
# 1. 进入 conda 环境
conda activate dejavu

# 2. 检查环境变量
echo $CONDA_DEFAULT_ENV
# 输出: dejavu

# 3. 检查 ducc 路径
which ducc
# 输出: /home/user/anaconda3/envs/dejavu/bin/ducc

# 4. 运行脚本
python3 test_tmux_cc_experience.py --use-tmux --index 0 --no-validate
```

### 在 tmux 中手动测试

```bash
# 1. 创建测试 session
tmux new-session -d -s test_conda

# 2. 激活环境
tmux send-keys -t test_conda "source ~/anaconda3/etc/profile.d/conda.sh" Enter
tmux send-keys -t test_conda "conda activate dejavu" Enter

# 3. 验证
tmux send-keys -t test_conda "echo \$CONDA_DEFAULT_ENV" Enter
tmux send-keys -t test_conda "which ducc" Enter

# 4. 查看输出
tmux capture-pane -p -t test_conda

# 5. 连接查看
tmux attach -t test_conda

# 6. 清理
tmux kill-session -t test_conda
```

## 故障排查

### 问题 1: 仍然找不到 ducc

**症状**：
```
✓ conda 环境激活命令已发送
⚠️  环境激活可能失败，继续尝试...
ducc: command not found
```

**排查步骤**：

1. **检查 conda.sh 是否存在**
   ```bash
   conda_base=$(conda info --base)
   ls -la $conda_base/etc/profile.d/conda.sh
   ```

2. **检查 ducc 安装位置**
   ```bash
   conda activate dejavu
   which ducc
   # 应该输出类似: /path/to/conda/envs/dejavu/bin/ducc
   ```

3. **手动在 tmux 中测试**
   ```bash
   tmux new-session -s test
   # 在 tmux 中手动激活
   source ~/anaconda3/etc/profile.d/conda.sh
   conda activate dejavu
   which ducc
   ```

### 问题 2: conda.sh 路径不对

**解决方案**：

1. **找到正确的 conda 安装路径**
   ```bash
   conda info --base
   # 输出: /home/user/anaconda3
   ```

2. **手动指定路径**
   
   临时方案：在脚本中硬编码路径
   ```python
   # 在 _call_ducc_tmux 方法中
   conda_sh = '/home/user/anaconda3/etc/profile.d/conda.sh'
   ```

3. **设置环境变量**
   ```bash
   export CONDA_SH_PATH="/path/to/conda/etc/profile.d/conda.sh"
   ```

### 问题 3: Shell 配置问题

**症状**：`conda activate` 命令不可用

**解决方案**：

1. **初始化 conda**
   ```bash
   conda init bash  # 或 zsh
   ```

2. **重启 shell 或 source 配置**
   ```bash
   source ~/.bashrc  # 或 ~/.zshrc
   ```

3. **验证**
   ```bash
   conda activate dejavu
   echo $CONDA_DEFAULT_ENV
   ```

## 替代方案

如果自动激活仍然有问题，可以使用以下替代方案：

### 方案 1: 使用绝对路径

不依赖 conda 环境，直接使用 ducc 的绝对路径：

```bash
# 找到 ducc 路径
conda activate dejavu
which ducc
# 输出: /home/user/anaconda3/envs/dejavu/bin/ducc

# 设置环境变量
export DUCC_BIN="/home/user/anaconda3/envs/dejavu/bin/ducc"

# 运行脚本
python3 test_tmux_cc_experience.py --use-tmux --index 0
```

### 方案 2: 不使用 tmux 模式

如果 tmux 环境配置太复杂，使用直接模式：

```bash
# 直接模式不会有 conda 环境问题
python3 test_tmux_cc_experience.py --max-tasks 2 --no-validate
```

直接模式会继承当前 shell 的完整环境。

### 方案 3: 预先配置 tmux

在 `~/.tmux.conf` 中配置：

```bash
# 自动加载 conda 环境
set-option -g default-command "bash -l"

# 或者添加启动命令
set-hook -g after-new-session 'send-keys "source ~/anaconda3/etc/profile.d/conda.sh && conda activate dejavu" Enter'
```

## 测试检查清单

运行脚本前检查：

- [ ] conda 环境已激活：`echo $CONDA_DEFAULT_ENV`
- [ ] ducc 可用：`which ducc`
- [ ] conda.sh 存在：`ls $(conda info --base)/etc/profile.d/conda.sh`
- [ ] tmux 可用：`tmux -V`

如果全部通过，脚本应该能正常工作。

## 日志输出示例

### 成功的输出

```
============================================================
启动 tmux session: swe_bench_django__django_12345_1735286400
工作目录: /tmp/swe_bench_xyz/workspace
查看执行过程: tmux attach -t swe_bench_django__django_12345_1735286400
============================================================

✓ tmux session 已创建
  检测到 conda 环境: dejavu
  ✓ 使用 conda.sh 初始化: /home/user/anaconda3/etc/profile.d/conda.sh
  ✓ conda 环境激活成功
✓ ducc 命令已发送
✓ 发送任务prompt
✓ 开始监控执行...
```

### 失败的输出

```
✓ tmux session 已创建
  检测到 conda 环境: dejavu
  ⚠️  未找到 conda.sh，尝试使用环境中的 conda
  ⚠️  环境激活可能失败，继续尝试...
✗ tmux模式执行失败: ducc command not found
```

## 总结

修改后的脚本会：

1. ✅ 自动检测 conda 环境
2. ✅ 自动在 tmux 中激活相同环境
3. ✅ 验证激活是否成功
4. ✅ 提供详细的日志输出
5. ✅ 支持多种 conda 安装方式

你不需要手动做任何事情，脚本会自动处理 conda 环境激活！
