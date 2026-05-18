#!/bin/bash
# 启动前预检脚本 - 在运行批处理任务前必须执行

echo "=================================================="
echo "  SWE-bench 批处理任务启动前检查"
echo "=================================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# ============================================
# 检查1: 数据集文件路径
# ============================================
echo "检查 1/8: 数据集文件"
echo "-------------------"

# 默认路径
DEFAULT_DATASET="/ssd1/Dejavu/datasets/SWE-bench_Pro/test-python.parquet"

if [ -f "$DEFAULT_DATASET" ]; then
  echo -e "${GREEN}✓${NC} 数据集文件存在: $DEFAULT_DATASET"
  
  # 检查文件大小
  file_size=$(stat -f%z "$DEFAULT_DATASET" 2>/dev/null || stat -c%s "$DEFAULT_DATASET" 2>/dev/null)
  if [ "$file_size" -gt 1000000 ]; then
    echo -e "${GREEN}✓${NC} 文件大小正常: $(numfmt --to=iec-i --suffix=B $file_size 2>/dev/null || echo "$file_size bytes")"
  else
    echo -e "${RED}✗${NC} 文件太小，可能损坏: $file_size bytes"
    ERRORS=$((ERRORS + 1))
  fi
else
  echo -e "${RED}✗${NC} 数据集文件不存在: $DEFAULT_DATASET"
  echo ""
  echo -e "${YELLOW}建议操作:${NC}"
  echo "  1. 检查文件路径是否正确"
  echo "  2. 或使用 --dataset-path 参数指定正确的路径"
  echo "  3. 或设置环境变量: export SWE_BENCH_DATASET='/your/path/to/dataset.parquet'"
  ERRORS=$((ERRORS + 1))
fi
echo ""

# ============================================
# 检查2: Python 环境
# ============================================
echo "检查 2/8: Python 环境"
echo "-------------------"

# 检查 Python 命令
if [ -n "$PYTHON_CMD" ]; then
  PYTHON_TO_CHECK="$PYTHON_CMD"
elif [ -x "$HOME/miniconda3/envs/dejavu/bin/python3" ]; then
  PYTHON_TO_CHECK="$HOME/miniconda3/envs/dejavu/bin/python3"
else
  PYTHON_TO_CHECK="$(which python3 2>/dev/null || which python 2>/dev/null)"
fi

if command -v "$PYTHON_TO_CHECK" &> /dev/null; then
  echo -e "${GREEN}✓${NC} Python 解释器: $PYTHON_TO_CHECK"
  py_version=$("$PYTHON_TO_CHECK" --version 2>&1)
  echo -e "${GREEN}✓${NC} 版本: $py_version"
else
  echo -e "${RED}✗${NC} 找不到 Python 解释器"
  echo -e "${YELLOW}建议操作:${NC}"
  echo "  export PYTHON_CMD='/path/to/your/python3'"
  ERRORS=$((ERRORS + 1))
fi
echo ""

# ============================================
# 检查3: Python 依赖包
# ============================================
echo "检查 3/8: Python 依赖包"
echo "-------------------"

required_packages=("pandas" "docker" "datasets")
for pkg in "${required_packages[@]}"; do
  if "$PYTHON_TO_CHECK" -c "import $pkg" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} $pkg"
  else
    echo -e "${RED}✗${NC} $pkg 未安装"
    ERRORS=$((ERRORS + 1))
  fi
done

# 检查 pyarrow (parquet 支持)
if "$PYTHON_TO_CHECK" -c "import pyarrow" 2>/dev/null; then
  echo -e "${GREEN}✓${NC} pyarrow (parquet 文件支持)"
else
  echo -e "${YELLOW}⚠${NC} pyarrow 未安装，无法读取 parquet 文件"
  echo -e "${YELLOW}建议操作:${NC}"
  echo "  $PYTHON_TO_CHECK -m pip install pyarrow"
  WARNINGS=$((WARNINGS + 1))
fi
echo ""

# ============================================
# 检查4: Docker 环境
# ============================================
echo "检查 4/8: Docker 环境"
echo "-------------------"

if command -v docker &> /dev/null; then
  echo -e "${GREEN}✓${NC} Docker 命令可用"
  
  # 检查 Docker 守护进程
  if docker info &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker 守护进程运行中"
  else
    echo -e "${RED}✗${NC} Docker 守护进程未运行"
    echo -e "${YELLOW}建议操作:${NC}"
    echo "  启动 Docker Desktop 或 Docker 服务"
    ERRORS=$((ERRORS + 1))
  fi
