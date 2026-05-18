# 集成评估流程使用指南

## 概述

集成评估流程将 patch 生成和评估整合为一个自动化流程，无需手动执行三个独立步骤。

### 原有流程（三步）
1. **生成 predictions**: `run_batch.sh` 或 `run_batch_by_ids.sh`
2. **转换格式**: `python convert_to_official_format.py`
3. **评估**: `python swe_bench_pro_eval.py`

### 新流程（一步）
使用 `--enable-eval` 参数，一个命令完成所有步骤！

---

## 核心功能

### 1. 实时评估（`run_batch_by_ids.sh`）
每个 instance 完成生成后立即评估，无需等待全部完成。

### 2. 批量评估（`run_batch.sh`）
所有批次完成后统一评估所有 predictions。

### 3. 自动汇总
评估完成后自动生成统计报告，包括：
- 总体准确率
- Fail-to-Pass 和 Pass-to-Pass 指标
- 失败实例列表
- 详细测试结果

---

## 使用方法

### run_batch_by_ids.sh - 实时评估模式

#### 基本用法（不带评估）
```bash
bash run_batch_by_ids.sh \
  --ids-file ./run_batch_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 5
```

#### 启用实时评估
```bash
bash run_batch_by_ids.sh \
  --ids-file ./run_batch_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 5 \
  --enable-eval
```

#### 自定义评估参数
```bash
bash run_batch_by_ids.sh \
  --ids-file ./run_batch_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 5 \
  --enable-eval \
  --dockerhub-username myuser \
  --raw-sample-csv ./custom_data.csv \
  --scripts-dir ./custom_scripts
```

### run_batch.sh - 批量评估模式

#### 基本用法（不带评估）
```bash
bash run_batch.sh \
  --model claude \
  --parallel 3
```

#### 启用批量评估
```bash
bash run_batch.sh \
  --model claude \
  --parallel 3 \
  --enable-eval
```

---

## 参数说明

### 共有参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--model` | 模型名称（支持简短名或完整名） | claude / minimax_27 |
| `--parallel` | 并发数量 | 1 |
| `--enable-eval` | 启用评估功能 | 未启用 |
| `--dockerhub-username` | Docker Hub 用户名 | jefzda |
| `--raw-sample-csv` | Raw sample CSV 文件路径 | ../swe_bench_pro_test.csv |
| `--scripts-dir` | Scripts 目录路径 | ./SWE-bench_Pro-os/run_scripts |

### run_batch_by_ids.sh 特有参数

| 参数 | 说明 | 必需 |
|------|------|------|
| `--ids-file` | Instance ID 列表文件路径 | ✓ |

### run_batch.sh 特有参数

| 参数 | 说明 | 必需 |
|------|------|------|
| `--retry-failed` | 重试失败的任务 | ✗ |

---

## 输出文件

### 不启用评估
```
./evaluation/
├── batch/
│   └── {model}_swe_bench_output_*/
│       ├── predictions/          # 生成的 predictions
│       └── all_preds.jsonl       # JSONL 格式
└── logs/                          # 生成日志
```

### 启用评估
```
./evaluation/
├── batch/
│   ├── {model}_swe_bench_output_*/
│   │   ├── predictions/                    # 生成的 predictions
│   │   └── all_preds.jsonl
│   ├── eval_results/                       # 评估结果（每个 instance）
│   │   ├── instance_xxx_eval.json
│   │   └── ...
│   ├── {model}_eval_summary.json           # 评估摘要报告 ⭐
│   └── {model}_eval_detailed.json          # 详细评估结果
└── logs/
    ├── {model}_ids_*.log                    # 生成日志
    └── {model}_eval_*.log                   # 评估日志
```

---

## 评估报告格式

