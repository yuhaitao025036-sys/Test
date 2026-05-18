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
MODEL_NAME="minimax_27"

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
    ["minimax_27"]="MiniMax"
)

# ==============================

# 获取脚本的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PATH="$SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"

# 检查是否是重试模式
RETRY_MODE=false
# 并发数量（默认1，即顺序执行）
PARALLEL_JOBS=1
# 是否启用评估
ENABLE_EVAL=false
# Docker Hub 用户名
DOCKERHUB_USERNAME="jefzda"
# 数据集路径 (parquet 或 CSV)
DATASET_PATH="/ssd1/Dejavu/datasets/SWE-bench_Pro/test-python.parquet"
# Scripts 目录
SCRIPTS_DIR="./SWE-bench_Pro-os/run_scripts"

# 解析参数
while [[ $# -gt 0 ]]; do
  case $1 in
    --retry-failed)
      RETRY_MODE=true
      shift
      ;;
    --parallel)
      PARALLEL_JOBS="$2"
      shift 2
      ;;
    --model)
      MODEL_NAME="$2"
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
      shift
      ;;
  esac
done

# 如果不是后台模式，重新以后台模式启动自己
if [ -z "$DAEMON_MODE" ]; then
  echo "以后台模式启动..."
  mkdir -p ./evaluation/logs
  
  # 构建启动命令和参数
  if [ "$RETRY_MODE" = true ]; then
    log_file="./evaluation/logs/run_batch_master_retry_${MODEL_NAME}.log"
  else
    log_file="./evaluation/logs/run_batch_master_${MODEL_NAME}.log"
  fi
  
  # 构建参数数组（正确处理带空格的参数）
  args=(--daemon)
  if [ "$RETRY_MODE" = true ]; then
    args+=(--retry-failed)
  fi
  if [ "$PARALLEL_JOBS" -gt 1 ]; then
    args+=(--parallel "$PARALLEL_JOBS")
  fi
  # 传递模型参数
  args+=(--model "$MODEL_NAME")
  # 传递评估参数
  if [ "$ENABLE_EVAL" = true ]; then
    args+=(--enable-eval --dockerhub-username "$DOCKERHUB_USERNAME" --dataset-path "$DATASET_PATH" --scripts-dir "$SCRIPTS_DIR")
  fi
  
  nohup bash "$SCRIPT_PATH" "${args[@]}" > "$log_file" 2>&1 &
  
  master_pid=$!
  echo "✓ 主进程 PID: $master_pid"
  echo "✓ 主日志: $log_file"
  
  if [ "$RETRY_MODE" = true ]; then
    echo ""
    echo "🔄 重试模式: 只处理失败的任务"
  fi
  
  if [ "$PARALLEL_JOBS" -gt 1 ]; then
    echo ""
    echo "⚡ 并发模式: 同时运行 $PARALLEL_JOBS 个批次"
  fi
  
  echo ""
  echo "监控命令:"
  echo "  # 查看主日志"
  echo "  tail -f $log_file"
  echo ""
  echo "  # 查看批次日志"
  echo "  tail -f ./evaluation/logs/${MODEL_NAME}_batch_120_130.log"
  echo ""
  echo "  # 停止所有"
  echo "  kill $master_pid"
  echo "  # 或强制停止所有子进程"
  echo "  pkill -P $master_pid"
  echo ""
  echo "使用示例:"
  echo "  # 更换模型重新运行"
  echo "  bash run_batch.sh --model claude --parallel 2"
  echo "  bash run_batch.sh --model \"Claude Sonnet 4\" --parallel 3"
  exit 0
fi

# 以下是实际执行逻辑（后台模式）
# 切换到脚本所在目录
cd "$SCRIPT_DIR"

# 创建必要的目录
mkdir -p ./evaluation/logs
mkdir -p ./evaluation/batch

# 批次配置（10个一批，更稳定）
batches=(
  # "50:60"
  # "60:70"
  # "70:80"
  # "80:90"
  # "90:100"
  # "100:110"
  # "110:120"
  "120:130"
  "130:140"
  "140:150"
  "150:160"
  "160:170"
  "170:180"
  "180:190"
  "190:200"
  "200:210"
  "210:220"
  "220:230"
  "230:240"
  "240:250"
  "250:260"
  "260:266"
)

