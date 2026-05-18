#!/bin/bash

# ========== 配置区域 ==========
# Python 命令配置 - 优先使用环境变量，然后尝试 conda 环境，最后使用系统 Python
if [ -n "$PYTHON_CMD" ]; then
  # 使用环境变量指定的 Python
  :
elif [ -x "$HOME/miniconda3/envs/dejavu/bin/python3" ]; then
  # 使用 dejavu conda 环境
  PYTHON_CMD="$HOME/miniconda3/envs/dejavu/bin/python3"
else
  # 使用系统 Python
  PYTHON_CMD="$(which python3 2>/dev/null || which python 2>/dev/null || echo python3)"
fi

# 验证 Python 是否可用
if ! command -v "$PYTHON_CMD" &> /dev/null; then
  echo "❌ 错误: 找不到 Python 解释器"
  echo "请设置 PYTHON_CMD 环境变量: export PYTHON_CMD=/path/to/python3"
  exit 1
fi

# 模型名称配置（用于日志和结果目录命名）
MODEL_NAME="claude"

# Instance ID 列表文件路径
IDS_FILE="./ids.txt"

# 模型映射配置 - 将简短名称映射到完整模型名
# 键: 简短名称（用于目录命名）
# 值: 完整模型名称（传递给 ducc）
declare -A MODEL_CONFIGS=(
    ["claude"]="Claude Opus 4.6"
    ["opus"]="Claude Opus 4.6"
    ["sonnet"]="Claude Sonnet 4"
    ["sonnet4"]="Claude Sonnet 4"
    ["gpt4"]="GPT-4"
    ["minimax"]="MiniMax"
)

# ==============================

# 获取脚本的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"

# 并发数量（默认1，即顺序执行）
PARALLEL_JOBS=1
DAEMON_MODE=""
# 是否启用实时评估
ENABLE_EVAL=false
# Docker Hub 用户名（用于评估）
DOCKERHUB_USERNAME="jefzda"
# 数据集路径 (parquet 或 CSV)
DATASET_PATH="/ssd1/Dejavu/datasets/SWE-bench_Pro/test-python.parquet"
# Scripts 目录
SCRIPTS_DIR="./SWE-bench_Pro-os/run_scripts"

# 解析参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --ids-file)
      IDS_FILE="$2"
      shift 2
      ;;
    --model)
      MODEL_NAME="$2"
      shift 2
      ;;
    --parallel)
      PARALLEL_JOBS="$2"
      shift 2
      ;;
    --enable-eval)
      ENABLE_EVAL=true
      shift
      ;;
    --dockerhub-username)
      DOCKERHUB_USERNAME="$2"
      shift 2
      ;;
    --dataset-path)
      DATASET_PATH="$2"
      shift 2
      ;;
    --scripts-dir)
      SCRIPTS_DIR="$2"
      shift 2
      ;;
    --daemon)
      DAEMON_MODE=true
      shift
      ;;
    *)
      echo "未知参数: $1"
      echo "用法: $0 [--ids-file <文件路径>] [--model <模型名>] [--parallel <并发数>] [--enable-eval]"
      exit 1
      ;;
  esac
done

# 检查 IDs 文件是否存在
if [ ! -f "$IDS_FILE" ]; then
  echo "❌ 错误: Instance IDs 文件不存在: $IDS_FILE"
  echo ""
  echo "用法: $0 --ids-file <文件路径> [--model <模型名>] [--parallel <并发数>]"
  echo ""
  echo "参数说明:"
  echo "  --ids-file            Instance ID 列表文件路径 (每行一个 instance_id)"
  echo "  --model               模型名称 (默认: claude)"
  echo "                        支持简短名称: claude, opus, sonnet, sonnet4, gpt4, minimax"
  echo "                        或完整模型名（需要用引号）: \"Claude Opus 4.6\", \"Claude Sonnet 4\""
  echo "  --parallel            并发数量 (默认: 1)"
  echo "  --enable-eval         启用实时评估（每个任务完成后立即评估）"
  echo "  --dockerhub-username  Docker Hub 用户名 (默认: jefzda)"
  echo "  --dataset-path        数据集文件路径 (parquet/CSV)"
  echo "                        (默认: /ssd1/Dejavu/datasets/SWE-bench_Pro/test-python.parquet)"
  echo "  --scripts-dir         Scripts 目录路径 (默认: ./SWE-bench_Pro-os/run_scripts)"
  echo ""
  echo "示例:"
  echo "  # 不带评估"
  echo "  $0 --ids-file ./ids.txt --model claude --parallel 3"
  echo ""
  echo "  # 带实时评估"
  echo "  $0 --ids-file ./ids.txt --model claude --parallel 3 --enable-eval"
  echo ""
  echo "  # 自定义评估参数"
  echo "  $0 --ids-file ./ids.txt --model \"Claude Sonnet 4.6\" --parallel 5 \\"
  echo "     --enable-eval --dockerhub-username myuser --dataset-path ./data.parquet"
  exit 1
