# 批量处理任务指南

## 任务选择参数

脚本支持三种方式选择要处理的任务：

### 方式 1: 单个任务 (`--index`)

```bash
# 处理索引为 5 的任务
python test_tmux_cc_experience.py --index 5
```

**适用场景：**
- 测试脚本
- 调试特定任务
- 重新运行失败的任务

---

### 方式 2: 前 N 个任务 (`--max-tasks`)

```bash
# 处理前 10 个任务（索引 0-9）
python test_tmux_cc_experience.py --max-tasks 10
```

**适用场景：**
- 快速测试脚本功能
- 小规模评测
- 从头开始运行

**限制：**
- ❌ 总是从索引 0 开始
- ❌ 不能跳过已完成的任务
- ❌ 不适合分批次运行

---

### 方式 3: 指定范围 (`--start-index` + `--end-index`) ⭐ 推荐

```bash
# 处理索引 50-100 的任务（不包含 100）
python test_tmux_cc_experience.py --start-index 50 --end-index 100
```

**适用场景：**
- ✅ 分批次运行大量任务
- ✅ 跳过已完成的任务
- ✅ 并行运行（不同机器处理不同范围）
- ✅ 断点续传（从上次停止的地方继续）

**优势：**
- 灵活指定任意范围
- 避免重复运行
- 便于进度管理

---

## 分批次处理策略

### 场景：处理 500 个任务

#### 策略 1: 按固定大小分批（推荐）

```bash
# 每批 50 个任务
python test_tmux_cc_experience.py --start-index 0 --end-index 50 --no-validate
python test_tmux_cc_experience.py --start-index 50 --end-index 100 --no-validate
python test_tmux_cc_experience.py --start-index 100 --end-index 150 --no-validate
python test_tmux_cc_experience.py --start-index 150 --end-index 200 --no-validate
...
```

**优点：**
- 进度可预测
- 便于管理和追踪
- 失败后容易定位

#### 策略 2: 按百分比分批

```bash
# 前 25% (0-125)
python test_tmux_cc_experience.py --start-index 0 --end-index 125 --no-validate

# 26-50% (125-250)
python test_tmux_cc_experience.py --start-index 125 --end-index 250 --no-validate

# 51-75% (250-375)
python test_tmux_cc_experience.py --start-index 250 --end-index 375 --no-validate

# 76-100% (375-500)
python test_tmux_cc_experience.py --start-index 375 --end-index 500 --no-validate
```

**优点：**
- 进度清晰（25%, 50%, 75%, 100%）
- 批次数量少

---

## 实战示例

### 示例 1: 测试 + 批量运行

```bash
# Step 1: 先测试单个任务
python test_tmux_cc_experience.py --index 0 --use-tmux --no-validate

# Step 2: 确认无误后，批量运行第一批
nohup python test_tmux_cc_experience.py --start-index 0 --end-index 50 --no-validate > batch1.log 2>&1 &

# Step 3: 第一批完成后，运行第二批
nohup python test_tmux_cc_experience.py --start-index 50 --end-index 100 --no-validate > batch2.log 2>&1 &
```

---

### 示例 2: 并行处理（多机器/多进程）

**机器 A：**
```bash
python test_tmux_cc_experience.py --start-index 0 --end-index 250 --no-validate
```

**机器 B：**
```bash
python test_tmux_cc_experience.py --start-index 250 --end-index 500 --no-validate
```

**优点：**
- 充分利用资源
- 加快处理速度

**注意：**
- 确保不同范围不重叠
- 最后需要合并结果

---

### 示例 3: 断点续传

```bash
# 第一次运行: 处理 0-100
python test_tmux_cc_experience.py --start-index 0 --end-index 100 --no-validate

# 运行到 60 时崩溃了...

# 检查已完成的任务
ls ./swe_bench_output_ducc/tasks/ | wc -l
# 假设显示: 60

# 从第 60 个继续运行
python test_tmux_cc_experience.py --start-index 60 --end-index 100 --no-validate
```

