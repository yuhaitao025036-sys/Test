#!/bin/bash
# 批量导出SWE-bench镜像

set -e

DATASET_PATH="/Users/yuhaitao01/datasets/SWE-bench_Pro/test-00000-of-00001.parquet"
OUTPUT_DIR="./swebench-images"
MAX_IMAGES=10  # 限制导出数量,避免占用太多空间

echo "=========================================="
echo "批量导出SWE-bench镜像"
echo "=========================================="
echo ""

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 读取镜像列表
echo "正在读取数据集..."
IMAGE_TAGS=$(python3 -c "
import pyarrow.parquet as pq
import pandas as pd

table = pq.read_table('$DATASET_PATH')
df = table.to_pandas()

# 获取前N个唯一的镜像tag
unique_tags = df['dockerhub_tag'].unique()[:$MAX_IMAGES]
for tag in unique_tags:
    print(tag)
")

echo "找到 $(echo "$IMAGE_TAGS" | wc -l) 个唯一镜像"
echo ""

# 逐个处理
index=1
for tag in $IMAGE_TAGS; do
    FULL_IMAGE="jefzda/sweap-images:$tag"
    # 安全的文件名(替换特殊字符)
    SAFE_NAME=$(echo "$tag" | tr '/' '_' | tr ':' '_')
    TAR_FILE="$OUTPUT_DIR/${SAFE_NAME}.tar.gz"
    
    echo "[$index] 处理镜像: $tag"
    
    # 检查是否已导出
    if [ -f "$TAR_FILE" ]; then
        echo "  ✓ 已存在,跳过"
        ((index++))
        continue
    fi
    
    # 检查本地是否有镜像
    if ! docker image inspect "$FULL_IMAGE" &>/dev/null; then
        echo "  正在拉取镜像..."
        if docker pull "$FULL_IMAGE"; then
            echo "  ✓ 拉取成功"
        else
            echo "  ✗ 拉取失败,跳过"
            ((index++))
            continue
        fi
    else
        echo "  ✓ 本地已有镜像"
    fi
    
    # 导出并压缩
    echo "  正在导出..."
    docker save "$FULL_IMAGE" | gzip > "$TAR_FILE"
    SIZE=$(du -h "$TAR_FILE" | cut -f1)
    echo "  ✓ 导出完成: $SIZE"
    
    ((index++))
    echo ""
done

echo "=========================================="
echo "导出完成!"
echo "=========================================="
echo ""
echo "导出位置: $OUTPUT_DIR"
echo "镜像列表:"
ls -lh "$OUTPUT_DIR"
echo ""
echo "传输到服务器:"
echo "  scp -J relay_user@relay_host $OUTPUT_DIR/*.tar.gz target_user@target_host:/tmp/"
echo ""
echo "在服务器上导入:"
echo "  for f in /tmp/*.tar.gz; do docker load -i \$f; done"
echo ""
