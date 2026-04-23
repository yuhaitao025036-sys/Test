#!/bin/bash
# 在目标服务器上导入所有镜像

set -e

IMAGES_DIR="${1:-/tmp}"

echo "=========================================="
echo "批量导入SWE-bench镜像"
echo "=========================================="
echo ""

if [ ! -d "$IMAGES_DIR" ]; then
    echo "✗ 目录不存在: $IMAGES_DIR"
    exit 1
fi

# 查找所有tar.gz文件
TAR_FILES=$(find "$IMAGES_DIR" -name "*.tar.gz" -type f)
COUNT=$(echo "$TAR_FILES" | wc -l)

if [ $COUNT -eq 0 ]; then
    echo "✗ 未找到镜像文件"
    exit 1
fi

echo "找到 $COUNT 个镜像文件"
echo ""

index=1
for tar_file in $TAR_FILES; do
    echo "[$index/$COUNT] 导入: $(basename $tar_file)"
    
    if gunzip -c "$tar_file" | docker load; then
        echo "  ✓ 导入成功"
    else
        echo "  ✗ 导入失败"
    fi
    
    ((index++))
    echo ""
done

echo "=========================================="
echo "导入完成!"
echo "=========================================="
echo ""
echo "已导入的镜像:"
docker images | grep sweap-images
echo ""
