#!/bin/bash
# 一键上传脚本 - 上传到服务器 /ssd1/Dejavu/docker_images

set -e

# ============ 配置区域 ============
RELAY_USER="your_relay_user"        # 修改为你的堡垒机用户名
RELAY_HOST="your_relay_host"        # 修改为你的堡垒机地址
RELAY_PORT="22"                      # 修改为你的堡垒机端口

TARGET_USER="your_target_user"      # 修改为目标服务器用户名
TARGET_HOST="your_target_host"      # 修改为目标服务器地址
TARGET_DIR="/ssd1/Dejavu/docker_images"

LOCAL_DIR="./swebench-images-export"
# ==================================

echo "=========================================="
echo "上传SWE-bench镜像到服务器"
echo "=========================================="
echo ""

if [ ! -d "$LOCAL_DIR" ]; then
    echo "✗ 本地目录不存在: $LOCAL_DIR"
    echo "请先运行 ./batch-download.sh"
    exit 1
fi

# 统计文件
FILE_COUNT=$(find "$LOCAL_DIR" -name "*.tar.gz" | wc -l | tr -d ' ')
TOTAL_SIZE=$(du -sh "$LOCAL_DIR" | cut -f1)

echo "准备上传:"
echo "  本地目录: $LOCAL_DIR"
echo "  文件数量: $FILE_COUNT"
echo "  总大小: $TOTAL_SIZE"
echo "  目标路径: ${TARGET_USER}@${TARGET_HOST}:${TARGET_DIR}"
echo ""

read -p "确认上传? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "开始上传..."
echo ""

# 先在服务器创建目录
echo "1. 创建目标目录..."
ssh -J "${RELAY_USER}@${RELAY_HOST}:${RELAY_PORT}" \
    "${TARGET_USER}@${TARGET_HOST}" \
    "mkdir -p ${TARGET_DIR}"
echo "✓ 目录已创建"
echo ""

# 打包
echo "2. 打包镜像文件..."
ARCHIVE="swebench-images-$(date +%Y%m%d_%H%M%S).tar.gz"
tar czf "$ARCHIVE" -C "$LOCAL_DIR" .
ARCHIVE_SIZE=$(du -h "$ARCHIVE" | cut -f1)
echo "✓ 打包完成: $ARCHIVE ($ARCHIVE_SIZE)"
echo ""

# 上传
echo "3. 上传到服务器..."
echo "   (通过堡垒机: ${RELAY_HOST})"
scp -J "${RELAY_USER}@${RELAY_HOST}:${RELAY_PORT}" \
    "$ARCHIVE" \
    "${TARGET_USER}@${TARGET_HOST}:${TARGET_DIR}/"
echo "✓ 上传完成"
echo ""

# 清理本地打包文件
rm "$ARCHIVE"
echo "✓ 本地打包文件已清理"
echo ""

echo "=========================================="
echo "上传成功!"
echo "=========================================="
echo ""
echo "下一步: 在服务器上解压和导入"
echo ""
echo "SSH到服务器:"
echo "  ssh -J ${RELAY_USER}@${RELAY_HOST}:${RELAY_PORT} ${TARGET_USER}@${TARGET_HOST}"
echo ""
echo "解压:"
echo "  cd ${TARGET_DIR}"
echo "  tar xzf $ARCHIVE"
echo ""
echo "导入镜像:"
echo "  cd ${TARGET_DIR}"
echo "  for f in *.tar.gz; do"
echo "    echo \"导入: \$f\""
echo "    gunzip -c \"\$f\" | docker load"
echo "  done"
echo ""