**快速查找已完成任务数：**
```bash
# 统计已完成任务
completed=$(ls -1 ./swe_bench_output_ducc/tasks/ 2>/dev/null | wc -l)
echo "已完成: $completed 个任务"

# 从下一个任务继续
python test_tmux_cc_experience.py --start-index $completed --end-index 500 --no-validate
```

---

### 示例 4: 自动化批处理脚本

创建一个 shell 脚本 `batch_run.sh`：

```bash
#!/bin/bash

# 配置
TOTAL_TASKS=500
BATCH_SIZE=50
OUTPUT_DIR="./swe_bench_output_ducc"

# 计算批次数
NUM_BATCHES=$(( ($TOTAL_TASKS + $BATCH_SIZE - 1) / $BATCH_SIZE ))

echo "总任务数: $TOTAL_TASKS"
echo "批次大小: $BATCH_SIZE"
echo "总批次数: $NUM_BATCHES"
echo ""

for ((batch=0; batch<$NUM_BATCHES; batch++)); do
    start=$(( $batch * $BATCH_SIZE ))
    end=$(( ($batch + 1) * $BATCH_SIZE ))
    
    # 最后一批可能不满
    if [ $end -gt $TOTAL_TASKS ]; then
        end=$TOTAL_TASKS
    fi
    
    echo "======================================"
    echo "批次 $(($batch + 1))/$NUM_BATCHES: [$start, $end)"
    echo "======================================"
    
    # 运行
    python test_tmux_cc_experience.py \
        --start-index $start \
        --end-index $end \
        --no-validate \
        --timeout 1800
    
    # 检查返回值
    if [ $? -ne 0 ]; then
        echo "批次 $(($batch + 1)) 失败！"
        exit 1
    fi
    
    # 统计进度
    completed=$(ls -1 $OUTPUT_DIR/tasks/ 2>/dev/null | wc -l)
    progress=$(( $completed * 100 / $TOTAL_TASKS ))
    echo "进度: $completed/$TOTAL_TASKS ($progress%)"
    echo ""
done

echo "全部完成！"
```

**使用：**
```bash
chmod +x batch_run.sh
./batch_run.sh
```

---

## 进度监控

### 实时监控脚本

```bash
#!/bin/bash
# monitor.sh - 监控批处理进度

OUTPUT_DIR="./swe_bench_output_ducc"
TOTAL_TASKS=500

while true; do
    clear
    echo "========================================"
    echo "批处理进度监控"
    echo "========================================"
    
    # 统计完成任务
    completed=$(ls -1 $OUTPUT_DIR/tasks/ 2>/dev/null | wc -l)
    progress=$(( $completed * 100 / $TOTAL_TASKS ))
    
    echo "已完成: $completed / $TOTAL_TASKS ($progress%)"
    echo ""
    
    # 统计成功/失败
    if [ -f "$OUTPUT_DIR/report.json" ]; then
        echo "报告:"
        cat $OUTPUT_DIR/report.json | jq -r '
            "  总数: \(.total_instances)",
            "  成功: \(.resolved_instances)",
            "  成功率: \(.resolve_rate * 100)%"
        '
    fi
    
    echo ""
    echo "最近完成的任务:"
    ls -lt $OUTPUT_DIR/tasks/ | head -6 | tail -5
    
    echo ""
    echo "按 Ctrl+C 退出"
    
    sleep 5
done
```

**使用：**
```bash
chmod +x monitor.sh
./monitor.sh
```

---

## 常见问题

### Q1: 如何知道数据集有多少个任务？

```bash
# 运行脚本查看数据集大小（会自动显示）
python test_tmux_cc_experience.py --index 0 --no-validate

# 输出会显示:
# ✓ 加载数据集成功: 500 个任务
```

### Q2: 如何跳过已完成的任务？

```bash
# 方法 1: 手动指定起始索引
completed=$(ls -1 ./swe_bench_output_ducc/tasks/ | wc -l)
python test_tmux_cc_experience.py --start-index $completed --end-index 500

# 方法 2: 删除输出目录重新开始
rm -rf ./swe_bench_output_ducc
python test_tmux_cc_experience.py --start-index 0 --end-index 500
```

