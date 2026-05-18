# 部署说明

## 目录说明

```
swe_bench_integrated_eval/
├── README.md                          # 主文档
├── QUICK_START.md                     # 快速开始
├── DEPLOYMENT.md                      # 本文件（部署说明）
│
├── 核心脚本
├── evaluate_single_instance.py        # 单实例评估
├── summarize_eval_results.py          # 结果汇总
├── run_batch_by_ids.sh                # ID列表批量运行（推荐）
├── run_batch.sh                       # 批次批量运行
├── test_tmux_cc_experience.py         # DUCC 代码生成
│
├── 文档
├── docs/
│   ├── INTEGRATED_EVAL_GUIDE.md       # 详细指南
│   ├── QUICK_START_EVAL.md            # 快速开始
│   └── IMPLEMENTATION_COMPLETE.md     # 实现报告
│
├── 示例
├── example_ids.txt                    # 示例 ID 列表
│
└── SWE-bench_Pro-os/                  # 官方评估系统（完整）
    ├── swe_bench_pro_eval.py
    ├── helper_code/
    ├── dockerfiles/
    ├── run_scripts/                   # 1000+ 测试脚本
    └── ...
```

## 独立部署步骤

### 1. 复制整个目录

```bash
# 将整个 swe_bench_integrated_eval 目录复制到目标机器
scp -r swe_bench_integrated_eval/ user@remote:/path/to/dest/

# 或打包传输
tar -czf swe_bench_integrated_eval.tar.gz swe_bench_integrated_eval/
scp swe_bench_integrated_eval.tar.gz user@remote:/path/to/dest/
ssh user@remote "cd /path/to/dest && tar -xzf swe_bench_integrated_eval.tar.gz"
```

### 2. 准备额外依赖

```bash
cd swe_bench_integrated_eval

# 安装 Python 依赖
pip install pandas docker

# 确认 Docker 运行
docker --version
docker ps
```

### 3. 准备测试数据

```bash
# 需要从其他地方获取 swe_bench_pro_test.csv
# 放到当前目录或记住路径用于后续指定
cp /path/to/swe_bench_pro_test.csv ./
```

### 4. 配置执行权限

```bash
chmod +x run_batch_by_ids.sh
chmod +x run_batch.sh
chmod +x evaluate_single_instance.py
chmod +x summarize_eval_results.py
```

### 5. 测试运行

```bash
# 使用示例文件测试（假设 example_ids.txt 包含有效的 instance IDs）
bash run_batch_by_ids.sh \
  --ids-file ./example_ids.txt \
  --model "Claude Sonnet 4.6" \
  --enable-eval
```

## 环境要求

### 必需
- ✅ Python 3.8+
- ✅ Docker（运行中）
- ✅ `pandas` 包
- ✅ `docker` Python 包
- ✅ 16GB+ 内存（推荐）
- ✅ 足够的磁盘空间（Docker 镜像 + 结果）

### 可选
- Conda 环境（用于 DUCC）
- Modal 账号（如果不用本地 Docker）

## 与原目录的区别

### 原目录结构（混乱）
```
test/
├── SWE-bench_Pro-os/
├── evaluate_single_instance.py
├── summarize_eval_results.py
├── run_batch_by_ids.sh
├── run_batch.sh
├── test_tmux_cc_experience.py
├── swe_bench_pro_test.csv
├── INTEGRATED_EVAL_GUIDE.md
├── QUICK_START_EVAL.md
├── ... (其他50+个文件)
└── ... (杂乱的文档和脚本)
```

### 打包后结构（清晰）
```
swe_bench_integrated_eval/          # 独立工具包
├── README.md                        # 清晰的主文档
├── QUICK_START.md                   # 快速开始
├── DEPLOYMENT.md                    # 部署说明
├── 核心脚本（5个）
├── docs/（3个文档）
├── example_ids.txt
└── SWE-bench_Pro-os/（完整）
```

## 文件完整性检查