else
  echo -e "${RED}✗${NC} Docker 未安装"
  ERRORS=$((ERRORS + 1))
fi
echo ""

# ============================================
# 检查5: SWE-bench_Pro-os 目录
# ============================================
echo "检查 5/8: SWE-bench_Pro-os 目录"
echo "-------------------"

if [ -d "./SWE-bench_Pro-os" ]; then
  echo -e "${GREEN}✓${NC} SWE-bench_Pro-os 目录存在"
  
  # 检查关键文件
  if [ -f "./SWE-bench_Pro-os/swe_bench_pro_eval.py" ]; then
    echo -e "${GREEN}✓${NC} swe_bench_pro_eval.py"
  else
    echo -e "${RED}✗${NC} swe_bench_pro_eval.py 缺失"
    ERRORS=$((ERRORS + 1))
  fi
  
  if [ -d "./SWE-bench_Pro-os/run_scripts" ]; then
    script_count=$(ls -1 ./SWE-bench_Pro-os/run_scripts/*.sh 2>/dev/null | wc -l | xargs)
    echo -e "${GREEN}✓${NC} run_scripts/ ($script_count 个脚本)"
  else
    echo -e "${RED}✗${NC} run_scripts/ 目录缺失"
    ERRORS=$((ERRORS + 1))
  fi
else
  echo -e "${RED}✗${NC} SWE-bench_Pro-os 目录不存在"
  ERRORS=$((ERRORS + 1))
fi
echo ""

# ============================================
# 检查6: 核心脚本文件
# ============================================
echo "检查 6/8: 核心脚本文件"
echo "-------------------"

scripts=("test_tmux_cc_experience.py" "evaluate_single_instance.py" "summarize_eval_results.py" "run_batch_by_ids.sh" "run_batch.sh")
for script in "${scripts[@]}"; do
  if [ -f "./$script" ]; then
    echo -e "${GREEN}✓${NC} $script"
  else
    echo -e "${RED}✗${NC} $script 缺失"
    ERRORS=$((ERRORS + 1))
  fi
done
echo ""

# ============================================
# 检查7: 输出目录权限
# ============================================
echo "检查 7/8: 输出目录权限"
echo "-------------------"

# 创建测试目录
test_dir="./evaluation/test_$$"
if mkdir -p "$test_dir" 2>/dev/null; then
  echo -e "${GREEN}✓${NC} 可以创建输出目录"
  rmdir "$test_dir"
  
  # 清理测试目录的父目录（如果为空）
  rmdir ./evaluation 2>/dev/null
else
  echo -e "${RED}✗${NC} 无法创建输出目录"
  ERRORS=$((ERRORS + 1))
fi
echo ""

# ============================================
# 检查8: 百度 CC settings (可选)
# ============================================
echo "检查 8/8: 百度 CC 配置 (可选)"
echo "-------------------"

settings_file="$HOME/.baidu-cc/baidu-cc/settings.json"
if [ -f "$settings_file" ]; then
  echo -e "${GREEN}✓${NC} settings.json 存在"
  
  # 检查是否包含 anthropic 配置
  if grep -q "anthropic" "$settings_file" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} 包含 Anthropic 配置"
  else
    echo -e "${YELLOW}⚠${NC} 未找到 Anthropic 配置"
    echo -e "${YELLOW}建议:${NC} 使用 --anthropic-model 等参数手动指定"
    WARNINGS=$((WARNINGS + 1))
  fi
else
  echo -e "${YELLOW}⚠${NC} settings.json 不存在: $settings_file"
  echo -e "${YELLOW}建议:${NC} 使用命令行参数传递模型配置"
  WARNINGS=$((WARNINGS + 1))
fi
echo ""

# ============================================
# 总结报告
# ============================================
echo "=================================================="
echo "  检查完成"
echo "=================================================="
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
  echo -e "${GREEN}✓ 所有检查通过！可以开始运行任务${NC}"
  echo ""
  exit 0
elif [ $ERRORS -eq 0 ]; then
  echo -e "${YELLOW}⚠ 发现 $WARNINGS 个警告，但可以运行${NC}"
  echo ""
  exit 0
else
  echo -e "${RED}✗ 发现 $ERRORS 个错误，$WARNINGS 个警告${NC}"
  echo -e "${RED}请修复错误后再运行任务${NC}"
  echo ""
  exit 1
fi
