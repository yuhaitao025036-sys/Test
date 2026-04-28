#!/bin/bash
################################################################################
# SWE-bench 批量批处理管理脚本
#
# 自动化创建多个 tmux session 来并行处理任务
#
# 用法:
#   ./batch_manager.sh <command> [options]
#
# 命令:
#   start    - 启动批处理
#   list     - 列出所有批次
#   status   - 查看所有批次状态
#   attach   - 连接到指定批次
#   stop     - 停止指定批次
#   stopall  - 停止所有批次
#   logs     - 查看指定批次的日志
#
################################################################################

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="${SCRIPT_DIR}/logs"

# 创建日志目录
mkdir -p "$LOG_DIR"

################################################################################
# 命令: start - 启动批处理
################################################################################
cmd_start() {
    local total_tasks=${1:-100}
    local batch_size=${2:-50}
    local extra_args=${3:-""}
    
    local num_batches=$(( (total_tasks + batch_size - 1) / batch_size ))
    
    echo "========================================"
    log_info "批处理配置"
    echo "========================================"
    echo "总任务数:   $total_tasks"
    echo "批次大小:   $batch_size"
    echo "批次数量:   $num_batches"
    echo "额外参数:   ${extra_args:-无}"
    echo "========================================"
    echo ""
    
    read -p "确认启动 $num_batches 个批次? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        log_info "已取消"
        return
    fi
    
    for ((i=0; i<num_batches; i++)); do
        local start=$((i * batch_size))
        local end=$((start + batch_size))
        
        if [ $end -gt $total_tasks ]; then
            end=$total_tasks
        fi
        
        local session_name="batch_${start}_${end}"
        
        echo ""
        log_info "启动批次 $((i+1))/$num_batches: $session_name"
        
        # 调用 run_with_tmux.sh
        if [ -f "${SCRIPT_DIR}/run_with_tmux.sh" ]; then
            bash "${SCRIPT_DIR}/run_with_tmux.sh" "$session_name" "$start" "$end" $extra_args <<< "n"
        else
            log_error "找不到 run_with_tmux.sh"
            return 1
        fi
        
        sleep 1
    done
    
    echo ""
    log_success "所有批次已启动！"
    echo ""
    cmd_list
}

################################################################################
# 命令: list - 列出所有批次
################################################################################
cmd_list() {
    echo "========================================"
    log_info "运行中的批次 (tmux sessions)"
    echo "========================================"
    
    if ! tmux ls 2>/dev/null | grep "^batch_"; then
        log_warning "没有运行中的批次"
    fi
    
    echo ""
}

################################################################################
# 命令: status - 查看所有批次状态
################################################################################
cmd_status() {
    echo "========================================"
    log_info "批次详细状态"
    echo "========================================"
    echo ""
    
    local sessions=$(tmux ls 2>/dev/null | grep "^batch_" | cut -d: -f1 || true)
    
    if [ -z "$sessions" ]; then
        log_warning "没有运行中的批次"
        return
    fi
    
    printf "%-20s %-15s %-10s %-30s\n" "Session" "任务范围" "状态" "最近日志"
    echo "--------------------------------------------------------------------------------"
    
    for session in $sessions; do
        local log_file="${LOG_DIR}/${session}.log"
        local status="运行中"
        local last_log="无"
        
        # 检查 session 是否存活
        if ! tmux has-session -t "$session" 2>/dev/null; then
            status="已停止"
        fi
        
        # 获取最近的日志行
        if [ -f "$log_file" ]; then
            last_log=$(tail -1 "$log_file" 2>/dev/null | cut -c1-50 || echo "无")
        fi
        
        # 从 session 名称提取范围
        local range=$(echo "$session" | sed 's/batch_//' | sed 's/_/-/')
        
        printf "%-20s %-15s ${GREEN}%-10s${NC} %-30s\n" "$session" "[$range)" "$status" "$last_log"
    done
    
    echo ""
}

################################################################################
# 命令: attach - 连接到指定批次
################################################################################
cmd_attach() {
    local session_name=$1
    
    if [ -z "$session_name" ]; then
        echo "可用的批次:"
        tmux ls 2>/dev/null | grep "^batch_" || log_warning "没有运行中的批次"
        echo ""
        read -p "请输入要查看的 session 名称: " session_name
    fi
    
    if ! tmux has-session -t "$session_name" 2>/dev/null; then
        log_error "Session '$session_name' 不存在"
        return 1
    fi
    
    log_info "正在连接到 $session_name..."
    log_warning "退出查看时按 Ctrl+B 再按 D（不要直接 Ctrl+C）"
    sleep 2
    tmux attach -t "$session_name"
}

################################################################################
# 命令: stop - 停止指定批次
################################################################################
cmd_stop() {
    local session_name=$1
    
    if [ -z "$session_name" ]; then
        echo "运行中的批次:"
        tmux ls 2>/dev/null | grep "^batch_" || log_warning "没有运行中的批次"
        echo ""
        read -p "请输入要停止的 session 名称: " session_name
    fi
    
    if ! tmux has-session -t "$session_name" 2>/dev/null; then
        log_error "Session '$session_name' 不存在"
        return 1
    fi
    
    read -p "确认停止 '$session_name'? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        tmux kill-session -t "$session_name"
        log_success "已停止 $session_name"
    else
        log_info "已取消"
    fi
}

