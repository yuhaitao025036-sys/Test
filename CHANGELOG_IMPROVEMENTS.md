# 改进说明文档

## 概述

本次对 `test_tmux_cc_experience.py` 进行了重大改进，主要包括：

1. ✅ 优化 Prompt 格式
2. ✅ 完整的日志保存
3. ✅ 任务执行轨迹记录
4. ✅ 独立的任务目录结构
5. ✅ 与数据集完整对应

## 改进详情

### 1. Prompt 优化

#### 问题
- 原始 prompt 可能包含转义字符（如 `\n`）
- 输出约束不够明确，ducc 可能生成多余内容

#### 解决方案
修改了 `_build_prompt()` 方法（第 750-790 行）：

```python
# 清理 problem_statement
if problem_stmt.startswith('"') and problem_stmt.endswith('"'):
    problem_stmt = problem_stmt[1:-1]
problem_stmt = problem_stmt.replace('\\n', '\n')

# 更明确的输出要求
"Output ONLY the patch in unified diff format (no explanations)"
"Do not include any explanation or commentary, only output the diff."
```

**效果**：
- 移除多余的引号和转义字符
- 强调只输出 diff，不要解释
- 提高 patch 提取成功率

---

### 2. 日志保存改进

#### 问题
- 原来的 prompt 在控制台只打印前 200 字符，看不到完整内容
- ducc 执行日志没有保存，出问题无法回溯

#### 解决方案

**A. Prompt 保存**（第 325-332 行）
```python
if task_dir:
    prompt_file = os.path.join(task_dir, 'prompt.txt')
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt)
```

**B. 控制台输出改进**（第 334-341 行）
```python
# 不再截断，而是显示统计信息
print(f"  prompt 长度: {len(prompt)} 字符")
print(f"  Prompt 预览 (前5行):")
for i, line in enumerate(lines[:5], 1):
    print(f"    {i}. {line[:80]}{'...' if len(line) > 80 else ''}")
```

**C. Ducc 执行日志保存**（第 372-406 行）
```python
# 保存完整输出到日志文件
with open(log_file, 'w', encoding='utf-8') as f:
    f.write("=" * 80 + "\n")
    f.write("DUCC 执行日志\n")
    f.write("=" * 80 + "\n")
    f.write(f"开始时间: ...\n")
    f.write(f"执行耗时: {duration:.2f}秒\n")
    f.write(f"退出码: {result.returncode}\n")
    f.write("\nSTDOUT:\n")
    f.write(result.stdout)
    f.write("\nSTDERR:\n")
    f.write(result.stderr)
```

**效果**：
- ✅ 完整 prompt 可查
- ✅ 执行日志永久保存
- ✅ stdout/stderr 分开记录
- ✅ 包含时间、退出码等元信息

---

### 3. 任务执行轨迹记录

#### 新增文件
每个任务现在会保存以下轨迹文件：

| 文件名 | 内容 | 用途 |
|--------|------|------|
| `prompt.txt` | 发送给 ducc 的完整 prompt | 检查 prompt 是否正确 |
| `ducc_execution.log` | ducc 完整执行日志 | 分析执行过程，排查问题 |
| `ducc_raw_output.txt` | ducc 原始输出 | 查看 ducc 返回的原始内容 |
| `extracted_patch.diff` | 提取的 patch | 直接查看和应用 patch |
| `validation_result.json` | 验证结果详情 | 分析测试通过/失败情况 |
| `dataset_info.json` | 数据集原始信息 | 与数据集对应 |
| `task_summary.json` | 任务执行摘要 | 快速了解任务状态 |
| `README.txt` | 文本格式摘要 | 人类可读的摘要 |

---

### 4. 独立任务目录结构

#### 问题
- 原来所有文件混在一起，难以管理
- 批量运行时找不到特定任务的文件

#### 解决方案
新的目录结构：

```
swe_bench_output_ducc/
├── tasks/                          # 每个任务的详细信息
│   ├── django__django-12345/       # 任务独立目录（以 instance_id 命名）
│   │   ├── dataset_info.json       # 数据集信息
│   │   ├── prompt.txt              # 完整 prompt
│   │   ├── ducc_execution.log      # 执行日志
│   │   ├── ducc_raw_output.txt     # 原始输出
│   │   ├── extracted_patch.diff    # 提取的 patch
│   │   ├── validation_result.json  # 验证结果
│   │   ├── task_summary.json       # 任务摘要
│   │   └── README.txt              # 文本摘要
│   ├── flask__flask-67890/
│   │   └── ...
│   └── ...
├── predictions/                    # SWE-bench 标准格式（用于官方评估）
│   ├── django__django-12345.json
│   └── ...
├── django__django-12345_full.json  # 向后兼容（根目录）
├── all_preds.jsonl                 # 所有预测（JSONL格式）
└── report.json                     # 评测报告
```

**优势**：
- ✅ 每个任务有独立目录，文件组织清晰
- ✅ 目录名 = instance_id，易于查找
- ✅ 所有相关文件集中在一起
- ✅ 支持批量处理时的并发和断点续传