# 解析模型配置
# 如果 MODEL_NAME 在映射表中，使用映射的完整名称
# 否则直接使用 MODEL_NAME（可能是用户传入的完整名称）
if [ -n "${MODEL_CONFIGS[$MODEL_NAME]}" ]; then
  ANTHROPIC_MODEL="${MODEL_CONFIGS[$MODEL_NAME]}"
else
  ANTHROPIC_MODEL="$MODEL_NAME"
fi

echo "========================================"
if [ "$RETRY_MODE" = true ]; then
  echo "启动 ${MODEL_NAME} 批量评测（重试模式）"
  echo "🔄 只处理失败的任务，跳过成功的任务"
else
  echo "启动 ${MODEL_NAME} 批量评测"
fi

# 显示模型信息
if [ "$ANTHROPIC_MODEL" != "$MODEL_NAME" ]; then
  echo "模型: $MODEL_NAME -> \"$ANTHROPIC_MODEL\""
else
  echo "模型: \"$ANTHROPIC_MODEL\""
fi

if [ "$PARALLEL_JOBS" -gt 1 ]; then
  echo "⚡ 并发执行模式: 同时运行 $PARALLEL_JOBS 个批次"
else
  echo "📋 顺序执行模式"
fi

echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# 顺序执行所有批次
total_batches=${#batches[@]}

if [ "$PARALLEL_JOBS" -le 1 ]; then
  # ===== 顺序执行模式（原有逻辑）=====
  current_batch=1
  
  for batch in "${batches[@]}"; do
    start=$(echo $batch | cut -d: -f1)
    end=$(echo $batch | cut -d: -f2)
  
    output_dir="./evaluation/batch/${MODEL_NAME}_swe_bench_output_batch_${start}_${end}"
    log_file="./evaluation/logs/${MODEL_NAME}_batch_${start}_${end}.log"
    
    echo "========================================"
    echo "批次 $current_batch/$total_batches: [$start, $end)"
    echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "========================================"
    
    # 启动当前批次（后台运行）
    nohup "$PYTHON_CMD" -u test_tmux_cc_experience.py \
      --start-index $start --end-index $end \
      --output-dir "$output_dir" \
      --anthropic-model "$ANTHROPIC_MODEL" \
      --no-validate --in-container \
      > "$log_file" 2>&1 &
    
    current_pid=$!
    echo "  ✓ PID: $current_pid"
    echo "  ✓ 输出: $output_dir"
    echo "  ✓ 日志: $log_file"
    echo ""
    
    # 等待当前批次完成
    echo "  等待批次 [$start, $end) 完成..."
    echo "  提示: 可在另一个终端查看实时日志: tail -f $log_file"
    echo ""
    
    wait $current_pid
    exit_code=$?
    
    # 检查执行结果
    if [ $exit_code -eq 0 ]; then
      echo "  ✓ 批次 [$start, $end) 执行成功"
    else
      echo "  ✗ 批次 [$start, $end) 执行失败 (退出码: $exit_code)"
      echo "  ⚠️  继续执行下一批次..."
    fi
    
    # 统计当前批次结果
    expected=$((end - start))
    
    # 统计成功的任务（有 prediction 文件）
    if [ -d "$output_dir/predictions/" ]; then
      success_count=$(ls -1 "$output_dir/predictions/" 2>/dev/null | wc -l)
    else
      success_count=0
    fi
  
  # 统计失败的任务（有 _full.json 且包含 error）
  failed_count=0
  if [ -d "$output_dir" ]; then
    for full_file in "$output_dir"/*_full.json; do
      if [ -f "$full_file" ]; then
        if grep -q '"error"' "$full_file" 2>/dev/null; then
          failed_count=$((failed_count + 1))
        fi
      fi
    done
  fi
  
  echo "  任务统计:"
  echo "    预期: $expected 个"
  echo "    成功: $success_count 个"
  echo "    失败: $failed_count 个"
  echo "    待处理: $((expected - success_count - failed_count)) 个"
  if [ $expected -gt 0 ]; then
    success_rate=$(awk "BEGIN {printf \"%.1f\", ($success_count / $expected) * 100}")
    echo "    成功率: ${success_rate}%"
  fi
  echo "  完成时间: $(date '+%Y-%m-%d %H:%M:%S')"
  echo ""
  
  # 批次间休息（避免 API 限流）
  if [ $current_batch -lt $total_batches ]; then
    sleep_time=30  # 10个一批，休息时间可以短一点
    echo "  休息 ${sleep_time} 秒后启动下一批次..."
    sleep $sleep_time
    echo ""
  fi
  
  current_batch=$((current_batch + 1))
  done

else
  # ===== 并行执行模式 =====
  echo "🚀 开始并行执行..."
  echo ""
  
  running_pids=()
  running_batches=()
  batch_index=0
  completed_count=0
  
  # 启动任务的函数
  start_batch() {
    local batch=$1
    local index=$2
    
    start=$(echo $batch | cut -d: -f1)
    end=$(echo $batch | cut -d: -f2)
    
    output_dir="./evaluation/batch/${MODEL_NAME}_swe_bench_output_batch_${start}_${end}"
    log_file="./evaluation/logs/${MODEL_NAME}_batch_${start}_${end}.log"
    
    echo "[$(date '+%H:%M:%S')] 启动批次 $index/$total_batches: [$start, $end)"
    
    nohup "$PYTHON_CMD" -u test_tmux_cc_experience.py \
      --start-index $start --end-index $end \
      --output-dir "$output_dir" \
      --anthropic-model "$ANTHROPIC_MODEL" \
      --no-validate --in-container \
      > "$log_file" 2>&1 &
    
    local pid=$!
    echo "  ✓ PID: $pid | 日志: $log_file"
    
    running_pids+=($pid)
    running_batches+=("$start:$end")
  }
  
  # 等待一个任务完成的函数（兼容旧版bash）
  wait_for_any() {
    while true; do
      for i in "${!running_pids[@]}"; do
        if ! kill -0 ${running_pids[$i]} 2>/dev/null; then
          local batch_range="${running_batches[$i]}"
          wait ${running_pids[$i]} 2>/dev/null
          local exit_code=$?
          
          ((completed_count++))
          echo ""
          echo "[$(date '+%H:%M:%S')] ✓ 批次 [$batch_range] 完成 (退出码: $exit_code) [$completed_count/$total_batches]"
          
          # 输出简要统计
          local start_idx=$(echo $batch_range | cut -d: -f1)
          local end_idx=$(echo $batch_range | cut -d: -f2)
          local batch_output="./evaluation/batch/${MODEL_NAME}_swe_bench_output_batch_${start_idx}_${end_idx}"
          
          if [ -d "$batch_output/predictions/" ]; then
            local success=$(ls -1 "$batch_output/predictions/" 2>/dev/null | wc -l)
            echo "  成功: $success 个"
          fi
          
          unset running_pids[$i]
          unset running_batches[$i]
          
          # 重建数组索引
          running_pids=("${running_pids[@]}")
          running_batches=("${running_batches[@]}")
          return 0
        fi
      done
      sleep 1
    done
  }
  
  # 分发批次到并行任务
  for batch in "${batches[@]}"; do
    ((batch_index++))
    
    # 如果已达到并行上限，等待一个任务完成
    while [ ${#running_pids[@]} -ge $PARALLEL_JOBS ]; do
      wait_for_any
    done
    
    # 启动新批次
    start_batch "$batch" "$batch_index"
    
    # 批次间短暂间隔，避免同时启动造成资源抢占
    sleep 3
  done
  
  # 等待所有剩余批次完成
  echo ""
  echo "等待所有剩余批次完成..."
  while [ ${#running_pids[@]} -gt 0 ]; do
    wait_for_any
  done
  
  echo ""
  echo "[$(date '+%H:%M:%S')] ✓ 所有批次执行完毕"
fi

echo ""
echo "========================================"
echo "所有批次执行完成"
echo "结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# 汇总统计
echo "=========================================="
echo "总体统计:"
echo "=========================================="
total_expected=0
total_success=0
total_failed=0

for batch in "${batches[@]}"; do
  start=$(echo $batch | cut -d: -f1)
  end=$(echo $batch | cut -d: -f2)
  output_dir="./evaluation/batch/${MODEL_NAME}_swe_bench_output_batch_${start}_${end}"
  
  expected=$((end - start))
  total_expected=$((total_expected + expected))
  
  # 统计成功
  if [ -d "$output_dir/predictions/" ]; then
    success=$(ls -1 "$output_dir/predictions/" 2>/dev/null | wc -l)
  else
    success=0
  fi
  total_success=$((total_success + success))
  
  # 统计失败
  failed=0
  if [ -d "$output_dir" ]; then
    for full_file in "$output_dir"/*_full.json; do
      if [ -f "$full_file" ]; then
        if grep -q '"error"' "$full_file" 2>/dev/null; then
          failed=$((failed + 1))
        fi
      fi
    done
  fi
  total_failed=$((total_failed + failed))
  
  pending=$((expected - success - failed))
  
  status="✓"
  if [ $failed -gt 0 ]; then
    status="⚠️"
  fi
  if [ $pending -gt 0 ]; then
    status="❌"
  fi
  
  echo "  $status 批次 [$start, $end): 成功 $success, 失败 $failed, 待处理 $pending / 总计 $expected"
done

echo ""
echo "总计:"
echo "  预期任务: $total_expected 个"
echo "  成功完成: $total_success 个"
echo "  失败需重试: $total_failed 个"
echo "  未处理: $((total_expected - total_success - total_failed)) 个"

if [ $total_expected -gt 0 ]; then
  success_rate=$(awk "BEGIN {printf \"%.1f\", ($total_success / $total_expected) * 100}")
  echo "  总成功率: ${success_rate}%"
fi

echo ""
echo "💡 提示:"
if [ $total_failed -gt 0 ] || [ $((total_expected - total_success - total_failed)) -gt 0 ]; then
  echo "  检测到失败或未完成的任务，直接重新运行此脚本即可自动重试："
  echo "  bash run_batch.sh"
  echo ""
  echo "  自动跳过已成功的任务，只重试失败的任务 ✨"
else
  echo "  所有任务已成功完成！🎉"
fi

echo ""
echo "日志目录: ./evaluation/logs/"
echo "结果目录: ./evaluation/batch/"

# 如果启用了评估，批量评估所有已完成的 predictions
if [ "$ENABLE_EVAL" = true ]; then
  echo ""
  echo "========================================"
  echo "开始批量评估所有 predictions..."
  echo "========================================"
  
  # 收集所有批次的 predictions 目录
  all_predictions=()
  for batch in "${batches[@]}"; do
    IFS=":" read -r start end <<< "$batch"
    output_dir="./evaluation/batch/${MODEL_NAME}_swe_bench_output_${start}_${end}"
    
    if [ -d "$output_dir/predictions" ]; then
      for pred_file in "$output_dir/predictions/"*.json; do
        if [ -f "$pred_file" ]; then
          all_predictions+=("$pred_file")
        fi
      done
    fi
  done
  
  echo "找到 ${#all_predictions[@]} 个 prediction 文件"
  
  if [ ${#all_predictions[@]} -gt 0 ]; then
    eval_results_dir="./evaluation/batch/${MODEL_NAME}_eval_results"
    mkdir -p "$eval_results_dir"
    
    echo "开始评估..."
    eval_count=0
    
    for pred_file in "${all_predictions[@]}"; do
      instance_id=$(basename "$pred_file" .json)
      eval_log_file="./evaluation/logs/${MODEL_NAME}_eval_${instance_id}.log"
      
      ((eval_count++))
      echo "[$eval_count/${#all_predictions[@]}] 评估: $instance_id"
      
      "$PYTHON_CMD" evaluate_single_instance.py \
        --instance-id "$instance_id" \
        --prediction-file "$pred_file" \
        --dataset-path "$DATASET_PATH" \
        --scripts-dir "$SCRIPTS_DIR" \
        --output-dir "$eval_results_dir" \
        --dockerhub-username "$DOCKERHUB_USERNAME" \
        --use-local-docker \
        --prefix "${MODEL_NAME}" \
        > "$eval_log_file" 2>&1
      
      if [ $? -eq 0 ]; then
        echo "  ✓ RESOLVED"
      else
        echo "  ✗ FAILED"
      fi
    done
    
    echo ""
    echo "========================================"
    echo "生成评估汇总报告..."
    echo "========================================"
    
    eval_summary_file="./evaluation/batch/${MODEL_NAME}_eval_summary.json"
    
    "$PYTHON_CMD" summarize_eval_results.py \
      --eval-results-dir "$eval_results_dir" \
      --output-file "$eval_summary_file" \
      --detailed-output "./evaluation/batch/${MODEL_NAME}_eval_detailed.json"
    
    echo ""
    echo "评估报告已保存:"
    echo "  摘要: $eval_summary_file"
    echo "  详细: ./evaluation/batch/${MODEL_NAME}_eval_detailed.json"
  else
    echo "没有找到任何 prediction 文件，跳过评估"
  fi
fi