### Q3: end-index 超过数据集大小会怎样？

脚本会自动调整：
```bash
# 数据集只有 500 个任务
python test_tmux_cc_experience.py --start-index 400 --end-index 600

# 输出：
# ⚠️ --end-index (600) 超过数据集大小 (500)，将调整为 500
# 处理任务范围: [400, 500) (共 100 个任务)
```

### Q4: 能否同时使用 --max-tasks 和 --start-index？

不能，会报错：
```bash
python test_tmux_cc_experience.py --max-tasks 10 --start-index 50 --end-index 60

# 错误:
# error: --max-tasks 不能与 --start-index, --end-index 同时使用
```

---

## 最佳实践

### ✅ 推荐做法

1. **先小批量测试**
   ```bash
   python test_tmux_cc_experience.py --start-index 0 --end-index 5 --no-validate
   ```

2. **使用固定批次大小**
   ```bash
   # 每批 50 个，便于管理
   --start-index 0 --end-index 50
   --start-index 50 --end-index 100
   ...
   ```

3. **使用 nohup 后台运行**
   ```bash
   nohup python test_tmux_cc_experience.py --start-index 0 --end-index 100 > batch.log 2>&1 &
   ```

4. **定期检查进度**
   ```bash
   # 查看已完成任务数
   ls -1 ./swe_bench_output_ducc/tasks/ | wc -l
   
   # 查看最新日志
   tail -f batch.log
   ```

5. **保留日志和结果**
   ```bash
   # 每批保存日志
   python ... > batch_0_50.log 2>&1
   python ... > batch_50_100.log 2>&1
   ```

### ❌ 避免的做法

1. **不要用 --max-tasks 处理大量任务**
   ```bash
   # ❌ 不好：总是从 0 开始
   python test_tmux_cc_experience.py --max-tasks 500
   
   # ✅ 好：使用范围，便于分批
   python test_tmux_cc_experience.py --start-index 0 --end-index 500
   ```

2. **不要在没有测试的情况下运行大批量**
   ```bash
   # ❌ 不好：直接运行全部
   python test_tmux_cc_experience.py --start-index 0 --end-index 500
   
   # ✅ 好：先测试小批量
   python test_tmux_cc_experience.py --start-index 0 --end-index 5
   # 确认无误后再运行全部
   ```

3. **不要忽略日志**
   ```bash
   # ❌ 不好：没有日志
   python test_tmux_cc_experience.py --start-index 0 --end-index 100
   
   # ✅ 好：保存日志
   python test_tmux_cc_experience.py --start-index 0 --end-index 100 > batch.log 2>&1
   ```

---

## 总结

**关键参数：**
- `--index <N>`: 单个任务
- `--max-tasks <N>`: 前 N 个任务（从 0 开始）
- `--start-index <N> --end-index <M>`: 任务范围 [N, M)

**推荐用法：**
```bash
# 分批处理 500 个任务，每批 50 个
for start in 0 50 100 150 200 250 300 350 400 450; do
    end=$((start + 50))
    python test_tmux_cc_experience.py --start-index $start --end-index $end --no-validate
done
```

**核心优势：**
- ✅ 灵活的任务范围选择
- ✅ 支持断点续传
- ✅ 便于并行处理
- ✅ 避免重复运行

现在你可以高效地分批次处理大量任务了！🚀




# 第一批：0-49（共50个）
nohup python test_tmux_cc_experience.py --start-index 0 --end-index 50 --no-validate > batch_0_50.log 2>&1 &

# 第二批：50-99（共50个）
nohup python test_tmux_cc_experience.py --start-index 50 --end-index 100 --no-validate > batch_50_100.log 2>&1 &

# 第三批：100-149（共50个）
nohup python test_tmux_cc_experience.py --start-index 100 --end-index 150 --no-validate > batch_100_150.log 2>&1 &