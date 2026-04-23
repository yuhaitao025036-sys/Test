#!/bin/bash
# SWE-bench Pro 批量评测脚本 - 每次运行一个任务
# 用法: ./run_batch.sh [start_index] [end_index]

set -e

# 默认参数
START_INDEX=${1:-0}
END_INDEX=${2:-10}
OUTPUT_DIR="./swe_bench_output"
SCRIPT="test_llm_api.py"

# 确保输出目录存在
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "SWE-bench Pro 批量评测"
echo "=========================================="
echo "任务范围: $START_INDEX - $END_INDEX"
echo "输出目录: $OUTPUT_DIR"
echo "=========================================="

# 记录开始时间
START_TIME=$(date +%s)

# 循环执行每个任务
for i in $(seq $START_INDEX $END_INDEX); do
    echo ""
    echo "[$i] 开始评测任务索引 $i ..."
    
    # 运行单个任务（失败也继续）
    python3 "$SCRIPT" --index "$i" --output-dir "$OUTPUT_DIR" || {
        echo "[$i] 警告: 任务 $i 失败，继续下一个"
    }
    
    # 清理Docker资源（防止堆积）
    echo "[$i] 清理Docker资源..."
    docker ps -a --filter "status=exited" -q | xargs -r docker rm 2>/dev/null || true
    
    # 短暂等待
    sleep 2
done

# 计算耗时
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
HOURS=$((ELAPSED / 3600))
MINUTES=$(((ELAPSED % 3600) / 60))
SECONDS=$((ELAPSED % 60))

echo ""
echo "=========================================="
echo "批量评测完成"
echo "总耗时: ${HOURS}h ${MINUTES}m ${SECONDS}s"
echo "=========================================="

# 生成分析报告
echo ""
echo "生成分析报告..."
python3 "$SCRIPT" --analysis --output-dir "$OUTPUT_DIR"

echo ""
echo "全部完成！查看结果:"
echo "  - 完整结果: $OUTPUT_DIR/all_results.jsonl"
echo "  - 分析报告: $OUTPUT_DIR/analysis_report.txt"
echo "  - Predictions: $OUTPUT_DIR/predictions/"
