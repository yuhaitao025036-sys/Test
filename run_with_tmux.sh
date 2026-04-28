#!/bin/bash
################################################################################
# SWE-bench 批处理脚本 - Tmux 版本
#
# 优势:
#   - 可以随时 tmux attach 查看实时输出
#   - 不查看时自动后台运行
#   - 比 nohup 更灵活，可以发送命令到 session
#   - 断线不影响运行
#   - 支持多个批次并行运行
#
# 用法:
#   ./run_with_tmux.sh <session_name> <start_index> <end_index> [extra_args]
#
# 示例:
#   # 运行第一批（0-50）
#   ./run_with_tmux.sh batch_0_50 0 50
#
#   # 运行第二批（50-100），不验证
#   ./run_with_tmux.sh batch_50_100 50 100 --no-validate
#
#   # 查看运行情况
#   tmux attach -t batch_0_50
#
#   # 退出查看（不终止任务）
#   按 Ctrl+B 然后按 D
#
#   # 列出所有运行中的批次
#   tmux ls
#
################################################################################

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查参数
if [ $# -lt 3 ]; then
    log_error "参数不足！"
    echo ""
    echo "用法: $0 <session_name> <start_index> <end_index> [extra_args]"
    echo ""
    echo "示例:"
    echo "  $0 batch_0_50 0 50"
    echo "  $0 batch_50_100 50 100 --no-validate"
    echo "  $0 my_batch 0 10 --use-tmux --timeout 1800"
    echo ""
    exit 1
fi

SESSION_NAME=$1
START_INDEX=$2
END_INDEX=$3
shift 3
EXTRA_ARGS="$@"

# 检查 tmux 是否安装
if ! command -v tmux &> /dev/null; then
    log_error "tmux 未安装！"
    echo ""
    echo "安装方法:"
    echo "  Ubuntu/Debian: sudo apt-get install tmux"
    echo "  CentOS/RHEL:   sudo yum install tmux"
    echo "  macOS:         brew install tmux"
    echo ""
    exit 1
fi

# 检查 session 是否已存在
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    log_warning "Session '$SESSION_NAME' 已存在！"
    echo ""
    echo "选项:"
    echo "  1. 查看该 session:  tmux attach -t $SESSION_NAME"
    echo "  2. 终止该 session:  tmux kill-session -t $SESSION_NAME"
    echo "  3. 使用不同的名称"
    echo ""
    read -p "是否终止并重新创建? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        tmux kill-session -t "$SESSION_NAME"
        log_success "已终止旧 session"
    else
        log_info "退出"
        exit 0
    fi
fi

# 获取脚本目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_FILE="${SCRIPT_DIR}/logs/${SESSION_NAME}.log"

# 创建日志目录
mkdir -p "${SCRIPT_DIR}/logs"

# 构建完整命令
PYTHON_CMD="python test_tmux_cc_experience.py --start-index $START_INDEX --end-index $END_INDEX $EXTRA_ARGS"

# 显示配置
echo "========================================"
log_info "批处理配置"
echo "========================================"
echo "Session 名称: $SESSION_NAME"
echo "任务范围:     [$START_INDEX, $END_INDEX)"
echo "任务数量:     $((END_INDEX - START_INDEX))"
echo "额外参数:     ${EXTRA_ARGS:-无}"
echo "日志文件:     $LOG_FILE"
echo "工作目录:     $SCRIPT_DIR"
echo "========================================"
echo ""

# 创建 tmux session 并运行命令
log_info "创建 tmux session: $SESSION_NAME"

tmux new-session -d -s "$SESSION_NAME" -c "$SCRIPT_DIR"

# 发送命令到 tmux session
tmux send-keys -t "$SESSION_NAME" "cd $SCRIPT_DIR" C-m
tmux send-keys -t "$SESSION_NAME" "echo '===================================='" C-m
tmux send-keys -t "$SESSION_NAME" "echo '开始批处理任务'" C-m
tmux send-keys -t "$SESSION_NAME" "echo 'Session: $SESSION_NAME'" C-m
tmux send-keys -t "$SESSION_NAME" "echo '范围: [$START_INDEX, $END_INDEX)'" C-m
tmux send-keys -t "$SESSION_NAME" "echo '开始时间: \$(date)'" C-m
tmux send-keys -t "$SESSION_NAME" "echo '===================================='" C-m
tmux send-keys -t "$SESSION_NAME" "echo ''" C-m

# 运行主命令，同时输出到终端和日志文件
tmux send-keys -t "$SESSION_NAME" "$PYTHON_CMD 2>&1 | tee $LOG_FILE" C-m

log_success "Session 已创建并开始运行！"
echo ""
echo "========================================"
log_info "如何使用"
echo "========================================"
echo ""
echo "📺 查看运行情况:"
echo "   tmux attach -t $SESSION_NAME"
echo ""
echo "⌨️  退出查看（不终止任务）:"
echo "   按 Ctrl+B，然后按 D"
echo ""
echo "📋 列出所有 session:"
echo "   tmux ls"
echo ""
echo "📄 查看日志文件:"
echo "   tail -f $LOG_FILE"
echo ""
echo "🛑 终止任务:"
echo "   tmux kill-session -t $SESSION_NAME"
echo ""
echo "🔍 监控进度:"
echo "   watch -n 5 'tail -20 $LOG_FILE'"
echo ""
echo "========================================"
echo ""

# 提示是否立即 attach
read -p "是否立即查看运行情况? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo ""
    log_info "正在连接到 session..."
    echo ""
    log_warning "退出查看时按 Ctrl+B 再按 D（不要直接 Ctrl+C，会终止任务）"
    echo ""
    sleep 2
    tmux attach -t "$SESSION_NAME"
else
    log_success "任务在后台运行中"
    echo ""
    log_info "稍后可以用以下命令查看: tmux attach -t $SESSION_NAME"
fi
