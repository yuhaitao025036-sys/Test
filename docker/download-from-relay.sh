#!/bin/bash
# 服务器运行: 从本地拉取镜像文件
# 适用于已将文件上传到堡垒机的情况

set -e

# ============ 配置区域 - 请修改为你的实际信息 ============
RELAY_HOST="relay.example.com"          # 堡垒机地址
RELAY_USER="your_username"              # 堡垒机用户名
RELAY_PATH="/tmp/swebench-images"       # 堡垒机上的文件路径

TARGET_DIR="/ssd1/Dejavu/docker_images" # 本服务器的目标路径
# ============================================================

echo "=========================================="
echo "从堡垒机下载镜像到本服务器"
echo "=========================================="
echo ""

# 创建目标目录
mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

echo "目标目录: $TARGET_DIR"
echo "堡垒机: ${RELAY_USER}@${RELAY_HOST}:${RELAY_PATH}"
echo ""

# 从堡垒机下载
echo "开始下载..."
scp -r "${RELAY_USER}@${RELAY_HOST}:${RELAY_PATH}/*.tar.gz" ./ 2>&1

if [ $? -eq 0 ]; then
    echo "✓ 下载完成"
else
    echo "✗ 下载失败"
    exit 1
fi

echo ""
echo "=========================================="
echo "下载完成,开始导入镜像"
echo "=========================================="
echo ""

# 统计文件
FILE_COUNT=$(ls *.tar.gz 2>/dev/null | wc -l | tr -d ' ')
echo "找到 $FILE_COUNT 个镜像文件"
echo ""

# 导入镜像
index=1
success=0
failed=0

for f in *.tar.gz; do
    if [ ! -f "$f" ]; then
        continue
    fi
    
    echo "[$index/$FILE_COUNT] 导入: $f"
    
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
echo "成功: $success"
echo "失败: $failed"
echo ""
echo "已导入的镜像:"
docker images | grep sweap-images | head -10
echo ""