fi

# 如果不是后台模式，重新以后台模式启动自己
if [ -z "$DAEMON_MODE" ]; then
  echo "以后台模式启动..."
  mkdir -p ./evaluation/logs
  
  log_file="./evaluation/logs/run_batch_ids_master_${MODEL_NAME}.log"
  
  # 构建参数数组（正确处理带空格的参数）
  args=(--daemon --ids-file "$IDS_FILE" --model "$MODEL_NAME")
  if [ "$PARALLEL_JOBS" -gt 1 ]; then
    args+=(--parallel "$PARALLEL_JOBS")
  fi
  if [ "$ENABLE_EVAL" = true ]; then
    args+=(--enable-eval --dockerhub-username "$DOCKERHUB_USERNAME" --dataset-path "$DATASET_PATH" --scripts-dir "$SCRIPTS_DIR")
  fi
  
  nohup bash "$SCRIPT_PATH" "${args[@]}" > "$log_file" 2>&1 &
  
  master_pid=$!
  echo "✓ 主进程 PID: $master_pid"
  echo "✓ 主日志: $log_file"
  echo "✓ IDs 文件: $IDS_FILE"
  echo "✓ 模型: $MODEL_NAME"
  
  if [ "$PARALLEL_JOBS" -gt 1 ]; then
    echo ""
    echo "⚡ 并发模式: 同时运行 $PARALLEL_JOBS 个任务"
  fi
  
  echo ""
  echo "监控命令:"
  echo "  # 查看主日志"
  echo "  tail -f $log_file"
  echo ""
  echo "  # 查看具体任务日志"
  echo "  tail -f ./evaluation/logs/${MODEL_NAME}_ids_*.log"
  echo ""
  echo "  # 停止所有"
  echo "  kill $master_pid"
  echo "  # 或强制停止所有子进程"
  echo "  pkill -P $master_pid"
  exit 0
fi

# 以下是实际执行逻辑（后台模式）
# 切换到脚本所在目录
cd "$SCRIPT_DIR"

# 创建必要的目录
mkdir -p ./evaluation/logs
mkdir -p ./evaluation/batch

# 读取 Instance IDs
echo "========================================" 
echo "启动 ${MODEL_NAME} ID列表批量评测"
echo "========================================"
echo "IDs 文件: $IDS_FILE"

# 解析模型配置
# 如果 MODEL_NAME 在映射表中，使用映射的完整名称
# 否则直接使用 MODEL_NAME（可能是用户传入的完整名称）
if [ -n "${MODEL_CONFIGS[$MODEL_NAME]}" ]; then
  ANTHROPIC_MODEL="${MODEL_CONFIGS[$MODEL_NAME]}"
  echo "模型: $MODEL_NAME -> \"$ANTHROPIC_MODEL\""
else
  ANTHROPIC_MODEL="$MODEL_NAME"
  echo "模型: \"$ANTHROPIC_MODEL\" (直接使用)"
fi

# 统计总数（排除空行和注释行）
total_ids=$(grep -v '^#' "$IDS_FILE" | grep -v '^$' | wc -l | tr -d ' ')
echo "总任务数: $total_ids"

if [ "$PARALLEL_JOBS" -gt 1 ]; then
  echo "⚡ 并发执行模式: 同时运行 $PARALLEL_JOBS 个任务"
else
  echo "📋 顺序执行模式"
fi

echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# 读取所有 instance_id 到数组（排除注释和空行）
mapfile -t instance_ids < <(grep -v '^#' "$IDS_FILE" | grep -v '^$')

# 输出目录
output_dir="./evaluation/batch/${MODEL_NAME}_swe_bench_output_ids"
mkdir -p "$output_dir"

if [ "$PARALLEL_JOBS" -le 1 ]; then
  # ===== 顺序执行模式 =====
  current_task=1
  
  for instance_id in "${instance_ids[@]}"; do
    # 去除前后空格
    instance_id=$(echo "$instance_id" | xargs)
    
    log_file="./evaluation/logs/${MODEL_NAME}_ids_${current_task}.log"
    
    echo "========================================"
    echo "任务 $current_task/$total_ids"
    echo "Instance ID: $instance_id"
    echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================"
    
    # 检查是否已经成功
    prediction_file="$output_dir/predictions/${instance_id}.json"
    if [ -f "$prediction_file" ]; then
      echo "  ⏭️  跳过（已完成）: $instance_id"
      echo ""
      current_task=$((current_task + 1))
      continue
    fi
    
    # 启动当前任务（后台运行）
    nohup "$PYTHON_CMD" -u test_tmux_cc_experience.py \
      --instance-id "$instance_id" \
      --output-dir "$output_dir" \
      --anthropic-model "$ANTHROPIC_MODEL" \
      --no-validate --in-container \
      > "$log_file" 2>&1 &
    
    current_pid=$!
    echo "  ✓ PID: $current_pid"
    echo "  ✓ 日志: $log_file"
    echo ""
    
    # 等待当前任务完成
    echo "  等待任务完成..."
    echo "  提示: 可在另一个终端查看实时日志: tail -f $log_file"
    echo ""
    
    wait $current_pid
    exit_code=$?
    
    # 检查执行结果
    if [ $exit_code -eq 0 ]; then
      echo "  ✓ 任务执行成功: $instance_id"
    else
      echo "  ✗ 任务执行失败: $instance_id (退出码: $exit_code)"
      echo "  ⚠️  继续执行下一个任务..."
    fi
    
    # 实时评估（如果启用）
    if [ "$ENABLE_EVAL" = true ] && [ -f "$prediction_file" ]; then
      echo "  🔍 开始评估..."
      eval_log_file="./evaluation/logs/${MODEL_NAME}_eval_${current_task}.log"
      
      # 确定任务目录（用于保存评估日志）
      task_dir="$output_dir/tasks/${instance_id}"
      
        "$PYTHON_CMD" evaluate_single_instance.py \
            --instance-id "$instance_id" \
            --prediction-file "$prediction_file" \
            --dataset-path "$DATASET_PATH" \
        --scripts-dir "$SCRIPTS_DIR" \
        --output-dir "$output_dir/../eval_results" \
        --dockerhub-username "$DOCKERHUB_USERNAME" \
        --use-local-docker \
        --prefix "${MODEL_NAME}" \
        --task-dir "$task_dir" \
        > "$eval_log_file" 2>&1
      
      eval_exit_code=$?
      if [ $eval_exit_code -eq 0 ]; then
        echo "  ✓ 评估完成: RESOLVED"
      else
        echo "  ✗ 评估完成: FAILED"
      fi
    fi
    
    echo "  完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    # 任务间短暂休息
    if [ $current_task -lt $total_ids ]; then
      sleep 5
    fi
    
    current_task=$((current_task + 1))
  done

