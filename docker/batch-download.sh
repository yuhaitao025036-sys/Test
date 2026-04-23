#!/bin/bash
# 本地批量下载SWE-bench镜像并打包传输

set -e

DATASET_PATH="/Users/yuhaitao01/datasets/SWE-bench_Pro/test-00000-of-00001.parquet"
OUTPUT_DIR="./swebench-images-export"
BATCH_SIZE=5  # 每次导出5个镜像 (可修改为更小的数字,如2或3)

echo "=========================================="
echo "SWE-bench镜像批量下载和打包"
echo "=========================================="
echo ""

mkdir -p "$OUTPUT_DIR"

# 读取镜像列表
echo "正在读取数据集..."
TAGS=$(python3 -c "
import pyarrow.parquet as pq
table = pq.read_table('$DATASET_PATH')
df = table.to_pandas()
# 获取前N个唯一的tag
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
    
    # 检查是否已导出
    if [ -f "${TAR_FILE}.gz" ]; then
        echo "  ✓ 已导出,跳过"
        ((index++))
        continue
    fi
    
    # 检查并拉取镜像 (强制x86_64架构)
    if ! docker image inspect "$FULL_IMAGE" &>/dev/null; then
        echo "  正在拉取 x86_64 镜像 (可能需要较长时间)..."
        if docker pull --platform linux/amd64 "$FULL_IMAGE" 2>&1 | grep -E "(Pulling|Downloaded|Status)"; then
            echo "  ✓ 拉取成功"
        else
            echo "  ✗ 拉取失败,跳过"
            ((index++))
            continue
        fi
    else
        echo "  ✓ 本地已有镜像,验证架构..."
        ARCH=$(docker inspect "$FULL_IMAGE" | grep -o '"Architecture": "[^"]*"' | cut -d'"' -f4)
        if [ "$ARCH" != "amd64" ]; then
            echo "  ⚠️  当前镜像是 $ARCH 架构,重新拉取 x86_64 版本..."
            docker rmi "$FULL_IMAGE"
            docker pull --platform linux/amd64 "$FULL_IMAGE" 2>&1 | grep -E "(Pulling|Downloaded|Status)"
        fi
    fi
    
    # 导出并压缩
    echo "  正在导出和压缩..."
    docker save "$FULL_IMAGE" -o "$TAR_FILE"
    gzip "$TAR_FILE"
    
    SIZE=$(du -h "${TAR_FILE}.gz" | cut -f1)
    echo "  ✓ 完成: ${SIZE}"
    
    ((index++))
    echo ""
done

# 创建一个清单文件
echo "创建镜像清单..."
MANIFEST="$OUTPUT_DIR/manifest.txt"
echo "# SWE-bench镜像清单" > "$MANIFEST"
echo "# 导出时间: $(date)" >> "$MANIFEST"
echo "# 镜像数量: $total" >> "$MANIFEST"
echo "" >> "$MANIFEST"

for gz_file in "$OUTPUT_DIR"/*.tar.gz; do
    if [ -f "$gz_file" ]; then
        filename=$(basename "$gz_file" .tar.gz)
        size=$(du -h "$gz_file" | cut -f1)
        echo "$filename  $size" >> "$MANIFEST"
    fi
done

echo ""
echo "=========================================="
echo "导出完成!"
echo "=========================================="
echo ""
echo "导出位置: $OUTPUT_DIR"
echo "镜像文件:"
ls -lh "$OUTPUT_DIR"/*.tar.gz 2>/dev/null | awk '{print $9, $5}'
echo ""
echo "总大小:"
du -sh "$OUTPUT_DIR"
echo ""
echo "=========================================="
echo "传输到服务器的命令:"
echo "=========================================="
echo ""
echo "# 方法1: 通过堡垒机直接传输"
echo "scp -J relay_user@relay_host:port \\"
echo "    $OUTPUT_DIR/*.tar.gz \\"
echo "    target_user@target_host:/ssd1/Dejavu/docker_images/"
echo ""
echo "# 方法2: 先打包再传输(推荐,文件多时)"
echo "tar czf swebench-images.tar.gz -C $OUTPUT_DIR ."
echo "scp -J relay_user@relay_host:port \\"
echo "    swebench-images.tar.gz \\"
echo "    target_user@target_host:/ssd1/Dejavu/docker_images/"
echo ""
echo "# 在目标服务器解压:"
echo "cd /ssd1/Dejavu/docker_images && tar xzf swebench-images.tar.gz"
echo ""
echo "# 导入镜像:"
echo "cd /ssd1/Dejavu/docker_images"
echo "for f in *.tar.gz; do"
echo "  echo \"导入: \$f\""
echo "  gunzip -c \"\$f\" | docker load"
echo "done"
echo ""
