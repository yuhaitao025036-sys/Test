# 快速开始指南

## 前置要求

### 1. 确认依赖已安装
```bash
# Python 包
pip install pandas docker

# 检查 Docker
docker --version
```

### 2. 准备测试数据
```bash
# 确保有 swe_bench_pro_test.csv 文件
# 可以从上层目录复制或指定路径
cp ../swe_bench_pro_test.csv ./
```

## 基本使用

### 步骤 0: 准备必需文件 ⚠️

```bash
# 确保有 swe_bench_pro_test.csv 文件
# 方式 1: 从上层目录复制
cp ../swe_bench_pro_test.csv ./

# 方式 2: 从其他位置复制
cp /path/to/swe_bench_pro_test.csv ./

# 验证文件存在
ls -lh swe_bench_pro_test.csv
```

### 步骤 1: 准备 Instance ID 列表

```bash
# 使用示例文件
cat example_ids.txt

# 或创建自己的列表
cat > my_test_ids.txt << EOF
instance_django__django-12345
instance_flask__flask-67890
instance_requests__requests-54321
EOF
```

### 步骤 2: 运行（生成 + 评估）

#### 最简单的方式（使用默认配置）

```bash
bash run_batch_by_ids.sh \
  --ids-file ./my_test_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 3 \
  --enable-eval
```

**默认配置**:
- CSV 文件: `../swe_bench_pro_test.csv`（上层目录）
- Scripts 目录: `./SWE-bench_Pro-os/run_scripts`
- Docker Hub 用户名: `jefzda`
- 输出目录: `./evaluation/batch/{model}_swe_bench_output_ids/`

**参数说明**:
- `--ids-file`: Instance ID 列表文件（必需）
- `--model`: 使用的模型名称（必需）
- `--parallel`: 并发数量（可选，默认 1）
- `--enable-eval`: 启用实时评估（可选）

### 步骤 3: 监控进度

打开新终端，实时查看日志：

```bash
# 查看主日志
tail -f ./evaluation/logs/run_batch_ids_master_*.log

# 查看具体任务
tail -f ./evaluation/logs/*_ids_*.log

# 查看评估进度
tail -f ./evaluation/logs/*_eval_*.log
```

### 步骤 4: 查看结果

#### 输出文件位置

```
./evaluation/
├── batch/
│   ├── {model}_swe_bench_output_ids/      # 生成的 predictions
│   │   ├── predictions/
│   │   │   ├── instance_xxx.json
│   │   │   └── ...
│   │   └── all_preds.jsonl
│   │
│   ├── eval_results/                       # 评估结果
│   │   ├── instance_xxx_eval.json
│   │   └── ...
│   │
│   ├── eval_summary_{model}.json           # ⭐ 摘要报告（最重要）
│   └── eval_detailed_{model}.json          # 详细结果
│
└── logs/
    ├── run_batch_ids_master_*.log          # 主日志
    ├── {model}_ids_*.log                   # 生成日志
    └── {model}_eval_*.log                  # 评估日志
```

#### 查看评估报告

```bash
# 查看评估摘要（JSON 格式）
cat ./evaluation/batch/eval_summary_*.json

# 使用汇总脚本查看详细报告
python summarize_eval_results.py \
  --eval-results-dir ./evaluation/batch/eval_results
```

## 输出说明

### 主要输出文件

```
./evaluation/batch/
├── eval_results/                      # 每个 instance 的评估结果
│   ├── instance_xxx_eval.json
│   └── ...
├── {model}_eval_summary.json          # ⭐ 摘要报告（最重要）
└── {model}_eval_detailed.json         # 详细结果
```

### 摘要报告格式

```json
{
  "total": 100,                        // 总任务数
  "resolved": 75,                      // 成功解决的数量
  "accuracy": 0.75,                    // 总体准确率 ⭐
  "fail_to_pass_accuracy": 0.80,      // F2P 准确率
  "pass_to_pass_accuracy": 0.90,      // P2P 准确率
  "failed_instances": [...]            // 失败的 instance 列表
}
```

## 高级用法

### 自定义所有参数（完整版）

```bash
bash run_batch_by_ids.sh \
  --ids-file ./my_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 5 \
  --enable-eval \
  --dockerhub-username myuser \
  --raw-sample-csv ./swe_bench_pro_test.csv \
  --scripts-dir ./SWE-bench_Pro-os/run_scripts
```

**所有参数说明**:
- `--ids-file`: Instance ID 列表文件（必需）
- `--model`: 模型名称（必需）
- `--parallel`: 并发数量（可选，默认 1）
- `--enable-eval`: 启用评估（可选）
- `--dockerhub-username`: Docker Hub 用户名（可选，默认 `jefzda`）
- `--raw-sample-csv`: CSV 文件路径（可选，默认 `../swe_bench_pro_test.csv`）
- `--scripts-dir`: Scripts 目录（可选，默认 `./SWE-bench_Pro-os/run_scripts`）

