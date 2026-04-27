# 快速参考 - 改进后的功能

## 🎯 主要改进

### 1. 每个任务都有独立目录

```
swe_bench_output_ducc/tasks/django__django-12345/
├── dataset_info.json       # 数据集原始信息
├── prompt.txt              # 完整 prompt
├── ducc_execution.log      # 执行日志（stdout/stderr）
├── ducc_raw_output.txt     # ducc 原始输出
├── extracted_patch.diff    # 提取的 patch
├── validation_result.json  # 验证结果详情
├── task_summary.json       # JSON 格式摘要
└── README.txt              # 人类可读摘要
```

### 2. Prompt 已优化

- ✅ 移除了转义字符（`\n` → 真实换行）
- ✅ 移除了多余引号
- ✅ 更明确的输出要求（只要 diff，不要解释）

### 3. 完整日志保存

- ✅ Prompt 完整保存
- ✅ Ducc stdout/stderr 分开记录
- ✅ 执行时间、退出码等元信息
- ✅ Tmux 模式也会保存日志

## 🚀 使用方法

### 运行任务（不变）

```bash
# 直接模式
python3 test_tmux_cc_experience.py --max-tasks 2 --no-validate

# Tmux 模式
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate
```

### 查看任务详情（新功能）

```bash
# 快速查看摘要
cat swe_bench_output_ducc/tasks/<instance_id>/README.txt

# 查看 prompt
cat swe_bench_output_ducc/tasks/<instance_id>/prompt.txt

# 查看执行日志
cat swe_bench_output_ducc/tasks/<instance_id>/ducc_execution.log

# 查看生成的 patch
cat swe_bench_output_ducc/tasks/<instance_id>/extracted_patch.diff

# 查看 JSON 摘要
jq . swe_bench_output_ducc/tasks/<instance_id>/task_summary.json
```

## 📊 批量分析

### 统计成功率

```bash
# 总任务数
ls -d swe_bench_output_ducc/tasks/*/ | wc -l

# 成功的任务
jq -r 'select(.validation_success == true) | .instance_id' \
  swe_bench_output_ducc/tasks/*/task_summary.json | wc -l

# 失败的任务
jq -r 'select(.validation_success == false) | .instance_id' \
  swe_bench_output_ducc/tasks/*/task_summary.json
```

### 平均执行时间

```bash
jq '.duration_seconds' swe_bench_output_ducc/tasks/*/task_summary.json \
  | awk '{sum+=$1; count++} END {print "平均: " sum/count " 秒"}'
```

### 找出最慢的任务

```bash
jq -r '[.instance_id, .duration_seconds] | @tsv' \
  swe_bench_output_ducc/tasks/*/task_summary.json \
  | sort -k2 -rn | head -10
```

## 🔍 故障排查

### Prompt 有问题？

```bash
# 查看完整 prompt
cat swe_bench_output_ducc/tasks/<instance_id>/prompt.txt

# 检查是否还有转义字符
cat swe_bench_output_ducc/tasks/<instance_id>/prompt.txt | grep '\\n'
```

### Ducc 执行失败？

```bash
# 查看执行日志
cat swe_bench_output_ducc/tasks/<instance_id>/ducc_execution.log

# 查看退出码
jq '.validation_details.exit_code' \
  swe_bench_output_ducc/tasks/<instance_id>/task_summary.json
```

### Patch 没提取出来？

```bash
# 对比原始输出和提取结果
diff \
  <(cat swe_bench_output_ducc/tasks/<instance_id>/ducc_raw_output.txt) \
  <(cat swe_bench_output_ducc/tasks/<instance_id>/extracted_patch.diff)

# 查看原始输出中是否有 diff
grep -C 5 "diff --git" \
  swe_bench_output_ducc/tasks/<instance_id>/ducc_raw_output.txt
```

### 验证失败？

```bash
# 查看验证详情
cat swe_bench_output_ducc/tasks/<instance_id>/validation_result.json | jq .

# 查看失败统计
jq '.stats' swe_bench_output_ducc/tasks/<instance_id>/validation_result.json
```

## 📁 目录结构一览

