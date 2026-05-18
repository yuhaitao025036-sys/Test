#!/bin/bash
# 打包脚本 - 将 swe_bench_integrated_eval 打包为 tar.gz

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
PACKAGE_NAME="swe_bench_integrated_eval"

echo "=========================================="
echo "打包 SWE-bench 集成评估系统"
echo "=========================================="
echo ""

cd "$PARENT_DIR" || exit 1

echo "1. 检查目录结构..."
if [ ! -d "$PACKAGE_NAME" ]; then
  echo "错误: $PACKAGE_NAME 目录不存在"
  exit 1
fi

echo "   ✓ 目录存在"
echo ""

echo "2. 统计文件数量..."
file_count=$(find "$PACKAGE_NAME" -type f | wc -l | tr -d ' ')
dir_count=$(find "$PACKAGE_NAME" -type d | wc -l | tr -d ' ')
echo "   文件数: $file_count"
echo "   目录数: $dir_count"
echo ""

echo "3. 计算大小..."
size=$(du -sh "$PACKAGE_NAME" | awk '{print $1}')
echo "   总大小: $size"
echo ""

echo "4. 创建打包文件..."
timestamp=$(date +%Y%m%d_%H%M%S)
output_file="${PACKAGE_NAME}_${timestamp}.tar.gz"

tar -czf "$output_file" "$PACKAGE_NAME" \
  --exclude="$PACKAGE_NAME/.git" \
  --exclude="$PACKAGE_NAME/__pycache__" \
  --exclude="$PACKAGE_NAME/.DS_Store" \
  --exclude="$PACKAGE_NAME/*.pyc" \
  --exclude="$PACKAGE_NAME/evaluation"

if [ $? -eq 0 ]; then
  echo "   ✓ 打包完成: $output_file"
else
  echo "   ✗ 打包失败"
  exit 1
fi
echo ""

echo "5. 验证打包文件..."
if [ -f "$output_file" ]; then
  package_size=$(du -sh "$output_file" | awk '{print $1}')
  echo "   文件名: $output_file"
  echo "   大小: $package_size"
  echo "   ✓ 验证通过"
else
  echo "   ✗ 打包文件不存在"
  exit 1
fi
echo ""

echo "=========================================="
echo "打包完成！"
echo "=========================================="
echo ""
echo "打包文件: $output_file"
echo ""
echo "解压使用:"
echo "  tar -xzf $output_file"
echo ""
echo "部署说明:"
echo "  1. 将 $output_file 传输到目标机器"
echo "  2. 解压: tar -xzf $output_file"
echo "  3. 查看: cd $PACKAGE_NAME && cat DEPLOYMENT.md"
echo ""
