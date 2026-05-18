# 开始前检查清单

在运行集成评估之前，请确保以下所有项目都已就绪。

## ✅ 必需文件检查

### 1. swe_bench_pro_test.csv（必需）

```bash
# 检查文件是否存在
ls -lh ../swe_bench_pro_test.csv

# 或检查当前目录
ls -lh ./swe_bench_pro_test.csv
```

**如果文件不存在**:
```bash
# 从其他位置复制
cp /path/to/swe_bench_pro_test.csv ./

# 或复制到上层目录
cp /path/to/swe_bench_pro_test.csv ../
```

**验证文件内容**:
```bash
# 查看前几行
head -5 swe_bench_pro_test.csv

# 应该包含列: instance_id, fail_to_pass, pass_to_pass, etc.
```

### 2. Instance ID 列表文件（必需）

```bash
# 使用示例文件
cat example_ids.txt

# 或创建自己的
cat > my_ids.txt << EOF
instance_django__django-12345
instance_flask__flask-67890
EOF
```

**格式要求**:
- 每行一个 instance_id
- 支持 `#` 开头的注释行
- 支持空行（会自动跳过）

### 3. SWE-bench_Pro-os 目录（已包含）

```bash
# 验证目录存在
ls -d SWE-bench_Pro-os/

# 验证关键文件
ls SWE-bench_Pro-os/swe_bench_pro_eval.py
ls -d SWE-bench_Pro-os/run_scripts/
```

## ✅ 环境依赖检查

### 1. Python 3.8+

```bash
python3 --version
# 应该输出: Python 3.8.x 或更高
```

### 2. 必需的 Python 包

```bash
# 检查 pandas
python3 -c "import pandas; print(pandas.__version__)"

# 检查 docker
python3 -c "import docker; print(docker.__version__)"
```

**如果缺少包**:
```bash
pip install pandas docker
```

### 3. Docker 运行检查

```bash
# 检查 Docker 版本
docker --version

# 检查 Docker 是否运行
docker ps

# 如果提示权限错误，可能需要 sudo
sudo docker ps
```

## ✅ 参数配置检查

### 默认参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| CSV 文件 | `../swe_bench_pro_test.csv` | 上层目录 |
| Scripts 目录 | `./SWE-bench_Pro-os/run_scripts` | 当前目录下 |
| Docker Hub 用户名 | `jefzda` | 官方镜像用户名 |
| 输出目录 | `./evaluation/batch/{model}_swe_bench_output_ids/` | 自动创建 |

### 需要修改的情况

#### 情况 1: CSV 文件位置不同

```bash
# 如果 CSV 在其他位置，使用 --raw-sample-csv 指定
bash run_batch_by_ids.sh \
  --ids-file ./my_ids.txt \
  --model claude \
  --enable-eval \
  --raw-sample-csv /path/to/swe_bench_pro_test.csv
```

#### 情况 2: 使用不同的 Docker Hub 用户名

```bash
bash run_batch_by_ids.sh \
  --ids-file ./my_ids.txt \
  --model claude \
  --enable-eval \
  --dockerhub-username your_username
```

## ✅ 输出目录结构预览

运行后会自动创建以下目录结构：

```
./evaluation/
├── batch/
│   ├── {model}_swe_bench_output_ids/      # 生成的 predictions
│   │   ├── predictions/
│   │   │   ├── instance_xxx.json          # 每个 instance 的结果
│   │   │   └── ...
│   │   └── all_preds.jsonl                # JSONL 格式（自动生成）
│   │
│   ├── eval_results/                       # 评估结果（启用 --enable-eval）
│   │   ├── instance_xxx_eval.json
│   │   └── ...
│   │
│   ├── eval_summary_{model}.json           # ⭐ 摘要报告
│   └── eval_detailed_{model}.json          # 详细结果
│
└── logs/
    ├── run_batch_ids_master_*.log          # 主日志
    ├── {model}_ids_*.log                   # 生成日志
    └── {model}_eval_*.log                  # 评估日志
```

**所有目录都会自动创建，无需手动创建！**

## ✅ 快速验证命令

运行这个命令进行完整验证：

```bash
bash verify.sh
```

验证脚本会检查：
- ✅ 核心脚本是否存在
- ✅ 文档是否完整
- ✅ SWE-bench_Pro-os 是否完整
- ✅ Python 依赖是否安装
- ✅ Docker 是否运行
- ✅ 文件权限是否正确

## ✅ 最小可运行示例

确保以下文件存在，就可以运行：

```bash
# 1. 检查必需文件
ls swe_bench_integrated_eval/swe_bench_pro_test.csv  # 或 ../swe_bench_pro_test.csv
ls swe_bench_integrated_eval/example_ids.txt
ls swe_bench_integrated_eval/SWE-bench_Pro-os/

# 2. 运行最简单的命令
cd swe_bench_integrated_eval
bash run_batch_by_ids.sh \
  --ids-file ./example_ids.txt \
  --model "Claude Sonnet 4.6" \
  --enable-eval
```

## ❌ 常见问题

### 问题 1: "CSV 文件不存在"

**错误信息**: `Instance not found in CSV` 或 `CSV file not found`

**解决方法**:
```bash
# 检查 CSV 文件位置
ls ../swe_bench_pro_test.csv

# 如果不存在，复制或指定路径
cp /path/to/swe_bench_pro_test.csv ./
bash run_batch_by_ids.sh --raw-sample-csv ./swe_bench_pro_test.csv ...
```

### 问题 2: "Docker 镜像拉取失败"

**错误信息**: `Failed to pull image`

**解决方法**:
```bash
# 检查 Docker 是否运行
docker ps

# 手动测试拉取
docker pull jefzda/sweap-images:test
```

### 问题 3: "Python 包缺失"

**错误信息**: `ModuleNotFoundError: No module named 'pandas'`

**解决方法**:
```bash
pip install pandas docker
```

## ✅ 检查清单总结

在运行前，确认以下所有项：

- [ ] `swe_bench_pro_test.csv` 文件存在（当前或上层目录）
- [ ] Instance ID 列表文件准备好
- [ ] Python 3.8+ 已安装
- [ ] `pandas` 和 `docker` Python 包已安装
- [ ] Docker 正在运行
- [ ] SWE-bench_Pro-os 目录完整
- [ ] 磁盘空间充足（建议 10GB+）
- [ ] 网络可访问 Docker Hub

**全部确认后，查看**: [QUICK_START.md](./QUICK_START.md) 开始使用！