---

### 5. 与数据集完整对应

#### 保存的数据集信息（`dataset_info.json`）

```json
{
  "instance_id": "django__django-12345",
  "repo": "django/django",
  "repo_language": "Python",
  "problem_statement": "完整的问题描述...",
  "requirements": "依赖要求...",
  "interface": "接口说明...",
  "dockerhub_tag": "镜像标签",
  "base_commit": "基础提交",
  "hints": "提示信息",
  "created_at": "创建时间"
}
```

**用途**：
- 追溯任务来源
- 对比数据集和处理结果
- 分析不同类型任务的成功率
- 重现问题场景

---

### 6. 任务摘要（`task_summary.json` 和 `README.txt`）

#### JSON 格式摘要

```json
{
  "instance_id": "django__django-12345",
  "start_time": "2026-04-27 10:30:00",
  "end_time": "2026-04-27 10:35:30",
  "duration_seconds": 330.5,
  "patch_generated": true,
  "patch_length": 1523,
  "validation_performed": true,
  "validation_success": false,
  "error": "",
  "task_directory": "/path/to/tasks/django__django-12345",
  "validation_details": {
    "test_output_length": 5234,
    "exit_code": 1,
    "test_duration": 45.3,
    "stats": {
      "passed": 10,
      "failed": 2,
      "errors": 0
    }
  }
}
```

#### 文本格式摘要（`README.txt`）

```
================================================================================
SWE-bench 任务执行摘要
================================================================================

任务 ID: django__django-12345
开始时间: 2026-04-27 10:30:00
结束时间: 2026-04-27 10:35:30
执行耗时: 330.50秒

Patch 生成: ✓ 是
Patch 长度: 1523 字符

验证执行: ✓ 是
验证结果: ✗ 失败
  - 退出码: 1
  - 测试耗时: 45.30秒
  - 通过: 10
  - 失败: 2
  - 错误: 0

================================================================================
文件说明:
================================================================================
  dataset_info.json      - 数据集原始信息
  prompt.txt             - 发送给 ducc 的 prompt
  ducc_execution.log     - ducc 执行日志（含stdout/stderr）
  ducc_raw_output.txt    - ducc 原始输出
  extracted_patch.diff   - 提取的 patch
  validation_result.json - 验证结果详情
  task_summary.json      - 任务摘要（JSON格式）
  README.txt             - 本文件（文本摘要）
```

**优势**：
- 快速了解任务执行情况
- 不需要查看日志就知道成功/失败
- JSON 格式便于程序分析
- TXT 格式便于人类阅读

---

## 使用示例

### 基础用法（与之前相同）

```bash
# 直接模式
python3 test_tmux_cc_experience.py --max-tasks 2 --no-validate

# tmux 模式
python3 test_tmux_cc_experience.py --index 0 --use-tmux --no-validate
```

### 查看任务详情

```bash
# 查看任务摘要
cat swe_bench_output_ducc/tasks/django__django-12345/README.txt

# 查看完整 prompt
cat swe_bench_output_ducc/tasks/django__django-12345/prompt.txt

# 查看执行日志
cat swe_bench_output_ducc/tasks/django__django-12345/ducc_execution.log

# 查看 patch
cat swe_bench_output_ducc/tasks/django__django-12345/extracted_patch.diff

# 应用 patch（手动测试）
cd /path/to/repo
git apply swe_bench_output_ducc/tasks/django__django-12345/extracted_patch.diff
```

### 批量分析

```bash
# 统计成功率
jq '.validation_success' swe_bench_output_ducc/tasks/*/task_summary.json | grep -c true

# 找出失败的任务
jq -r 'select(.validation_success == false) | .instance_id' swe_bench_output_ducc/tasks/*/task_summary.json

# 统计平均执行时间
jq '.duration_seconds' swe_bench_output_ducc/tasks/*/task_summary.json | awk '{sum+=$1; count++} END {print sum/count}'

# 按执行时间排序
jq -r '[.instance_id, .duration_seconds] | @tsv' swe_bench_output_ducc/tasks/*/task_summary.json | sort -k2 -n
```

---

## 向后兼容

本次改进**完全向后兼容**：

1. ✅ 原有的输出文件仍然生成：
   - `predictions/*.json` （SWE-bench 标准格式）
   - `*_full.json` （完整结果）
   - `all_preds.jsonl` （JSONL格式）
   - `report.json` （评测报告）

2. ✅ 命令行参数不变：
   - `--index`, `--max-tasks`, `--no-validate`, `--use-tmux` 等

3. ✅ API 兼容：
   - `evaluate_single()` 返回值格式不变
   - 只是增加了 `task_dir` 字段

---

## 性能影响

### 额外开销
- 文件 I/O: 每个任务约 5-10 个文件，总大小约 100KB - 1MB
- 时间: 文件写入约 0.1-0.3 秒（可忽略）

### 优化建议
如需进一步优化性能：
1. 可选的日志保存：添加 `--no-logs` 参数跳过日志保存
2. 异步写入：使用异步 I/O 写入日志文件
3. 压缩存储：对大日志文件进行 gzip 压缩

