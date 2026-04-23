#!/bin/bash
# 在Mac上正确导出x86_64镜像

set -e

DATASET_PATH="/Users/yuhaitao01/datasets/SWE-bench_Pro/test-00000-of-00001.parquet"
OUTPUT_DIR="./swebench-images-export-x64"
BATCH_SIZE=5

echo "=========================================="
echo "导出 x86_64 架构镜像"
echo "=========================================="
echo ""

mkdir -p "$OUTPUT_DIR"

# 读取镜像列表
echo "正在读取数据集..."
TAGS=$(python3 -c "
import pyarrow.parquet as pq
table = pq.read_table('$DATASET_PATH')
df = table.to_pandas()
unique = df['dockerhub_tag'].unique()[:$BATCH_SIZE]
for tag in unique:
    print(tag)
")

echo "将处理 $BATCH_SIZE 个镜像"
echo ""

index=1
total=$(echo "$TAGS" | wc -l | tr -d ' ')

for tag in $TAGS; do
    FULL_IMAGE="jefzda/sweap-images:$tag"
    SAFE_NAME=$(echo "$tag" | sed 's/[\/:]/_/g')
    TAR_FILE="$OUTPUT_DIR/${SAFE_NAME}.tar"
    
    echo "[$index/$total] 处理: $tag"
    
    if [ -f "${TAR_FILE}.gz" ]; then
        echo "  ✓ 已导出,跳过"
        ((index++))
        continue
    fi
    
    # 删除已有镜像
    echo "  删除旧镜像(如果有)..."
    docker rmi "$FULL_IMAGE" 2>/dev/null || true
    
    # 强制拉取 amd64 版本
    echo "  拉取 linux/amd64 镜像..."
    docker pull --platform linux/amd64 "$FULL_IMAGE"
    
    # 验证架构
    ARCH=$(docker inspect "$FULL_IMAGE" --format '{{.Architecture}}')
    echo "  验证架构: $ARCH"
    
    if [ "$ARCH" != "amd64" ]; then
        echo "  ✗ 架构错误: $ARCH,跳过"
        ((index++))
        continue
    fi
    
    # 方法1: 先运行容器,再commit(确保是amd64)
    echo "  启动容器验证..."
    CONTAINER_ID=$(docker create --platform linux/amd64 "$FULL_IMAGE")
    
    # 导出容器为新镜像(强制amd64)
    echo "  导出为tar..."
    docker export "$CONTAINER_ID" | gzip > "${TAR_FILE}.export.gz"
    
    # 清理容器
    docker rm "$CONTAINER_ID"
    
    # 保存配置信息
    docker inspect "$FULL_IMAGE" > "${OUTPUT_DIR}/${SAFE_NAME}.json"
    
    SIZE=$(du -h "${TAR_FILE}.export.gz" | cut -f1)
    echo "  ✓ 完成: ${SIZE}"
    
    ((index++))
    echo ""
done

echo "=========================================="
echo "导出完成!"
echo "=========================================="
echo ""
echo "注意: 使用了 docker export,在服务器导入时需要特殊处理"