### 摘要报告 (`eval_summary.json`)
```json
{
  "total": 100,
  "resolved": 75,
  "failed": 25,
  "accuracy": 0.75,
  "fail_to_pass_accuracy": 0.80,
  "pass_to_pass_accuracy": 0.90,
  "avg_fail_to_pass_rate": 0.85,
  "avg_pass_to_pass_rate": 0.92,
  "overall_fail_to_pass_rate": 0.84,
  "overall_pass_to_pass_rate": 0.91,
  "total_fail_to_pass_tests": {
    "passed": 420,
    "total": 500,
    "rate": 0.84
  },
  "total_pass_to_pass_tests": {
    "passed": 910,
    "total": 1000,
    "rate": 0.91
  },
  "failed_instances": ["instance_1", "instance_2", ...],
  "error_instances": []
}
```

### 单实例评估结果 (`instance_xxx_eval.json`)
```json
{
  "instance_id": "instance_xxx",
  "resolved": true,
  "fail_to_pass_passed": true,
  "fail_to_pass_success_count": 5,
  "fail_to_pass_total_count": 5,
  "fail_to_pass_rate": 1.0,
  "pass_to_pass_passed": true,
  "pass_to_pass_success_count": 10,
  "pass_to_pass_total_count": 10,
  "pass_to_pass_rate": 1.0,
  "overall": true
}
```

---

## 实时监控

### 查看生成进度
```bash
# 主日志
tail -f ./evaluation/logs/run_batch_ids_master_{model}.log

# 具体任务日志
tail -f ./evaluation/logs/{model}_ids_*.log
```

### 查看评估进度
```bash
# 评估日志
tail -f ./evaluation/logs/{model}_eval_*.log
```

### 查看实时统计
```bash
# 在任务运行期间随时查看已完成的评估结果
python summarize_eval_results.py \
  --eval-results-dir ./evaluation/batch/eval_results
```

---

## 工作流程详解

### run_batch_by_ids.sh（实时评估）

1. **任务分发**: 根据 `--parallel` 参数并发运行多个 instance 生成任务
2. **生成 Prediction**: 调用 `test_tmux_cc_experience.py` 生成 patch
3. **立即评估**: Prediction 生成完成后立即启动评估（后台运行）
4. **继续下一个**: 不等待评估完成，立即处理下一个 instance
5. **汇总报告**: 所有任务完成后，等待评估完成并生成汇总报告

**优势**: 
- ⚡ 评估并行化，不阻塞生成任务
- 📊 实时了解成功率
- 🔄 失败任务可立即重试

### run_batch.sh（批量评估）

1. **批次处理**: 按照预定义的批次顺序处理（如 120-130, 130-140）
2. **生成 Predictions**: 每个批次完成后生成 `all_preds.jsonl`
3. **批量评估**: 所有批次完成后，扫描所有 predictions 目录
4. **逐个评估**: 对每个 prediction 文件调用评估脚本
5. **汇总报告**: 生成最终评估报告

**优势**: 
- 🎯 适合大规模批次处理
- 💾 节省计算资源（顺序评估）
- 📋 可选择性评估部分批次

---

## 常见使用场景

### 场景 1: 快速测试少量 instances
```bash
# 创建测试文件
echo "instance_django__django-12345" > test_ids.txt
echo "instance_flask__flask-67890" >> test_ids.txt

# 运行并评估
bash run_batch_by_ids.sh \
  --ids-file test_ids.txt \
  --model "Claude Sonnet 4.6" \
  --enable-eval
```

### 场景 2: 重新评估失败的 instances
```bash
# 第一次运行（带评估）
bash run_batch_by_ids.sh \
  --ids-file ./all_ids.txt \
  --model claude \
  --parallel 5 \
  --enable-eval

# 从摘要报告中提取失败的 instances
# eval_summary.json -> failed_instances

# 重新运行失败的 instances
bash run_batch_by_ids.sh \
  --ids-file ./failed_ids.txt \
  --model claude \
  --parallel 3 \
  --enable-eval
```

### 场景 3: 批次模式全量评估
```bash
# 运行所有批次并评估
bash run_batch.sh \
  --model claude \
  --parallel 2 \
  --enable-eval

# 查看结果
cat ./evaluation/batch/claude_eval_summary.json
```

