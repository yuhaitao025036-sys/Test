# 使用命令

## 🎯 两种运行模式

### 模式对比

| 特性 | run_batch_by_ids.sh | run_batch.sh |
|------|---------------------|--------------|
| **输入方式** | ID 列表文件 | 脚本内部批次配置 |
| **灵活性** | ✅ 高（自由指定） | ⚠️ 低（需修改脚本） |
| **索引参数** | ❌ 不需要 | ❌ 不需要（内部硬编码） |
| **输出目录** | 自动：`{model}_swe_bench_output_ids/` | 自动：`{model}_swe_bench_output_{start}_{end}/` |
| **适用场景** | 精确控制、失败重试 | 大规模批量处理 |

---

## run_batch_by_ids.sh（推荐）

### 完整参数命令

```bash
# 第 1 步：准备 ID 列表文件
cat > my_ids.txt << EOF
instance_django__django-12345
instance_flask__flask-67890
instance_requests__requests-54321
EOF

# 第 2 步：运行
bash run_batch_by_ids.sh \
  --ids-file ./final_filtered_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 5 \
  --enable-eval \
  --dockerhub-username jefzda \
  --dataset-path /ssd1/Dejavu/datasets/SWE-bench_Pro/test-python.parquet \
  --scripts-dir ./SWE-bench_Pro-os/run_scripts
```

**说明**:
- ✅ **不需要** `--output-dir`（自动生成）
- ✅ **不需要** `--start-index` 和 `--end-index`（从 ID 列表文件读取）
- ✅ **数据统一**: 使用同一个 parquet 文件作为数据源，评估时自动读取
- ✅ 输出位置：`./evaluation/batch/{model}_swe_bench_output_ids/`

### 参数说明

| 参数 | 默认值 | 必需 |
|------|--------|------|
| `--ids-file` | 无 | ✅ 必需 |
| `--model` | 无 | ✅ 必需 |
| `--parallel` | 1 | 可选 |
| `--enable-eval` | false | 可选 |
| `--dockerhub-username` | jefzda | 可选 |
| `--dataset-path` | /ssd1/Dejavu/datasets/SWE-bench_Pro/test-python.parquet | 可选 |
| `--scripts-dir` | ./SWE-bench_Pro-os/run_scripts | 可选 |

---

## run_batch.sh

### 完整参数命令

```bash
# 第 1 步：编辑批次配置（可选）
# vim run_batch.sh
# 找到第 171 行的 batches=(...)，修改索引范围
# batches=(
#   "120:130"   # 处理 CSV 第 120-130 行
#   "130:140"   # 处理 CSV 第 130-140 行
#   ...
# )

# 第 2 步：运行
bash run_batch.sh \
  --model claude \
  --parallel 3 \
  --enable-eval \
  --retry-failed \
  --dockerhub-username jefzda \
  --dataset-path /ssd1/Dejavu/datasets/SWE-bench_Pro/test-python.parquet \
  --scripts-dir ./SWE-bench_Pro-os/run_scripts
```

**说明**:
- ✅ **不需要** `--output-dir`（自动生成）
- ✅ **不需要** `--start-index` 和 `--end-index`（在脚本内部硬编码）
- ✅ 批次配置在脚本第 171-194 行
- ✅ 输出位置：`./evaluation/batch/{model}_swe_bench_output_{start}_{end}/`

### 参数说明

| 参数 | 默认值 | 必需 |
|------|--------|------|
| `--model` | minimax_27 | 可选 |
| `--parallel` | 1 | 可选 |
| `--enable-eval` | false | 可选 |
| `--retry-failed` | false | 可选 |
| `--dockerhub-username` | jefzda | 可选 |
| `--dataset-path` | /ssd1/Dejavu/datasets/SWE-bench_Pro/test-python.parquet | 可选 |
| `--scripts-dir` | ./SWE-bench_Pro-os/run_scripts | 可选 |

---

## 📊 数据来源说明（重要）

**核心改进: 数据源统一**

为了保证数据一致性，系统现在使用**单一数据源**:

```bash
/ssd1/Dejavu/datasets/SWE-bench_Pro/test-python.parquet
```

**工作流程**:
1. **生成预测**: `test_tmux_cc_experience.py` 从 parquet 文件读取 instance 元数据
2. **评估测试**: `evaluate_single_instance.py` 从**同一个** parquet 文件读取测试配置 (fail_to_pass/pass_to_pass)
3. **数据一致**: 不再需要单独的 CSV 文件，避免数据不同步风险

**问: instance_id 对应的实际代码从哪里获取?**

答: 系统从两个地方获取数据:

1. **元数据文件** (必需): `/ssd1/Dejavu/datasets/SWE-bench_Pro/test-python.parquet`
   - 包含所有 instance 的配置 (dockerhub_tag, fail_to_pass, pass_to_pass 等)
   - 可通过 `--dataset-path` 参数或环境变量 `SWE_BENCH_DATASET` 覆盖
   - **预测和评估都使用这个文件，确保数据一致**

2. **实际代码** (自动提取): Docker 镜像 `jefzda/sweap-images:{dockerhub_tag}`
   - 每个 instance 有独立的 Docker 镜像标签
   - 脚本自动从容器的 `/app` 或 `/testbed` 目录提取完整代码库
   - 可通过环境变量 `DOCKER_IMAGE_PREFIX` 覆盖镜像仓库前缀

**数据流程**:
```
你提供的 instance_id 
  → 查询 parquet 文件获取元数据 (包括测试配置)
  → 获取对应的 dockerhub_tag 
  → 拉取 Docker 镜像 
  → 提取代码到临时目录 
  → 执行任务 + 评估（使用同一份测试配置）
```

**环境变量配置** (可选):
```bash
export SWE_BENCH_DATASET="/path/to/your/test-python.parquet"
export DOCKER_IMAGE_PREFIX="jefzda/sweap-images"  # 或其他镜像仓库
```

---

## 输出位置

```
./evaluation/batch/{model}_swe_bench_output_*/predictions/*.json   # Predictions
./evaluation/batch/eval_results/*.json                              # 评估结果
./evaluation/batch/eval_summary_{model}.json                        # 摘要报告
./evaluation/logs/                                                  # 日志
```
