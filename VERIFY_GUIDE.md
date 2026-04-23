# SWE-bench 官方标准验证

这个脚本使用 SWE-bench 官方标准来验证生成的 patches。

## 快速开始

### 方式 1：使用简化验证（推荐，不需要 Docker）

```bash
# 验证所有 patches
python verify_with_swebench.py

# 验证单个 patch
python verify_with_swebench.py --instance-id instance_django__django-12345

# 指定输出目录
python verify_with_swebench.py --output-dir ./my_output
```

### 方式 2：使用官方 swebench 工具（需要 Docker）

```bash
# 安装官方工具
pip install swebench

# 使用官方 harness 验证（标准方式）
python -m swebench.harness.run_evaluation \
    --predictions_path ./swe_bench_output/predictions \
    --swe_bench_tasks testbed \
    --log_dir ./logs
```

## 验证标准

### SWE-bench 官方标准

| 指标 | 说明 |
|------|------|
| **Pass -> Pass** | 原本通过的测试仍然通过 ✓ |
| **Fail -> Pass** | 原本失败的测试现在通过 ✓（解决了问题） |
| **Pass -> Fail** | 原本通过的测试现在失败 ✗（引入了新 bug） |
| **Fail -> Fail** | 原本失败的测试仍然失败 ✗（没有解决问题） |

### Resolved 率计算

官方指标：`Resolved 率 = Fail -> Pass 数 / 总实例数`

## 输出说明

### 控制台输出

```
✓ instance_django__django-12345
  Pass -> Pass: 5
  Fail -> Pass: 1
  总计: 6 个测试通过

✗ instance_flask__flask-9999
  失败原因: Empty patch
```

### 报告文件

生成 `verification_report.json`，包含：

```json
{
  "summary": {
    "total_instances": 10,
    "passed": 7,
    "passed_rate": "70.0%"
  },
  "metrics": {
    "pass_to_pass": 35,
    "fail_to_pass": 8,
    "pass_to_fail": 2,
    "fail_to_fail": 15,
    "resolved_count": 8
  },
  "details": [...]
}
```

## 完整工作流

### 步骤 1：生成 patches

```bash
cd /Users/yuhaitao01/dev/baidu/explore/Experience

# 生成所有 patches（无需 Docker）
python test/test_llm_api.py --index 0-9 --no-validate
```

### 步骤 2：验证 patches

```bash
# 简化验证（快速，不需要 Docker）
python test/verify_with_swebench.py

# 或者用官方工具（完整，需要 Docker）
python -m swebench.harness.run_evaluation \
    --predictions_path ./swe_bench_output/predictions \
    --swe_bench_tasks testbed
```

### 步骤 3：查看报告

```bash
cat swe_bench_output/verification_report.json
```

## 注意事项

1. **简化验证**：当 Docker 不可用时，脚本会进行基本的 patch 格式检查
2. **完整验证**：需要安装 `swebench` 包和 Docker
3. **官方标准**：只有 `Fail -> Pass` 数被计为解决问题

## 官方工具安装

```bash
# 安装 swebench
pip install swebench

# 验证安装
python -c "import swebench; print(swebench.__version__)"
```

## 常见问题

### Q: 为什么显示"Docker 不可用"？

A: 完整验证需要 Docker。可以：
- 启动 Docker 后重新运行
- 或使用简化验证（不需要 Docker）

### Q: 如何理解验证结果？

A: 
- **Pass -> Pass**: 好的，没有引入 bug
- **Fail -> Pass**: 最好的，真正解决了问题
- **Pass -> Fail**: 不好的，破坏了原有功能
- **Fail -> Fail**: 不好的，没有解决问题

### Q: Resolved 率怎么计算？

A: `Fail -> Pass 数 / 总实例数 × 100%`

这是官方 SWE-bench 排行榜使用的指标。
