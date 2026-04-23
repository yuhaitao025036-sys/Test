#!/bin/bash
# 在服务器上快速导入镜像

set -e

if [ $# -eq 0 ]; then
    echo "用法: $0 <镜像目录或tar.gz文件>"
    echo "示例:"
    echo "  $0 /tmp/swebench-images/"
    echo "  $0 /tmp/*.tar.gz"
    exit 1
fi

echo "=========================================="
echo "批量导入Docker镜像"
echo "=========================================="
echo ""

# 如果是目录
if [ -d "$1" ]; then
    DIR="$1"
    echo "从目录导入: $DIR"
    FILES=$(find "$DIR" -name "*.tar.gz" -type f)
# 如果是文件列表
else
    FILES="$@"
    echo "导入指定文件"
fi

COUNT=$(echo "$FILES" | wc -l | tr -d ' ')
echo "找到 $COUNT 个镜像文件"
echo ""

index=1
success=0
failed=0

for file in $FILES; do
    if [ ! -f "$file" ]; then
        continue
    fi
    
    echo "[$index/$COUNT] 导入: $(basename "$file")"
    
    if gunzip -c "$file" | docker load 2>&1 | grep -E "(Loaded image|sha256)"; then
        echo "  ✓ 成功"
        ((success++))
    else
        echo "  ✗ 失败"
        ((failed++))
    fi
    
    ((index++))
    echo ""
done

echo "=========================================="
echo "导入完成"
echo "=========================================="
echo "成功: $success"
echo "失败: $failed"
echo ""
echo "已导入的镜像:"
docker images | grep sweap-images | head -20
echo ""
