#!/bin/bash
# 服务器运行: 解压和导入已上传的镜像

set -e

TARGET_DIR="/ssd1/Dejavu/docker_images"

echo "=========================================="
echo "自动解压和导入Docker镜像"
echo "=========================================="
echo ""

# 检查目录
if [ ! -d "$TARGET_DIR" ]; then
    echo "✗ 目录不存在: $TARGET_DIR"
    exit 1
fi

cd "$TARGET_DIR"
echo "工作目录: $(pwd)"
echo ""

# 查找最新的压缩包
ARCHIVE=$(ls -t swebench-images-*.tar.gz 2>/dev/null | head -1)

if [ -z "$ARCHIVE" ]; then
    echo "⚠️  未找到 swebench-images-*.tar.gz 压缩包"
    echo ""
    echo "将尝试直接导入当前目录的 .tar.gz 文件..."
    echo ""
else
    echo "找到压缩包: $ARCHIVE"
    ARCHIVE_SIZE=$(du -h "$ARCHIVE" | cut -f1)
    echo "大小: $ARCHIVE_SIZE"
    echo ""
    
    read -p "是否解压此文件? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "正在解压..."
        tar xzf "$ARCHIVE"
        echo "✓ 解压完成"
        echo ""
    fi
fi

# 统计镜像文件
IMAGE_FILES=$(ls *.tar.gz 2>/dev/null | grep -v "^swebench-images-" || true)
FILE_COUNT=$(echo "$IMAGE_FILES" | grep -c . || echo "0")

if [ "$FILE_COUNT" -eq "0" ]; then
    echo "✗ 没有找到镜像文件 (*.tar.gz)"
    exit 1
fi

echo "找到 $FILE_COUNT 个镜像文件"
echo ""

read -p "开始导入镜像? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "=========================================="
echo "开始导入"
echo "=========================================="
echo ""

index=1
success=0
failed=0

for f in $IMAGE_FILES; do
    echo "[$index/$FILE_COUNT] 导入: $f"
    
    # 显示文件大小
    SIZE=$(du -h "$f" | cut -f1)
    echo "  大小: $SIZE"
    
    # 导入镜像
    if gunzip -c "$f" | docker load 2>&1 | grep -E "(Loaded image|sha256)"; then
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
echo ""
echo "统计:"
echo "  成功: $success"
echo "  失败: $failed"
echo "  总计: $FILE_COUNT"
echo ""
echo "已导入的镜像:"
docker images | grep sweap-images | head -15
echo ""

if [ $success -gt 0 ]; then
    echo "可选: 清理镜像文件释放空间"
    echo "  cd $TARGET_DIR"
    echo "  rm *.tar.gz"
fi
echo ""