```bash
cd swe_bench_integrated_eval

# 检查核心脚本
ls -l evaluate_single_instance.py
ls -l summarize_eval_results.py
ls -l run_batch_by_ids.sh
ls -l run_batch.sh
ls -l test_tmux_cc_experience.py

# 检查 SWE-bench_Pro-os
ls -l SWE-bench_Pro-os/swe_bench_pro_eval.py
ls -l SWE-bench_Pro-os/helper_code/
ls -l SWE-bench_Pro-os/dockerfiles/
ls -l SWE-bench_Pro-os/run_scripts/ | wc -l  # 应该有 1000+ 个

# 检查文档
ls -l docs/
ls -l README.md
ls -l QUICK_START.md
```

## 依赖关系图

```
run_batch_by_ids.sh
├─> test_tmux_cc_experience.py
│   └─> DUCC API / Claude API
│
└─> evaluate_single_instance.py
    └─> SWE-bench_Pro-os/swe_bench_pro_eval.py
        ├─> SWE-bench_Pro-os/helper_code/image_uri.py
        ├─> SWE-bench_Pro-os/dockerfiles/
        ├─> SWE-bench_Pro-os/run_scripts/
        └─> Docker

summarize_eval_results.py
└─> evaluation/batch/eval_results/*.json
```

## 打包清单

### ✅ 已包含
- 所有核心 Python 脚本
- 所有 Shell 脚本
- 完整的 SWE-bench_Pro-os 目录
- 所有相关文档
- 示例 ID 列表

### ❌ 需要额外准备
- `swe_bench_pro_test.csv`（测试数据文件）
- Docker Hub 镜像访问权限
- Python 环境和依赖包
- DUCC/Claude API 配置（如果使用）

## 迁移现有数据

如果已经有评估结果想迁移：

```bash
# 复制 evaluation 目录
cp -r /old/path/evaluation ./

# 重新生成汇总报告
python summarize_eval_results.py \
  --eval-results-dir ./evaluation/batch/eval_results \
  --output-file ./evaluation/batch/summary.json
```

## Docker 镜像说明

工具需要访问 Docker Hub 上的 SWE-bench Pro 镜像：

```
{dockerhub_username}/sweap-images:{instance_tag}
```

默认用户名是 `jefzda`，可通过 `--dockerhub-username` 参数修改。

## 网络要求

- 访问 Docker Hub（拉取镜像）
- 访问 AI API（如果使用 Claude/DUCC）
- 可选：访问 Modal（如果不用本地 Docker）

## 性能建议

### 并发配置
```bash
# 小型机器（8GB 内存）
--parallel 2

# 中型机器（16GB 内存）
--parallel 3

# 大型机器（32GB+ 内存）
--parallel 5
```

### 磁盘空间
- Docker 镜像: ~5-10GB（缓存后）
- 每个 instance 评估结果: ~1-5MB
- 日志文件: 视任务数量而定

## 备份建议

重要文件：
```bash
# 定期备份评估结果
tar -czf backup_$(date +%Y%m%d).tar.gz evaluation/

# 备份配置和日志
tar -czf logs_$(date +%Y%m%d).tar.gz evaluation/logs/
```

## 故障恢复

### 中断恢复
直接重新运行相同命令，脚本会自动跳过已完成任务。

### 清理重来
```bash
# 删除所有结果
rm -rf evaluation/

# 重新开始
bash run_batch_by_ids.sh --ids-file ./ids.txt --model claude --enable-eval
```

## 版本管理

建议使用 Git 管理脚本修改：

```bash
cd swe_bench_integrated_eval
git init
git add .
git commit -m "Initial commit"
```

## 更新说明

如果 SWE-bench Pro 官方更新：

```bash
# 备份当前版本
cp -r SWE-bench_Pro-os SWE-bench_Pro-os.backup

# 获取新版本
git clone https://github.com/xxx/SWE-bench_Pro-os.git
# 或从其他渠道获取

# 替换
rm -rf SWE-bench_Pro-os
mv /path/to/new/SWE-bench_Pro-os ./
```

## 支持

- 主文档: [README.md](./README.md)
- 快速开始: [QUICK_START.md](./QUICK_START.md)
- 详细指南: [docs/INTEGRATED_EVAL_GUIDE.md](./docs/INTEGRATED_EVAL_GUIDE.md)

---

部署完成后，请查看 [QUICK_START.md](./QUICK_START.md) 开始使用！