---

## 故障排查指南

### 1. Prompt 格式问题

**症状**：生成的 patch 质量差或为空

**排查步骤**：
```bash
# 查看 prompt 是否正确
cat swe_bench_output_ducc/tasks/<instance_id>/prompt.txt

# 检查是否有转义字符
cat swe_bench_output_ducc/tasks/<instance_id>/prompt.txt | cat -A
```

### 2. Ducc 执行失败

**症状**：任务显示失败，不知道原因

**排查步骤**：
```bash
# 查看执行日志
cat swe_bench_output_ducc/tasks/<instance_id>/ducc_execution.log

# 查看退出码
jq '.validation_details.exit_code' swe_bench_output_ducc/tasks/<instance_id>/task_summary.json

# 查看 stderr
grep "STDERR:" -A 50 swe_bench_output_ducc/tasks/<instance_id>/ducc_execution.log
```

### 3. Patch 提取问题

**症状**：ducc 有输出，但 patch 为空

**排查步骤**：
```bash
# 对比原始输出和提取的 patch
cat swe_bench_output_ducc/tasks/<instance_id>/ducc_raw_output.txt
cat swe_bench_output_ducc/tasks/<instance_id>/extracted_patch.diff

# 检查输出中是否包含 diff
grep -i "diff" swe_bench_output_ducc/tasks/<instance_id>/ducc_raw_output.txt
```

### 4. 验证失败分析

**症状**：patch 已生成，但验证失败

**排查步骤**：
```bash
# 查看验证详情
cat swe_bench_output_ducc/tasks/<instance_id>/validation_result.json | jq .

# 查看失败的测试
jq '.stats' swe_bench_output_ducc/tasks/<instance_id>/validation_result.json

# 查看测试输出
jq -r '.test_output' swe_bench_output_ducc/tasks/<instance_id>/validation_result.json
```

---

## 数据分析示例

### 示例 1：找出耗时最长的任务

```bash
#!/bin/bash
echo "Top 10 耗时最长的任务:"
jq -r '[.instance_id, .duration_seconds] | @tsv' \
  swe_bench_output_ducc/tasks/*/task_summary.json \
  | sort -k2 -rn \
  | head -10 \
  | awk '{printf "%-50s %8.2fs\n", $1, $2}'
```

### 示例 2：按语言统计成功率

```bash
#!/bin/bash
for lang in Python JavaScript Go Rust; do
  total=$(jq -r "select(.repo_language == \"$lang\") | .instance_id" \
    swe_bench_output_ducc/tasks/*/dataset_info.json | wc -l)
  
  success=$(jq -r "select(.validation_success == true) | .instance_id" \
    swe_bench_output_ducc/tasks/*/task_summary.json | wc -l)
  
  echo "$lang: $success/$total ($(echo "scale=2; $success*100/$total" | bc)%)"
done
```

### 示例 3：生成失败任务报告

```bash
#!/bin/bash
echo "失败任务详细报告" > failed_tasks_report.txt
echo "===================" >> failed_tasks_report.txt

jq -r 'select(.validation_success == false) | .instance_id' \
  swe_bench_output_ducc/tasks/*/task_summary.json \
  | while read id; do
    echo "" >> failed_tasks_report.txt
    echo "任务: $id" >> failed_tasks_report.txt
    cat "swe_bench_output_ducc/tasks/$id/README.txt" >> failed_tasks_report.txt
    echo "---" >> failed_tasks_report.txt
  done

echo "报告已生成: failed_tasks_report.txt"
```

---

## 总结

### 改进成果

| 改进项 | 状态 | 效果 |
|--------|------|------|
| Prompt 优化 | ✅ | 提高 patch 质量 |
| 日志保存 | ✅ | 完整记录执行过程 |
| 轨迹记录 | ✅ | 便于问题排查 |
| 目录结构 | ✅ | 清晰的文件组织 |
| 数据集对应 | ✅ | 完整的可追溯性 |
| 任务摘要 | ✅ | 快速了解状态 |
| 向后兼容 | ✅ | 不影响现有工作流 |

### 下一步建议

1. **性能优化**：如需处理大规模数据，考虑添加 `--no-logs` 选项
2. **可视化**：基于 `task_summary.json` 创建 Web Dashboard
3. **分析工具**：编写脚本自动分析失败原因
4. **数据库存储**：将摘要信息存入数据库便于查询

### 立即开始

```bash
# 运行单个任务（查看完整输出）
python3 test_tmux_cc_experience.py --index 0 --no-validate

# 查看任务目录
ls -la swe_bench_output_ducc/tasks/<instance_id>/

# 查看摘要
cat swe_bench_output_ducc/tasks/<instance_id>/README.txt
```

---

## 反馈和问题

如有问题或建议，请查看：
- `TEST_TMUX_INTEGRATION.md` - 测试指南
- `SWE_BENCH_TMUX_USAGE.md` - 详细使用文档
- `QUICK_START.md` - 快速开始指南