else
  # ===== 并行执行模式 =====
  echo "🚀 开始并行执行..."
  echo ""
  
  running_pids=()
  running_ids=()
  task_index=0
  completed_count=0
  
  # 启动任务的函数
  start_task() {
    local instance_id=$1
    local index=$2
    
    log_file="./evaluation/logs/${MODEL_NAME}_ids_${index}.log"
    
    # 检查是否已经成功
    prediction_file="$output_dir/predictions/${instance_id}.json"
    if [ -f "$prediction_file" ]; then
      echo "[$(date '+%H:%M:%S')] ⏭️  跳过 $index/$total_ids: $instance_id (已完成)"
      return 1
    fi
    
    echo "[$(date '+%H:%M:%S')] 启动任务 $index/$total_ids: $instance_id"
    
    nohup "$PYTHON_CMD" -u test_tmux_cc_experience.py \
      --instance-id "$instance_id" \
      --output-dir "$output_dir" \
      --anthropic-model "$ANTHROPIC_MODEL" \
      --no-validate --in-container \
      > "$log_file" 2>&1 &
    
    local pid=$!
    echo "  ✓ PID: $pid | 日志: $log_file"
    
    running_pids+=($pid)
    running_ids+=("$instance_id")
    return 0
  }
  
  # 等待一个任务完成的函数
  wait_for_any() {
    while true; do
      for i in "${!running_pids[@]}"; do
        if ! kill -0 ${running_pids[$i]} 2>/dev/null; then
          local instance_id="${running_ids[$i]}"
          wait ${running_pids[$i]} 2>/dev/null
          local exit_code=$?
          
          ((completed_count++))
          echo ""
          echo "[$(date '+%H:%M:%S')] ✓ 任务完成: $instance_id (退出码: $exit_code) [$completed_count/$total_ids]"
          
          # 检查是否成功生成 prediction
          prediction_file="$output_dir/predictions/${instance_id}.json"
          if [ -f "$prediction_file" ]; then
            echo "  ✓ Prediction 已生成"
            
            # 实时评估（如果启用）
            if [ "$ENABLE_EVAL" = true ]; then
              echo "  🔍 开始评估..."
              eval_log_file="./evaluation/logs/${MODEL_NAME}_eval_${instance_id##*_}.log"
              
              # 确定任务目录（用于保存评估日志）
              task_dir="$output_dir/tasks/${instance_id}"
              
              "$PYTHON_CMD" evaluate_single_instance.py \
                --instance-id "$instance_id" \
                --prediction-file "$prediction_file" \
                --dataset-path "$DATASET_PATH" \
                --scripts-dir "$SCRIPTS_DIR" \
                --output-dir "$output_dir/../eval_results" \
                --dockerhub-username "$DOCKERHUB_USERNAME" \
                --use-local-docker \
                --prefix "${MODEL_NAME}" \
                --task-dir "$task_dir" \
                > "$eval_log_file" 2>&1 &
              
              # 不等待评估完成，让它在后台运行
              echo "  ⏳ 评估在后台运行 (PID: $!)"
            fi
          else
            echo "  ✗ Prediction 未生成"
          fi
          
          unset running_pids[$i]
          unset running_ids[$i]
          
          # 重建数组索引
          running_pids=("${running_pids[@]}")
          running_ids=("${running_ids[@]}")
          return 0
        fi
      done
      sleep 1
    done
  }
  
  # 分发任务到并行执行
  for instance_id in "${instance_ids[@]}"; do
    # 去除前后空格
    instance_id=$(echo "$instance_id" | xargs)
    ((task_index++))
    
    # 如果已达到并行上限，等待一个任务完成
    while [ ${#running_pids[@]} -ge $PARALLEL_JOBS ]; do
      wait_for_any
    done
    
    # 启动新任务
    start_task "$instance_id" "$task_index"
    
    # 任务间短暂间隔，避免同时启动造成资源抢占
    sleep 2
  done
  
  # 等待所有剩余任务完成
  echo ""
  echo "等待所有剩余任务完成..."
  while [ ${#running_pids[@]} -gt 0 ]; do
    wait_for_any
  done
  
  echo ""
  echo "[$(date '+%H:%M:%S')] ✓ 所有任务执行完毕"
fi

echo ""
echo "========================================"
echo "所有任务执行完成"
echo "结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# 汇总统计
echo "=========================================="
echo "总体统计:"
echo "=========================================="

total_success=0
total_failed=0
failed_ids=()

for instance_id in "${instance_ids[@]}"; do
  instance_id=$(echo "$instance_id" | xargs)
  
  # 检查 prediction 文件
  prediction_file="$output_dir/predictions/${instance_id}.json"
  if [ -f "$prediction_file" ]; then
    total_success=$((total_success + 1))
  else
    total_failed=$((total_failed + 1))
    failed_ids+=("$instance_id")
  fi
done

echo "  总任务数: $total_ids"
echo "  成功完成: $total_success"
echo "  失败需重试: $total_failed"

if [ $total_ids -gt 0 ]; then
  success_rate=$(awk "BEGIN {printf \"%.1f\", ($total_success / $total_ids) * 100}")
  echo "  总成功率: ${success_rate}%"
fi

echo ""

# 保存失败的 IDs
if [ $total_failed -gt 0 ]; then
  failed_file="./evaluation/logs/${MODEL_NAME}_failed_ids.txt"
  printf "%s\n" "${failed_ids[@]}" > "$failed_file"
  echo "失败任务列表已保存到: $failed_file"
  echo ""
  echo "💡 提示: 可以重新运行失败的任务："
  echo "  bash $0 --ids-file $failed_file --model $MODEL_NAME --parallel $PARALLEL_JOBS"
else
  echo "✅ 所有任务都已成功完成！🎉"
fi

echo ""
echo "日志目录: ./evaluation/logs/"
echo "结果目录: $output_dir"

# 如果启用了评估，生成评估汇总
if [ "$ENABLE_EVAL" = true ]; then
  echo ""
  echo "========================================"
  echo "生成评估汇总报告..."
  echo "========================================"

  eval_results_dir="$output_dir/../eval_results"
  eval_summary_file="$output_dir/../eval_summary_${MODEL_NAME}.json"

  # 等待所有后台评估完成
  echo "等待所有评估任务完成..."
  wait

  # 生成汇总报告
  "$PYTHON_CMD" summarize_eval_results.py \
    --eval-results-dir "$eval_results_dir" \
    --output-file "$eval_summary_file" \
    --detailed-output "$output_dir/../eval_detailed_${MODEL_NAME}.json"

  echo ""
  echo "评估报告已保存:"
  echo "  摘要: $eval_summary_file"
  echo "  详细: $output_dir/../eval_detailed_${MODEL_NAME}.json"

  # 生成整体进度统计
  echo ""
  echo "========================================"
  echo "生成整体进度统计..."
  echo "========================================"

  eval_total_tasks=$total_ids
  eval_completed=0
  eval_resolved=0
  eval_failed=0
  eval_not_evaluated=0

  for instance_id in "${instance_ids[@]}"; do
    instance_id=$(echo "$instance_id" | xargs)
    task_eval_result="$output_dir/tasks/${instance_id}/evaluation/result.json"

    if [ -f "$task_eval_result" ]; then
      eval_completed=$((eval_completed + 1))
      # 检查是否 resolved
      is_resolved=$(python3 -c "import json; d=json.load(open('$task_eval_result')); print(d.get('resolved', False) or d.get('overall', False))" 2>/dev/null)
      if [ "$is_resolved" = "True" ]; then
        eval_resolved=$((eval_resolved + 1))
      else
        eval_failed=$((eval_failed + 1))
      fi
    else
      eval_not_evaluated=$((eval_not_evaluated + 1))
    fi
  done

  eval_remaining=$((eval_total_tasks - eval_completed))

  echo "  总任务数:     $eval_total_tasks"
  echo "  已评估:       $eval_completed"
  echo "  ✓ 解决:       $eval_resolved"
  echo "  ✗ 失败:       $eval_failed"
  echo "  ⏳ 未评估/剩余: $eval_remaining"
  if [ $eval_completed -gt 0 ]; then
    eval_resolve_rate=$(awk "BEGIN {printf \"%.1f\", ($eval_resolved / $eval_completed) * 100}")
    echo "  解决率:       ${eval_resolve_rate}% ($eval_resolved/$eval_completed)"
  fi
  echo ""

  # 保存进度统计到 JSON 文件
  progress_file="$output_dir/eval_progress.json"
  cat > "$progress_file" << EOJSON
{
  "model": "${MODEL_NAME}",
  "total_tasks": ${eval_total_tasks},
  "evaluated": ${eval_completed},
  "resolved": ${eval_resolved},
  "failed": ${eval_failed},
  "remaining": ${eval_remaining},
  "resolve_rate": $(awk "BEGIN {printf \"%.4f\", ($eval_resolved / ($eval_completed > 0 ? $eval_completed : 1))}"),
  "timestamp": "$(date '+%Y-%m-%d %H:%M:%S')"
}
EOJSON
  echo "进度统计已保存: $progress_file"
fi