```
swe_bench_output_ducc/
├── tasks/                          # 🆕 每个任务的详细信息
│   ├── django__django-12345/       # 任务独立目录
│   │   ├── dataset_info.json       # 🆕 数据集信息
│   │   ├── prompt.txt              # 🆕 完整 prompt
│   │   ├── ducc_execution.log      # 🆕 执行日志
│   │   ├── ducc_raw_output.txt     # 🆕 原始输出
│   │   ├── extracted_patch.diff    # 🆕 提取的 patch
│   │   ├── validation_result.json  # 🆕 验证结果
│   │   ├── task_summary.json       # 🆕 JSON 摘要
│   │   └── README.txt              # 🆕 文本摘要
│   └── ...
├── predictions/                    # ✅ 保留（SWE-bench 标准格式）
│   ├── django__django-12345.json
│   └── ...
├── django__django-12345_full.json  # ✅ 保留（向后兼容）
├── all_preds.jsonl                 # ✅ 保留（JSONL 格式）
└── report.json                     # ✅ 保留（评测报告）
```

## 💡 实用技巧

### 1. 快速定位失败任务

```bash
# 创建失败任务列表
jq -r 'select(.validation_success == false) | .instance_id' \
  swe_bench_output_ducc/tasks/*/task_summary.json \
  > failed_tasks.txt

# 逐个查看
while read id; do
  echo "=== $id ==="
  cat "swe_bench_output_ducc/tasks/$id/README.txt"
  echo ""
done < failed_tasks.txt
```

### 2. 导出所有 patch

```bash
# 创建 patches 目录
mkdir -p all_patches

# 复制所有 patch
for dir in swe_bench_output_ducc/tasks/*/; do
  id=$(basename "$dir")
  if [ -f "$dir/extracted_patch.diff" ]; then
    cp "$dir/extracted_patch.diff" "all_patches/$id.diff"
  fi
done
```

### 3. 生成 HTML 报告

```bash
# 简单的 HTML 报告
cat > report.html << 'EOF'
<!DOCTYPE html>
<html>
<head><title>SWE-bench 评测报告</title></head>
<body>
<h1>任务执行报告</h1>
<table border="1">
<tr><th>任务 ID</th><th>耗时</th><th>Patch</th><th>验证</th></tr>
EOF

jq -r '[.instance_id, .duration_seconds, .patch_generated, .validation_success] | @tsv' \
  swe_bench_output_ducc/tasks/*/task_summary.json \
  | while IFS=$'\t' read id duration patch valid; do
    echo "<tr><td>$id</td><td>${duration}s</td><td>$patch</td><td>$valid</td></tr>" >> report.html
  done

echo "</table></body></html>" >> report.html
echo "报告已生成: report.html"
```

## 🎓 示例场景

### 场景 1：调试单个失败任务

```bash
# 1. 运行任务
python3 test_tmux_cc_experience.py --index 5

# 2. 查看摘要
cat swe_bench_output_ducc/tasks/<instance_id>/README.txt

# 3. 如果失败，查看日志
cat swe_bench_output_ducc/tasks/<instance_id>/ducc_execution.log

# 4. 检查 prompt
cat swe_bench_output_ducc/tasks/<instance_id>/prompt.txt

# 5. 手动测试 patch
cd /path/to/repo
git apply swe_bench_output_ducc/tasks/<instance_id>/extracted_patch.diff
pytest
```

### 场景 2：批量运行并分析

```bash
# 1. 批量运行
python3 test_tmux_cc_experience.py --max-tasks 50 --no-validate

# 2. 统计结果
total=$(ls -d swe_bench_output_ducc/tasks/*/ | wc -l)
with_patch=$(jq -r 'select(.patch_generated == true) | .instance_id' \
  swe_bench_output_ducc/tasks/*/task_summary.json | wc -l)

echo "总任务: $total"
echo "生成 patch: $with_patch"
echo "成功率: $(echo "scale=2; $with_patch*100/$total" | bc)%"

# 3. 找出问题任务
jq -r 'select(.patch_generated == false) | .instance_id' \
  swe_bench_output_ducc/tasks/*/task_summary.json
```

## 📖 文档索引

| 文档 | 内容 |
|------|------|
| `CHANGELOG_IMPROVEMENTS.md` | 📋 详细改进说明（本文档的扩展版） |
| `QUICK_START.md` | 🚀 快速开始指南 |
| `SWE_BENCH_TMUX_USAGE.md` | 📖 完整使用文档 |
| `TEST_TMUX_INTEGRATION.md` | 🧪 测试指南 |

## ✅ 向后兼容

所有原有功能**完全保留**，不影响现有工作流：

- ✅ 命令行参数相同
- ✅ 输出文件格式相同
- ✅ API 兼容
- ✅ 只是**增加**了新功能

## 🎉 立即开始

```bash
# 试试新功能！
python3 test_tmux_cc_experience.py --index 0 --no-validate

# 查看任务目录
ls -la swe_bench_output_ducc/tasks/*/

# 查看第一个任务的摘要
cat swe_bench_output_ducc/tasks/*/README.txt | head -50
```
