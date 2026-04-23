#!/bin/bash
# 在服务器上批量拉取镜像(后台运行)

set -e

DATASET_PATH="/ssd1/Dejavu/datasets/SWE-bench_Pro/test-00000-of-00001.parquet"
LOG_FILE="./pull_images.log"
BATCH_SIZE=10  # 先拉10个

echo "开始批量拉取镜像..." | tee -a "$LOG_FILE"
echo "开始时间: $(date)" | tee -a "$LOG_FILE"

# 读取镜像列表
TAGS=$(python3 -c "
import pyarrow.parquet as pq
table = pq.read_table('$DATASET_PATH')
df = table.to_pandas()
unique = df['dockerhub_tag'].unique()[:$BATCH_SIZE]
for tag in unique:
    print(tag)
")

index=1
success=0
failed=0

for tag in $TAGS; do
    FULL_IMAGE="jefzda/sweap-images:$tag"
    echo "" | tee -a "$LOG_FILE"
    echo "[$index/$BATCH_SIZE] $(date '+%H:%M:%S') 拉取: $tag" | tee -a "$LOG_FILE"
    
    if docker pull "$FULL_IMAGE" >> "$LOG_FILE" 2>&1; then
        echo "  ✓ 成功" | tee -a "$LOG_FILE"
        ((success++))
    else
        echo "  ✗ 失败" | tee -a "$LOG_FILE"
        ((failed++))
    fi
    
    ((index++))
done

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "拉取完成!" | tee -a "$LOG_FILE"
echo "结束时间: $(date)" | tee -a "$LOG_FILE"
echo "成功: $success, 失败: $failed" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# 显示已拉取的镜像
echo "" | tee -a "$LOG_FILE"
echo "已拉取的镜像:" | tee -a "$LOG_FILE"
docker images | grep sweap-images | tee -a "$LOG_FILE"
