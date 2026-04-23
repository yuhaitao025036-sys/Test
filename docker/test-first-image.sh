#!/bin/bash
# 测试第一个SWE-bench镜像

set -e

echo "=========================================="
echo "测试第一个SWE-bench镜像"
echo "=========================================="
echo ""

# 从数据集获取第一个镜像tag
echo "正在读取数据集..."
IMAGE_TAG=$(python3 -c "
import pyarrow.parquet as pq
table = pq.read_table('/Users/yuhaitao01/datasets/SWE-bench_Pro/test-00000-of-00001.parquet')
df = table.to_pandas()
print(df.iloc[0]['dockerhub_tag'])
")

FULL_IMAGE="jefzda/sweap-images:$IMAGE_TAG"
echo "第一个任务镜像: $FULL_IMAGE"
echo ""

# 拉取镜像
echo "开始拉取镜像..."
echo "提示: 镜像较大(几GB),首次下载需要时间"
echo "按 Ctrl+C 可以中断"
echo ""

docker pull --progress plain "$FULL_IMAGE"

echo ""
echo "=========================================="
echo "✓ 镜像拉取成功!"
echo "=========================================="
echo ""

# 启动容器测试
CONTAINER_NAME="swebench-test-$RANDOM"
echo "启动测试容器: $CONTAINER_NAME"

docker run -d \
  --name "$CONTAINER_NAME" \
  --platform linux/amd64 \
  "$FULL_IMAGE" \
  sleep infinity

echo "✓ 容器已启动"
echo ""

# 等待容器完全启动
sleep 2

# 测试容器功能
echo "=========================================="
echo "测试容器内代码访问"
echo "=========================================="
echo ""

echo "1. 查看 /testbed 目录:"
docker exec "$CONTAINER_NAME" ls -la /testbed/ | head -10
echo ""

echo "2. 统计Python文件数量:"
PY_COUNT=$(docker exec "$CONTAINER_NAME" sh -c "find /testbed -name '*.py' -type f 2>/dev/null | wc -l")
echo "   Python文件数: $PY_COUNT"
echo ""

echo "3. 测试grep搜索 (查找函数定义):"
docker exec "$CONTAINER_NAME" sh -c "grep -r 'def ' /testbed --include='*.py' 2>/dev/null | head -5"
echo ""

echo "4. 测试文件读取 (显示第一个Python文件的前20行):"
docker exec "$CONTAINER_NAME" sh -c "find /testbed -name '*.py' -type f 2>/dev/null | head -1 | xargs head -20"
echo ""

echo "=========================================="
echo "✓ 测试完成!"
echo "=========================================="
echo ""

echo "容器信息:"
echo "  容器名: $CONTAINER_NAME"
echo "  镜像: $FULL_IMAGE"
echo ""
echo "如需进入容器:"
echo "  docker exec -it $CONTAINER_NAME bash"
echo ""
echo "清理容器:"
echo "  docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME"
echo ""

read -p "是否现在清理容器? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker stop "$CONTAINER_NAME" >/dev/null
    docker rm "$CONTAINER_NAME" >/dev/null
    echo "✓ 容器已清理"
else
    echo "容器保留,记得后续手动清理"
fi
