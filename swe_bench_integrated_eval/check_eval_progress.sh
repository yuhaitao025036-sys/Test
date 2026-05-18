#!/bin/bash
#
# 检查评估进度 - 扫描 tasks/instance_id/evaluation/result.json 统计整体状况
#
# 用法:
#   bash check_eval_progress.sh [--output-dir <batch_output_dir>] [--ids-file <ids_file>]
#
# 示例:
#   bash check_eval_progress.sh
#   bash check_eval_progress.sh --output-dir "./evaluation/batch/Claude Sonnet 4.6_swe_bench_output_ids"
#   bash check_eval_progress.sh --ids-file ./ids/passed_instance_ids.txt

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

OUTPUT_DIR=""
IDS_FILE=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --ids-file) IDS_FILE="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

# 自动检测 output_dir
if [ -z "$OUTPUT_DIR" ]; then
  OUTPUT_DIR=$(ls -d ./evaluation/batch/*_swe_bench_output_ids 2>/dev/null | head -1)
  if [ -z "$OUTPUT_DIR" ]; then
    echo "❌ 未找到输出目录，请用 --output-dir 指定"
    exit 1
  fi
fi

echo "========================================"
echo "评估进度检查"
echo "========================================"
echo "输出目录: $OUTPUT_DIR"
echo "检查时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

tasks_dir="$OUTPUT_DIR/tasks"
predictions_dir="$OUTPUT_DIR/predictions"

if [ ! -d "$tasks_dir" ]; then
  echo "❌ 任务目录不存在: $tasks_dir"
  exit 1
fi

# 统计
total_tasks=0
has_prediction=0
has_evaluation=0
resolved=0
failed=0
errors=0
no_eval=0

resolved_ids=()
failed_ids=()
error_ids=()
no_eval_ids=()

# 如果指定了 ids-file，按文件统计
if [ -n "$IDS_FILE" ] && [ -f "$IDS_FILE" ]; then
  mapfile -t instance_ids < <(grep -v '^#' "$IDS_FILE" | grep -v '^$')
  echo "IDs 文件: $IDS_FILE"
else
  # 否则扫描 tasks 目录
  mapfile -t instance_ids < <(ls "$tasks_dir" 2>/dev/null)
fi

total_tasks=${#instance_ids[@]}
echo "总任务数: $total_tasks"
echo ""

for instance_id in "${instance_ids[@]}"; do
  instance_id=$(echo "$instance_id" | xargs)

  # 检查 prediction
  if [ -f "$predictions_dir/${instance_id}.json" ]; then
    has_prediction=$((has_prediction + 1))
  fi

  # 检查评估结果
  result_file="$tasks_dir/${instance_id}/evaluation/result.json"
  if [ -f "$result_file" ]; then
    has_evaluation=$((has_evaluation + 1))

    # 解析结果
    is_resolved=$(python3 -c "import json; d=json.load(open('$result_file')); print('resolved' if (d.get('resolved', False) or d.get('overall', False)) else ('error' if 'error' in d else 'failed'))" 2>/dev/null)

    case "$is_resolved" in
      resolved)
        resolved=$((resolved + 1))
        resolved_ids+=("$instance_id")
        ;;
      error)
        errors=$((errors + 1))
        error_ids+=("$instance_id")
        ;;
      failed)
        failed=$((failed + 1))
        failed_ids+=("$instance_id")
        ;;
    esac
  else
    no_eval=$((no_eval + 1))
    no_eval_ids+=("$instance_id")
  fi
done

remaining=$((total_tasks - has_evaluation))

echo "=========================================="
echo "整体统计"
echo "=========================================="
echo "  总任务数:       $total_tasks"
echo "  有 Prediction:  $has_prediction"
echo "  已评估:         $has_evaluation"
echo "  ├─ ✓ 解决:      $resolved"
echo "  ├─ ✗ 测试失败:  $failed"
echo "  └─ ⚠️  评估出错:  $errors"
echo "  ⏳ 未评估/剩余:  $remaining"
echo ""

if [ $has_evaluation -gt 0 ]; then
  resolve_rate=$(awk "BEGIN {printf \"%.1f\", ($resolved / $has_evaluation) * 100}")
  echo "  解决率: ${resolve_rate}% ($resolved/$has_evaluation)"
fi

if [ $total_tasks -gt 0 ]; then
  progress_rate=$(awk "BEGIN {printf \"%.1f\", ($has_evaluation / $total_tasks) * 100}")
  echo "  评估进度: ${progress_rate}% ($has_evaluation/$total_tasks)"
fi

echo ""

# 显示错误实例
if [ ${#error_ids[@]} -gt 0 ]; then
  echo "=========================================="
  echo "⚠️  评估出错的实例 (${#error_ids[@]}):"
  echo "=========================================="
  for eid in "${error_ids[@]:0:10}"; do
    err_msg=$(python3 -c "import json; d=json.load(open('$tasks_dir/$eid/evaluation/result.json')); print(d.get('error','unknown')[:80])" 2>/dev/null)
    echo "  $eid"
    echo "    -> $err_msg"
  done
  if [ ${#error_ids[@]} -gt 10 ]; then
    echo "  ... 还有 $((${#error_ids[@]} - 10)) 个"
  fi
  echo ""
fi

# 保存进度到 JSON
progress_file="$OUTPUT_DIR/eval_progress.json"
cat > "$progress_file" << EOJSON
{
  "output_dir": "$OUTPUT_DIR",
  "total_tasks": ${total_tasks},
  "has_prediction": ${has_prediction},
  "evaluated": ${has_evaluation},
  "resolved": ${resolved},
  "failed": ${failed},
  "errors": ${errors},
  "remaining": ${remaining},
  "resolve_rate": $(awk "BEGIN {printf \"%.4f\", ($resolved / ($has_evaluation > 0 ? $has_evaluation : 1))}"),
  "progress_rate": $(awk "BEGIN {printf \"%.4f\", ($has_evaluation / ($total_tasks > 0 ? $total_tasks : 1))}"),
  "timestamp": "$(date '+%Y-%m-%d %H:%M:%S')"
}
EOJSON
echo "进度统计已保存: $progress_file"