### CSV 文件位置说明

CSV 文件默认路径: `../swe_bench_pro_test.csv`（上层目录）

**推荐做法**:
```bash
# 方式 1: 复制到当前目录并指定
cp /path/to/swe_bench_pro_test.csv ./
bash run_batch_by_ids.sh \
  --ids-file ./my_ids.txt \
  --model claude \
  --enable-eval \
  --raw-sample-csv ./swe_bench_pro_test.csv

# 方式 2: 复制到上层目录（使用默认）
cp /path/to/swe_bench_pro_test.csv ../
bash run_batch_by_ids.sh \
  --ids-file ./my_ids.txt \
  --model claude \
  --enable-eval

# 方式 3: 指定任意路径
bash run_batch_by_ids.sh \
  --ids-file ./my_ids.txt \
  --model claude \
  --enable-eval \
  --raw-sample-csv /absolute/path/to/swe_bench_pro_test.csv
```

### 只生成不评估

```bash
# 不加 --enable-eval 参数
bash run_batch_by_ids.sh \
  --ids-file ./my_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 5
```

### 批次模式（大规模）

```bash
# 编辑 run_batch.sh 中的批次配置
# 然后运行
bash run_batch.sh \
  --model claude \
  --parallel 3 \
  --enable-eval
```

## 常见场景

### 场景 1: 快速测试 2-3 个 instances

```bash
echo "instance_django__django-12345" > test.txt
echo "instance_flask__flask-67890" >> test.txt

bash run_batch_by_ids.sh \
  --ids-file test.txt \
  --model "Claude Sonnet 4.6" \
  --enable-eval
```

### 场景 2: 中断后继续

```bash
# 直接重新运行相同命令，自动跳过已完成任务
bash run_batch_by_ids.sh \
  --ids-file ./my_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 3 \
  --enable-eval
```

### 场景 3: 重试失败的任务

```bash
# 从 eval_summary.json 提取 failed_instances
# 手动创建 failed_ids.txt

bash run_batch_by_ids.sh \
  --ids-file ./failed_ids.txt \
  --model "Claude Sonnet 4.6" \
  --enable-eval
```

## 故障排查

### 问题 1: "Instance not found in CSV"

**原因**: CSV 文件路径不正确

**解决**:
```bash
# 检查文件是否存在
ls -l ../swe_bench_pro_test.csv

# 指定正确路径
bash run_batch_by_ids.sh \
  --ids-file ./ids.txt \
  --model claude \
  --enable-eval \
  --raw-sample-csv /path/to/swe_bench_pro_test.csv
```

### 问题 2: Docker 镜像拉取失败

**原因**: Docker Hub 用户名不正确

**解决**:
```bash
# 检查 Docker 是否运行
docker ps

# 指定正确的用户名
bash run_batch_by_ids.sh \
  --ids-file ./ids.txt \
  --model claude \
  --enable-eval \
  --dockerhub-username your_username
```

### 问题 3: 评估很慢

**原因**: Docker 容器需要运行完整测试

**解决**: 
- 降低并发数 `--parallel 2`
- 使用实时评估模式（run_batch_by_ids.sh），评估在后台不阻塞

### 问题 4: 内存不足

**解决**:
```bash
# 降低并发数
bash run_batch_by_ids.sh \
  --ids-file ./ids.txt \
  --model claude \
  --parallel 2 \
  --enable-eval
```

## 完整示例

```bash
# 1. 准备环境
cd /path/to/swe_bench_integrated_eval
pip install pandas docker

# 2. 准备数据
cp ../swe_bench_pro_test.csv ./

# 3. 创建测试列表
cat > test_ids.txt << EOF
instance_django__django-12345
instance_flask__flask-67890
EOF

# 4. 运行
bash run_batch_by_ids.sh \
  --ids-file ./test_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 3 \
  --enable-eval

# 5. 监控（新终端）
tail -f ./evaluation/logs/run_batch_ids_master_*.log

# 6. 查看结果
cat ./evaluation/batch/eval_summary_*.json
```

## 下一步

- 查看详细文档: [docs/INTEGRATED_EVAL_GUIDE.md](./docs/INTEGRATED_EVAL_GUIDE.md)
- 了解实现细节: [docs/IMPLEMENTATION_COMPLETE.md](./docs/IMPLEMENTATION_COMPLETE.md)
- 主文档: [README.md](./README.md)

---

有问题？查看 [docs/INTEGRATED_EVAL_GUIDE.md](./docs/INTEGRATED_EVAL_GUIDE.md) 的"故障排查"章节
