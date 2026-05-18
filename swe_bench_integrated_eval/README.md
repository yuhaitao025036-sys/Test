# SWE-bench Pro 集成评估系统

一键完成 Patch 生成和评估的自动化工具包。

## 📦 目录结构

```
swe_bench_integrated_eval/
├── README.md                          # 本文件（主文档）
├── QUICK_START.md                     # 快速开始指南
│
├── Core Scripts (核心脚本)
├── evaluate_single_instance.py        # 单实例评估脚本
├── summarize_eval_results.py          # 评估结果汇总脚本
├── run_batch_by_ids.sh                # ID列表批量运行脚本（推荐）
├── run_batch.sh                       # 批次批量运行脚本
├── test_tmux_cc_experience.py         # DUCC 代码生成脚本
│
├── Documentation (文档)
├── docs/
│   ├── INTEGRATED_EVAL_GUIDE.md       # 详细使用指南
│   ├── QUICK_START_EVAL.md            # 快速开始
│   └── IMPLEMENTATION_COMPLETE.md     # 实现完成报告
│
├── Example (示例)
├── example_ids.txt                    # 示例 Instance ID 列表
│
└── SWE-bench_Pro-os/                  # SWE-bench Pro 官方评估系统
    ├── swe_bench_pro_eval.py          # 核心评估逻辑
    ├── helper_code/                   # 辅助代码
    ├── dockerfiles/                   # Docker 配置
    ├── run_scripts/                   # 测试脚本（1000+ instances）
    └── ...
```

## 🚀 快速开始

### ⚠️ 开始前必读

**第一次使用？** 请先查看: [CHECKLIST.md](./CHECKLIST.md) 确保所有依赖就绪！

### 一键运行（生成 + 评估）

```bash
bash run_batch_by_ids.sh \
  --ids-file ./example_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 5 \
  --enable-eval
```

这一个命令会自动完成：
1. ✅ 生成 predictions（AI 生成代码修复）
2. ✅ 实时评估每个 prediction（Docker 运行测试）
3. ✅ 生成汇总报告（统计成功率）

**重要提示**:
- 确保 `swe_bench_pro_test.csv` 文件存在（当前目录或 `../`）
- 确保 Docker 正在运行
- 确保已安装: `pip install pandas docker`

### 查看结果

```bash
# 查看评估摘要
cat ./evaluation/batch/eval_summary_*.json

# 或使用汇总脚本
python summarize_eval_results.py \
  --eval-results-dir ./evaluation/batch/eval_results
```

## 📋 核心功能

### 1. 实时评估模式（推荐）
使用 `run_batch_by_ids.sh` + `--enable-eval`
- 每个 instance 完成后立即评估
- 实时查看成功率
- 评估并行化，不阻塞生成

### 2. 批量评估模式
使用 `run_batch.sh` + `--enable-eval`
- 按批次处理大规模任务
- 所有批次完成后统一评估
- 适合全量评估场景

### 3. 自动化流程
原有流程（三步）：
```bash
run_batch.sh → convert_to_official_format.py → swe_bench_pro_eval.py
```

新流程（一步）：
```bash
run_batch_by_ids.sh --enable-eval  # 一键完成
```

## 🔧 依赖要求

### 必需依赖
```bash
# Python 包
pip install pandas docker

# Docker（必须运行）
docker --version

# Conda 环境（可选，用于 DUCC）
conda create -n dejavu python=3.10
```

### 必需文件
- ✅ `SWE-bench_Pro-os/` 目录（已包含）
- ✅ `swe_bench_pro_test.csv`（需要从上层目录获取或指定路径）
- ✅ Docker Hub 镜像访问权限

## 📊 输出结构

