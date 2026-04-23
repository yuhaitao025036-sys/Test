#!/bin/bash
# 本地运行: 上传镜像到服务器
# 通过堡垒机跳转上传

set -e

# ============ 配置区域 - 请修改为你的实际信息 ============
RELAY_USER="your_username"              # 堡垒机用户名
RELAY_HOST="relay.example.com"          # 堡垒机地址
RELAY_PORT="22"                         # 堡垒机端口(默认22)

TARGET_USER="your_username"             # 目标服务器用户名
TARGET_HOST="target.example.com"        # 目标服务器地址
TARGET_DIR="/ssd1/Dejavu/docker_images" # 目标服务器路径

LOCAL_DIR="./swebench-images-export"
# ============================================================

echo "=========================================="
echo "上传SWE-bench镜像到服务器"
echo "=========================================="
echo ""

# 检查本地目录
if [ ! -d "$LOCAL_DIR" ]; then
    echo "✗ 本地目录不存在: $LOCAL_DIR"
    echo "请先运行: ./batch-download.sh"
    exit 1
fi

# 统计文件
FILE_COUNT=$(find "$LOCAL_DIR" -name "*.tar.gz" | wc -l | tr -d ' ')
if [ $FILE_COUNT -eq 0 ]; then
    echo "✗ 没有找到镜像文件"
    exit 1
fi

TOTAL_SIZE=$(du -sh "$LOCAL_DIR" | cut -f1)

echo "本地镜像信息:"
echo "  目录: $LOCAL_DIR"
echo "  文件数: $FILE_COUNT"
echo "  总大小: $TOTAL_SIZE"
echo ""
echo "上传目标:"
echo "  堡垒机: ${RELAY_USER}@${RELAY_HOST}:${RELAY_PORT}"
echo "  目标服务器: ${TARGET_USER}@${TARGET_HOST}"
echo "  目标路径: ${TARGET_DIR}"
echo ""

read -p "确认上传? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "=========================================="
echo "开始上传"
echo "=========================================="
echo ""

# 步骤1: 在服务器创建目录
echo "[1/4] 在服务器创建目录..."
ssh -J "${RELAY_USER}@${RELAY_HOST}:${RELAY_PORT}" \
    "${TARGET_USER}@${TARGET_HOST}" \
    "mkdir -p ${TARGET_DIR}" 2>&1

if [ $? -eq 0 ]; then
    echo "✓ 目录创建成功"
else
    echo "✗ 目录创建失败"
    exit 1
fi
echo ""

# 步骤2: 打包镜像
echo "[2/4] 打包镜像文件..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE="swebench-images-${TIMESTAMP}.tar.gz"
echo "  正在打包: $ARCHIVE"

tar czf "$ARCHIVE" -C "$LOCAL_DIR" . 2>&1

ARCHIVE_SIZE=$(du -h "$ARCHIVE" | cut -f1)
echo "✓ 打包完成: $ARCHIVE_SIZE"
echo ""

# 步骤3: 上传到服务器
echo "[3/4] 上传到服务器..."
echo "  (通过堡垒机: ${RELAY_HOST})"
echo "  上传可能需要较长时间,请耐心等待..."
echo ""

scp -J "${RELAY_USER}@${RELAY_HOST}:${RELAY_PORT}" \
    "$ARCHIVE" \
    "${TARGET_USER}@${TARGET_HOST}:${TARGET_DIR}/" 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ 上传完成"
else
    echo ""
    echo "✗ 上传失败"
    rm "$ARCHIVE"
    exit 1
fi
echo ""

# 步骤4: 清理本地打包文件
echo "[4/4] 清理本地临时文件..."
rm "$ARCHIVE"
echo "✓ 清理完成"
echo ""

echo "=========================================="
echo "✓ 上传成功!"
echo "=========================================="
echo ""
echo "镜像已上传到: ${TARGET_DIR}/${ARCHIVE}"
echo ""
echo "下一步: 在服务器上导入镜像"
echo ""
echo "1. SSH到服务器:"
echo "   ssh -J ${RELAY_USER}@${RELAY_HOST}:${RELAY_PORT} ${TARGET_USER}@${TARGET_HOST}"
echo ""
echo "2. 解压和导入:"
echo "   cd ${TARGET_DIR}"
echo "   tar xzf ${ARCHIVE}"
echo "   for f in *.tar.gz; do"
echo "     [[ \"\$f\" == swebench-images-*.tar.gz ]] && continue"
echo "     echo \"导入: \$f\""
echo "     gunzip -c \"\$f\" | docker load"
echo "   done"
echo ""
echo "或者使用自动导入脚本:"
echo "   ./server-import.sh"
echo ""
