# 集成评估流程 - 快速开始

## 最简单的使用方式

### 1. 使用 ID 列表批量运行（推荐）

```bash
# 创建 ID 列表文件（或使用现有文件）
cat run_batch_ids.txt

# 运行并启用实时评估
bash run_batch_by_ids.sh \
  --ids-file ./run_batch_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 5 \
  --enable-eval
```

**特点**: 
- ⚡ 每个任务完成后立即评估
- 📊 实时查看成功率
- 🔄 自动跳过已完成任务

### 2. 使用批次模式运行

```bash
# 编辑 run_batch.sh 中的批次配置
# 然后运行

bash run_batch.sh \
  --model claude \
  --parallel 3 \
  --enable-eval
```

**特点**: 
- 📦 按批次顺序处理
- 💾 所有批次完成后统一评估
- 🎯 适合大规模任务

---

## 查看结果

### 实时监控进度

```bash
# 查看主日志
tail -f ./evaluation/logs/run_batch_ids_master_*.log

# 查看具体任务
tail -f ./evaluation/logs/claude_ids_*.log

# 查看评估日志
tail -f ./evaluation/logs/claude_eval_*.log
```

### 查看评估报告

```bash
# 查看摘要（JSON 格式）
cat ./evaluation/batch/eval_summary_claude.json

# 或使用 Python 美化输出
python3 -c "import json; print(json.dumps(json.load(open('./evaluation/batch/eval_summary_claude.json')), indent=2))"

# 使用汇总脚本查看详细报告
python summarize_eval_results.py \
  --eval-results-dir ./evaluation/batch/eval_results
```

---

## 输出说明

### 主要输出文件

```
./evaluation/batch/
├── eval_results/                      # 每个 instance 的评估结果
│   ├── instance_xxx_eval.json
│   └── ...
├── claude_eval_summary.json           # ⭐ 摘要报告（查看这个！）
└── claude_eval_detailed.json          # 详细结果（包含所有数据）
```

### 摘要报告关键字段

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

---

## 重试失败的任务

```bash
# 从摘要报告提取失败的 instances（手动或脚本）
# 假设保存到 failed_ids.txt

bash run_batch_by_ids.sh \
  --ids-file ./failed_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 3 \
  --enable-eval
```

---

## 不启用评估（只生成 predictions）

```bash
# 如果只想生成 predictions，不评估
bash run_batch_by_ids.sh \
  --ids-file ./run_batch_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 5
  # 不加 --enable-eval
```

---

## 常见问题

### Q: 评估很慢怎么办？
A: 评估需要运行 Docker 容器执行测试，速度取决于：
- Docker 容器性能
- 测试用例复杂度
- 并发数配置

建议: 
- 使用 `run_batch_by_ids.sh` 的实时评估模式，评估在后台进行不阻塞生成
- 降低 `--parallel` 参数避免资源竞争

### Q: 如何只查看评估结果不重新运行？
A: 使用汇总脚本:
```bash
python summarize_eval_results.py \
  --eval-results-dir ./evaluation/batch/eval_results
```

### Q: 评估出错了怎么办？
A: 查看评估日志:
```bash
tail -f ./evaluation/logs/claude_eval_*.log
```

常见错误:
- Docker 镜像不存在 → 检查 `--dockerhub-username`
- Instance 不在 CSV 中 → 检查 `--raw-sample-csv` 路径
- 权限问题 → 确保 Docker 正常运行

### Q: 中途中断了怎么恢复？
A: 直接重新运行相同命令，脚本会自动跳过已完成的任务:
```bash
# 直接重新运行
bash run_batch_by_ids.sh \
  --ids-file ./run_batch_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 5 \
  --enable-eval
```

---

## 完整示例

```bash
# 1. 准备 ID 列表
cat > my_test_ids.txt << EOF
instance_django__django-12345
instance_flask__flask-67890
instance_requests__requests-54321
EOF

# 2. 运行任务（生成 + 评估）
bash run_batch_by_ids.sh \
  --ids-file ./my_test_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 3 \
  --enable-eval

# 3. 等待完成，查看结果
cat ./evaluation/batch/eval_summary_claude.json

# 4. 如果有失败，提取失败 ID 并重试
# 手动创建 failed_ids.txt 或从 summary 提取
bash run_batch_by_ids.sh \
  --ids-file ./failed_ids.txt \
  --model "Claude Sonnet 4.6" \
  --parallel 3 \
  --enable-eval
```

---

## 更多信息

详细文档请参考: [INTEGRATED_EVAL_GUIDE.md](./INTEGRATED_EVAL_GUIDE.md)