### 场景 4: 只评估已生成的 predictions（不重新生成）
```bash
# 直接使用 summarize_eval_results.py
python summarize_eval_results.py \
  --eval-results-dir ./evaluation/batch/eval_results \
  --output-file ./my_summary.json
```

---

## 性能优化建议

### 并发配置
- **生成任务**: `--parallel 3-5`（受 Docker/API 限制）
- **评估任务**: 在 `run_batch_by_ids.sh` 中自动后台并行

### 资源管理
- 每个 Docker 评估容器消耗约 2-8GB 内存
- 建议总并发数（生成+评估）不超过机器核心数的 1.5 倍

### 断点续传
- 两个脚本都支持自动跳过已完成的任务
- 直接重新运行相同命令即可续传

---

## 故障排查

### 问题 1: 评估失败 "Instance not found in CSV"
**原因**: `raw-sample-csv` 路径不正确或 CSV 文件不包含该 instance

**解决方法**:
```bash
# 检查 CSV 文件是否存在
ls -l ../swe_bench_pro_test.csv

# 检查 instance_id 是否在 CSV 中
grep "instance_xxx" ../swe_bench_pro_test.csv
```

### 问题 2: Docker 镜像拉取失败
**原因**: Docker Hub 用户名不正确或镜像不存在

**解决方法**:
```bash
# 检查 Docker Hub 镜像
docker search {dockerhub_username}/sweap-images

# 手动拉取测试
docker pull {dockerhub_username}/sweap-images:xxx
```

### 问题 3: 评估进程僵死
**原因**: Docker 容器资源限制或进程泄漏

**解决方法**:
```bash
# 清理僵尸容器
docker ps -a | grep sweap | awk '{print $1}' | xargs docker rm -f

# 重启评估
bash run_batch_by_ids.sh --ids-file ./ids.txt --enable-eval
```

### 问题 4: 内存不足
**解决方法**: 降低并发数
```bash
bash run_batch_by_ids.sh \
  --ids-file ./ids.txt \
  --model claude \
  --parallel 2 \
  --enable-eval
```

---

## 手动使用评估脚本

### 单实例评估
```bash
python evaluate_single_instance.py \
  --instance-id "instance_django__django-12345" \
  --prediction-file "./evaluation/batch/.../predictions/instance_django__django-12345.json" \
  --raw-sample-csv "../swe_bench_pro_test.csv" \
  --scripts-dir "./SWE-bench_Pro-os/run_scripts" \
  --output-dir "./eval_results" \
  --dockerhub-username jefzda \
  --use-local-docker
```

### 汇总评估结果
```bash
python summarize_eval_results.py \
  --eval-results-dir "./eval_results" \
  --output-file "./summary.json" \
  --detailed-output "./detailed.json"
```

---

## 与原流程对比

| 特性 | 原流程 | 集成流程 |
|------|--------|----------|
| 执行步骤 | 3 步 | 1 步 |
| 反馈延迟 | 全部完成后 | 实时 |
| 失败重试 | 手动 | 自动 |
| 成功率可见性 | 最后才知道 | 实时更新 |
| 并行评估 | 需手动配置 | 自动后台 |
| 中间文件 | 需手动转换 | 自动处理 |

---

## 总结

集成评估流程通过以下方式显著提升效率：

1. ✅ **一键完成**: 生成 + 转换 + 评估全自动
2. ⚡ **实时反馈**: 无需等待全部完成即可了解成功率
3. 🔄 **智能重试**: 自动跳过已完成任务
4. 📊 **详细报告**: 自动生成多层次统计报告
5. 🚀 **并行优化**: 评估不阻塞生成任务

**推荐使用场景**:
- ⭐ **run_batch_by_ids.sh --enable-eval**: 适合少量精确 instances 的快速验证
- 🎯 **run_batch.sh --enable-eval**: 适合大规模批次的全量评估
