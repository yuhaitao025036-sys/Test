#!/bin/bash
# 快速清理 - 无需确认

echo "快速清理 SWE-bench 镜像..."

# 停止并删除容器
docker ps -a | grep sweap-images | awk '{print $1}' | xargs -r docker rm -f 2>/dev/null

# 删除镜像
docker images | grep sweap-images | awk '{print $1":"$2}' | xargs -r docker rmi -f 2>/dev/null

# 清理悬空镜像
docker image prune -f >/dev/null

echo "✓ 清理完成"
docker images | grep sweap-images || echo "没有 sweap-images 镜像"
