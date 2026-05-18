#!/bin/bash
# 验证脚本 - 检查目录结构和依赖完整性

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo "=========================================="
echo "验证 SWE-bench 集成评估系统"
echo "=========================================="
echo ""

error_count=0

# 检查核心脚本
echo "1. 检查核心脚本..."
scripts=(
  "evaluate_single_instance.py"
  "summarize_eval_results.py"
  "run_batch_by_ids.sh"
  "run_batch.sh"
  "test_tmux_cc_experience.py"
)

for script in "${scripts[@]}"; do
  if [ -f "$script" ]; then
    echo "   ✓ $script"
  else
    echo "   ✗ $script (缺失)"
    ((error_count++))
  fi
done
echo ""

# 检查文档
echo "2. 检查文档..."
docs=(
  "README.md"
  "QUICK_START.md"
  "DEPLOYMENT.md"
  "docs/INTEGRATED_EVAL_GUIDE.md"
  "docs/QUICK_START_EVAL.md"
  "docs/IMPLEMENTATION_COMPLETE.md"
)

for doc in "${docs[@]}"; do
  if [ -f "$doc" ]; then
    echo "   ✓ $doc"
  else
    echo "   ✗ $doc (缺失)"
    ((error_count++))
  fi
done
echo ""

# 检查 SWE-bench_Pro-os
echo "3. 检查 SWE-bench_Pro-os 目录..."
swe_files=(
  "SWE-bench_Pro-os/swe_bench_pro_eval.py"
  "SWE-bench_Pro-os/helper_code"
  "SWE-bench_Pro-os/dockerfiles"
  "SWE-bench_Pro-os/run_scripts"
)

for file in "${swe_files[@]}"; do
  if [ -e "$file" ]; then
    echo "   ✓ $file"
  else
    echo "   ✗ $file (缺失)"
    ((error_count++))
  fi
done

# 统计 run_scripts 数量
if [ -d "SWE-bench_Pro-os/run_scripts" ]; then
  script_count=$(ls -1 SWE-bench_Pro-os/run_scripts | wc -l | tr -d ' ')
  echo "   ✓ run_scripts 包含 $script_count 个实例"
fi
echo ""

# 检查 Python 依赖
echo "4. 检查 Python 依赖..."
if command -v python3 &> /dev/null; then
  python_version=$(python3 --version)
  echo "   ✓ Python: $python_version"
  
  # 检查 pandas
  if python3 -c "import pandas" 2>/dev/null; then
    echo "   ✓ pandas 已安装"
  else
    echo "   ⚠️  pandas 未安装 (pip install pandas)"
    ((error_count++))
  fi
  
  # 检查 docker
  if python3 -c "import docker" 2>/dev/null; then
    echo "   ✓ docker (Python) 已安装"
  else
    echo "   ⚠️  docker (Python) 未安装 (pip install docker)"
    ((error_count++))
  fi
else
  echo "   ✗ Python3 未安装"
  ((error_count++))
fi
echo ""

# 检查 Docker
echo "5. 检查 Docker..."
if command -v docker &> /dev/null; then
  docker_version=$(docker --version)
  echo "   ✓ Docker: $docker_version"
  
  if docker ps &> /dev/null; then
    echo "   ✓ Docker 运行正常"
  else
    echo "   ⚠️  Docker 未运行或权限不足"
    ((error_count++))
  fi
else
  echo "   ✗ Docker 未安装"
  ((error_count++))
fi
echo ""

# 检查可执行权限
echo "6. 检查可执行权限..."
exec_files=(
  "run_batch_by_ids.sh"
  "run_batch.sh"
  "evaluate_single_instance.py"
  "summarize_eval_results.py"
)

for file in "${exec_files[@]}"; do
  if [ -x "$file" ]; then
    echo "   ✓ $file"
  else
    echo "   ⚠️  $file (不可执行，运行: chmod +x $file)"
  fi
done
echo ""

# 统计信息
echo "7. 统计信息..."
total_files=$(find . -type f | wc -l | tr -d ' ')
total_dirs=$(find . -type d | wc -l | tr -d ' ')
total_size=$(du -sh . | awk '{print $1}')
echo "   文件数: $total_files"
echo "   目录数: $total_dirs"
echo "   总大小: $total_size"
echo ""

# 最终结果
echo "=========================================="
if [ $error_count -eq 0 ]; then
  echo "✅ 验证通过！所有核心文件都已就绪"
  echo "=========================================="
  echo ""
  echo "下一步:"
  echo "  1. 查看快速开始: cat QUICK_START.md"
  echo "  2. 准备测试数据: 确保有 swe_bench_pro_test.csv"
  echo "  3. 运行测试: bash run_batch_by_ids.sh --ids-file example_ids.txt --model claude --enable-eval"
  exit 0
else
  echo "⚠️  验证发现 $error_count 个问题"
  echo "=========================================="
  echo ""
  echo "请解决上述问题后重试"
  exit 1
fi
