# SWE-bench 评估失败分析指南

## 📊 快速分析

已经为你分析了当前批次的评估结果！

### 总体情况

| 指标 | 数值 |
|------|------|
| 总任务数 | 64 |
| 成功任务 | 50 (78%) |
| 失败任务 | 14 (22%) |

---

## 🔍 失败原因分析

### 主要失败原因

1. **💾 磁盘空间不足 (12个, 85.7%)**
   - 这是最主要的失败原因
   - 已通过修改 `/tmp` 为 `/ssd1/Dejavu/tmp` 解决
   - 影响项目：
     - gravitational/teleport: 8次
     - protonmail/webclients: 3次  
     - element-hq/element-web: 1次

2. **📝 未生成 Patch (2个, 14.3%)**
   - internetarchive/openlibrary: 2次
   - 可能原因：代码库太大、超时、或 AI 理解问题

---

## 🏗️ 项目维度分析

### ❌ 完全失败的项目（需要重点关注）

#### gravitational/teleport (0/8, 0%)
- **失败原因**：全部因磁盘空间不足
- **特点**：可能是大型 Go 项目，代码库庞大
- **建议**：修复磁盘问题后重跑

#### protonmail/webclients (0/3, 0%)
- **失败原因**：全部因磁盘空间不足
- **特点**：可能是大型前端项目
- **建议**：修复磁盘问题后重跑

### ⚠️ 部分失败的项目

#### internetarchive/openlibrary (8/10, 80%)
- **失败原因**：未生成有效 Patch
- **特点**：Python 项目，大多数成功
- **建议**：可能需要调整超时或 prompt

#### element-hq/element-web (5/6, 83%)
- **失败原因**：磁盘空间不足（1次）
- **建议**：修复磁盘问题后重跑失败的任务

### ✅ 完全成功的项目（表现优秀）

- NodeBB/NodeBB (5/5, 100%)
- qutebrowser/qutebrowser (7/7, 100%)
- ansible/ansible (9/9, 100%)
- navidrome/navidrome (5/5, 100%)
- future-architect/vuls (5/5, 100%)
- flipt-io/flipt (6/6, 100%)

---

## 🛠️ 使用分析工具

### 基本用法

```bash
# 分析当前批次
python analyze_failures.py

# 指定文件
python analyze_failures.py --log ./batch_0_50.log --preds ./all_preds.jsonl

# 保存报告到指定目录
python analyze_failures.py --output ./my_analysis
```

### 查看详细报告

```bash
# 查看 JSON 格式的完整报告
cat failure_analysis/failure_analysis.json | jq .

# 查看失败任务索引
cat failure_analysis/failed_task_indices.txt

# 查看特定项目的失败情况
cat failure_analysis/failure_analysis.json | jq '.project_stats["gravitational/teleport"]'
```

---

## 🚀 下一步行动建议

### 1. 重跑失败的任务

```bash
# 方案 A：重跑所有失败任务（推荐）
python test_tmux_cc_experience.py --indices 9,13,19,21,26,31,38,39,42,47,49,54,58,62

# 方案 B：只重跑磁盘空间导致失败的任务
python test_tmux_cc_experience.py --indices 9,13,19,21,26,31,38,39,42,47,49,54

# 方案 C：按项目重跑
# gravitational/teleport
python test_tmux_cc_experience.py --indices 9,13,19,21,31,38,39,49

# protonmail/webclients
python test_tmux_cc_experience.py --indices 26,42,54
```

### 2. 继续运行剩余任务

```bash
# 从第50个任务继续
python test_tmux_cc_experience.py --start-index 50 --end-index 100 --validate
```

### 3. 深入分析特定失败

```bash
# 查看特定任务的完整日志
grep -A 50 "instance_gravitational__teleport-3fa6904377c006497169945428e" batch_0_50.log

# 统计每个错误类型的出现次数
grep -i "error\|failed" batch_0_50.log | sort | uniq -c | sort -rn
```