```
./evaluation/
├── batch/
│   ├── {model}_swe_bench_output_*/
│   │   ├── predictions/              # 生成的 predictions
│   │   └── all_preds.jsonl
│   │
│   ├── eval_results/                 # 评估结果
│   │   ├── instance_xxx_eval.json
│   │   └── ...
│   │
│   ├── {model}_eval_summary.json     # ⭐ 摘要报告
│   └── {model}_eval_detailed.json    # 详细结果
│
└── logs/
    ├── run_batch_ids_master_*.log    # 主日志
    ├── {model}_ids_*.log             # 生成日志
    └── {model}_eval_*.log            # 评估日志
```

## 📖 详细文档

- **快速开始**: [QUICK_START.md](./QUICK_START.md)
- **详细指南**: [docs/INTEGRATED_EVAL_GUIDE.md](./docs/INTEGRATED_EVAL_GUIDE.md)
- **实现说明**: [docs/IMPLEMENTATION_COMPLETE.md](./docs/IMPLEMENTATION_COMPLETE.md)

## 💡 使用示例

### 示例 1: 测试少量 instances
```bash
# 创建测试文件
cat > test_ids.txt << EOF
instance_django__django-12345
instance_flask__flask-67890
EOF

# 运行
bash run_batch_by_ids.sh \
  --ids-file test_ids.txt \
  --model "Claude Sonnet 4.6" \
  --enable-eval
```

### 示例 2: 重试失败的 instances
```bash
# 从 eval_summary.json 提取 failed_instances
# 保存到 failed_ids.txt

bash run_batch_by_ids.sh \
  --ids-file failed_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 3 \
  --enable-eval
```

### 示例 3: 大规模批次评估
```bash
bash run_batch.sh \
  --model claude \
  --parallel 3 \
  --enable-eval
```

## 🔍 监控进度

```bash
# 查看主日志
tail -f ./evaluation/logs/run_batch_ids_master_*.log

# 查看生成进度
tail -f ./evaluation/logs/{model}_ids_*.log

# 查看评估进度
tail -f ./evaluation/logs/{model}_eval_*.log
```

## ❓ 常见问题

### Q: 中途中断了怎么办？
A: 直接重新运行相同命令，脚本会自动跳过已完成的任务。

### Q: 评估很慢怎么办？
A: 评估需要运行 Docker 容器执行测试。使用 `run_batch_by_ids.sh` 的实时评估模式，评估在后台进行不阻塞生成。

### Q: 如何只生成不评估？
A: 不加 `--enable-eval` 参数即可。

### Q: 需要修改 CSV 路径怎么办？
A: 使用 `--raw-sample-csv` 参数指定：
```bash
bash run_batch_by_ids.sh \
  --ids-file ./ids.txt \
  --model claude \
  --enable-eval \
  --raw-sample-csv /path/to/your/data.csv
```

## 🎯 核心优势

| 特性 | 原流程 | 集成流程 |
|------|--------|----------|
| 执行步骤 | 3 步手动 | 1 步自动 |
| 反馈延迟 | 全部完成后 | 实时 |
| 失败重试 | 手动 | 自动跳过已完成 |
| 成功率可见性 | 最后才知道 | 实时更新 |
| 并行评估 | 需手动配置 | 自动后台 |
| 中间文件处理 | 手动转换 | 自动处理 |

## 📦 打包说明

本目录是独立的工具包，包含：
- ✅ 所有必需的脚本
- ✅ 完整的 SWE-bench_Pro-os 评估系统
- ✅ 详细的文档和示例
- ✅ 可以直接在任何环境部署使用

**注意**: 需要额外准备：
1. `swe_bench_pro_test.csv` 文件（测试数据）
2. Docker Hub 镜像访问权限
3. Python 环境和依赖包

## 📝 License

本集成工具遵循 MIT License。  
SWE-bench Pro 官方代码遵循其原有 License。

## 🙏 致谢

- SWE-bench Pro 官方团队提供的评估系统
- DUCC (Baidu Code Copilot) 代码生成能力

---

**快速开始**: 查看 [QUICK_START.md](./QUICK_START.md)  
**详细文档**: 查看 [docs/](./docs/)  
**问题反馈**: 请查阅文档或联系维护者