################################################################################
# 命令: stopall - 停止所有批次
################################################################################
cmd_stopall() {
    local sessions=$(tmux ls 2>/dev/null | grep "^batch_" | cut -d: -f1 || true)
    
    if [ -z "$sessions" ]; then
        log_warning "没有运行中的批次"
        return
    fi
    
    echo "将停止以下批次:"
    echo "$sessions"
    echo ""
    
    read -p "确认停止所有批次? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for session in $sessions; do
            tmux kill-session -t "$session"
            log_success "已停止 $session"
        done
    else
        log_info "已取消"
    fi
}

################################################################################
# 命令: logs - 查看指定批次的日志
################################################################################
cmd_logs() {
    local session_name=$1
    local follow=${2:-false}
    
    if [ -z "$session_name" ]; then
        echo "可用的日志文件:"
        ls -1 "$LOG_DIR"/*.log 2>/dev/null | sed 's|.*/||' || log_warning "没有日志文件"
        echo ""
        read -p "请输入 session 名称: " session_name
    fi
    
    local log_file="${LOG_DIR}/${session_name}.log"
    
    if [ ! -f "$log_file" ]; then
        log_error "日志文件不存在: $log_file"
        return 1
    fi
    
    if [ "$follow" = "true" ] || [ "$follow" = "-f" ]; then
        log_info "实时查看日志（按 Ctrl+C 退出）: $log_file"
        tail -f "$log_file"
    else
        log_info "查看最近50行日志: $log_file"
        tail -50 "$log_file"
    fi
}

################################################################################
# 命令: progress - 查看整体进度
################################################################################
cmd_progress() {
    local output_dir="${SCRIPT_DIR}/swe_bench_output_ducc"
    
    echo "========================================"
    log_info "整体进度"
    echo "========================================"
    
    if [ ! -d "$output_dir/tasks" ]; then
        log_warning "输出目录不存在: $output_dir"
        return
    fi
    
    local completed=$(ls -1 "$output_dir/tasks" 2>/dev/null | wc -l)
    
    echo "已完成任务数: $completed"
    echo ""
    
    if [ -f "$output_dir/all_preds.jsonl" ]; then
        local preds=$(wc -l < "$output_dir/all_preds.jsonl")
        echo "生成的预测数: $preds"
        echo ""
    fi
    
    # 显示各批次进度
    echo "各批次日志大小:"
    du -h "$LOG_DIR"/*.log 2>/dev/null | sort -h || echo "无日志文件"
    
    echo ""
}

################################################################################
# 主程序
################################################################################
main() {
    local command=${1:-help}
    shift || true
    
    case "$command" in
        start)
            cmd_start "$@"
            ;;
        list|ls)
            cmd_list
            ;;
        status|st)
            cmd_status
            ;;
        attach|a)
            cmd_attach "$@"
            ;;
        stop)
            cmd_stop "$@"
            ;;
        stopall)
            cmd_stopall
            ;;
        logs|log)
            cmd_logs "$@"
            ;;
        progress|pg)
            cmd_progress
            ;;
        help|-h|--help)
            cat << EOF
SWE-bench 批量批处理管理工具

用法: $0 <command> [options]

命令:
  start [total] [batch_size] [extra_args]  启动批处理
      total      - 总任务数 (默认: 100)
      batch_size - 每批任务数 (默认: 50)
      extra_args - 额外参数 (如: --no-validate)
      
  list, ls                  列出所有批次
  status, st                查看所有批次状态
  attach, a [session]       连接到指定批次
  stop [session]            停止指定批次
  stopall                   停止所有批次
  logs, log [session] [-f]  查看批次日志 (-f 实时)
  progress, pg              查看整体进度
  help, -h, --help          显示此帮助

示例:
  # 启动批处理 (100个任务，每批50个)
  $0 start 100 50

  # 启动批处理并禁用验证
  $0 start 100 50 --no-validate

  # 列出所有批次
  $0 list

  # 查看批次状态
  $0 status

  # 连接到批次查看
  $0 attach batch_0_50

  # 查看日志
  $0 logs batch_0_50

  # 实时查看日志
  $0 logs batch_0_50 -f

  # 停止批次
  $0 stop batch_0_50

  # 查看整体进度
  $0 progress

Tmux 快捷键:
  Ctrl+B D  - 退出查看（不终止任务）
  Ctrl+B [  - 进入滚动模式（可以翻页查看历史）
  Ctrl+B ?  - 显示所有快捷键

EOF
            ;;
        *)
            log_error "未知命令: $command"
            echo ""
            echo "使用 '$0 help' 查看帮助"
            exit 1
            ;;
    esac
}

main "$@"