---

## 📈 监控建议

### 运行中监控

```bash
# 实时监控磁盘使用
watch -n 5 'df -h | grep -E "(Filesystem|/ssd1|/tmp)"'

# 实时监控 Docker 容器
watch -n 5 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Size}}"'

# 实时查看日志
tail -f batch_50_100.log | grep -E "处理完成|✗|⚠️"
```

### 定期清理

```bash
# 清理旧的临时文件
rm -rf /ssd1/Dejavu/tmp/swe_bench_*

# 清理 Docker 容器和 volumes
docker container prune -f
docker volume prune -f

# 清理 Claude sessions（可选，保留最近的）
cd ~/.claude/projects
ls -lt | tail -n +50 | awk '{print $9}' | xargs rm -rf
```

---

## 🔧 高级分析

### 生成可视化报告

如果想要更直观的可视化报告，可以：

```bash
# 导出为 CSV
cat failure_analysis/failure_analysis.json | jq -r '.project_stats | to_entries[] | [.key, .value.total, .value.success, .value.failed, .value.success_rate] | @csv' > project_stats.csv

# 在 Python 中分析
python3 << 'EOF'
import json
import pandas as pd
import matplotlib.pyplot as plt

with open('failure_analysis/failure_analysis.json') as f:
    data = json.load(f)

# 转换为 DataFrame
df = pd.DataFrame.from_dict(data['project_stats'], orient='index')
df = df.sort_values('failed', ascending=False)

# 绘制图表
df[['success', 'failed']].plot(kind='bar', stacked=True, figsize=(12, 6))
plt.title('SWE-bench 项目成功/失败分布')
plt.xlabel('项目')
plt.ylabel('任务数')
plt.tight_layout()
plt.savefig('failure_analysis/project_stats.png')
print("✓ 图表已保存: failure_analysis/project_stats.png")
EOF
```

---

## 💡 常见问题

### Q: 为什么 gravitational/teleport 全部失败？
**A:** 主要是磁盘空间不足。这个项目的代码库很大（Go 项目通常依赖多），解压后占用空间较多。修复磁盘问题后应该可以成功。

### Q: 如何提高成功率？
**A:** 
1. ✅ 确保 `/ssd1/Dejavu/tmp` 有足够空间（已修复）
2. 增加超时时间（如果任务经常超时）
3. 优化 prompt（针对未生成 patch 的情况）
4. 及时清理临时文件和容器

### Q: 哪些项目最容易成功？
**A:** 从数据看：
- NodeBB (JavaScript) - 100%
- qutebrowser (Python) - 100%
- ansible (Python) - 100%
- navidrome (Go) - 100%

这些项目可能代码结构清晰、测试覆盖好，或者问题描述比较准确。

### Q: 如何快速定位某个任务失败的具体原因？
**A:** 
```bash
# 方法1：使用分析工具
cat failure_analysis/failure_analysis.json | jq '.failure_categories.disk_space[] | select(.index == 9)'

# 方法2：直接查看日志
grep -A 100 "\[9/100\]" batch_0_50.log | grep -E "✗|Error|失败"
```

---

## 📝 报告文件说明

生成的报告文件包含：

- **failure_analysis.json**: 完整的 JSON 格式分析报告
  - `summary`: 总体统计
  - `failure_categories`: 按失败原因分类
  - `project_stats`: 项目维度统计

- **failed_task_indices.txt**: 失败任务的索引列表（逗号分隔）
  - 可直接用于 `--indices` 参数

---

## 🎯 总结

**当前状态：**
- ✅ 78% 的任务成功完成
- ❌ 主要失败原因是磁盘空间（已修复）
- ⚠️ 少数任务未生成 patch（需进一步调查）

**推荐行动：**
1. 立即重跑失败的14个任务
2. 继续运行任务 50-100
3. 监控磁盘使用和容器数量
4. 分析未生成 patch 的2个任务

祝评估顺利！🚀
