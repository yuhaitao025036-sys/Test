#!/bin/bash
# 清理服务器上错误架构的镜像

echo "=========================================="
echo "清理服务器上的 SWE-bench 镜像"
echo "=========================================="
echo ""

# 1. 停止所有相关容器
echo "1. 停止运行中的容器..."
RUNNING=$(docker ps | grep sweap-images | awk '{print $1}')
if [ -n "$RUNNING" ]; then
    echo "  停止容器: $RUNNING"
    echo "$RUNNING" | xargs -r docker stop
    echo "  ✓ 容器已停止"
else
    echo "  没有运行中的容器"
fi
echo ""

# 2. 删除所有相关容器
echo "2. 删除所有容器..."
ALL_CONTAINERS=$(docker ps -a | grep sweap-images | awk '{print $1}')
if [ -n "$ALL_CONTAINERS" ]; then
    echo "  删除容器: $ALL_CONTAINERS"
    echo "$ALL_CONTAINERS" | xargs -r docker rm -f
    echo "  ✓ 容器已删除"
else
    echo "  没有容器需要删除"
fi
echo ""

# 3. 删除所有 sweap-images 镜像
echo "3. 删除所有 sweap-images 镜像..."
IMAGES=$(docker images | grep sweap-images | awk '{print $1":"$2}')
if [ -n "$IMAGES" ]; then
    IMAGE_COUNT=$(echo "$IMAGES" | wc -l)
    echo "  找到 $IMAGE_COUNT 个镜像"
    echo ""
    
    read -p "确认删除这些镜像? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$IMAGES" | xargs -r docker rmi -f
        echo "  ✓ 镜像已删除"
    else
        echo "  已取消"
        exit 0
    fi
else
    echo "  没有镜像需要删除"
fi
echo ""

# 4. 清理悬空镜像
echo "4. 清理悬空镜像..."
docker image prune -f
echo ""

# 5. 显示清理后状态
echo "=========================================="
echo "清理完成"
echo "=========================================="
echo ""
echo "当前 Docker 状态:"
echo "  镜像数: $(docker images | wc -l)"
echo "  容器数: $(docker ps -a | wc -l)"
echo ""
echo "磁盘使用:"
docker system df
echo ""
