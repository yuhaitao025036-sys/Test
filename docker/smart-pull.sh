#!/bin/bash
# Docker镜像智能拉取脚本 - 自动尝试多个镜像源

set -e

IMAGE="$1"

if [ -z "$IMAGE" ]; then
    echo "用法: $0 <image:tag>"
    echo "示例: $0 jefzda/sweap-images:nodebb.nodebb-NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5"
    exit 1
fi

echo "=========================================="
echo "智能拉取Docker镜像"
echo "=========================================="
echo "目标镜像: $IMAGE"
echo ""

# 检查本地是否已有
if docker image inspect "$IMAGE" &>/dev/null; then
    echo "✓ 本地已有镜像,无需拉取"
    exit 0
fi

# 镜像源列表
MIRRORS=(
    ""  # 官方源
    "docker.m.daocloud.io"
    "docker.mirrors.sjtug.sjtu.edu.cn"
    "docker.nju.edu.cn"
    "mirror.ccs.tencentyun.com"
)

# 尝试每个镜像源
for mirror in "${MIRRORS[@]}"; do
    if [ -z "$mirror" ]; then
        echo "尝试官方源..."
        PULL_IMAGE="$IMAGE"
    else
        echo "尝试镜像源: $mirror"
        PULL_IMAGE="${mirror}/${IMAGE}"
    fi
    
    echo "  正在拉取: $PULL_IMAGE"
    
    if docker pull "$PULL_IMAGE" 2>&1; then
        echo "  ✓ 拉取成功!"
        
        # 如果使用了镜像源,重新tag
        if [ -n "$mirror" ]; then
            echo "  重命名为原始镜像名..."
            docker tag "$PULL_IMAGE" "$IMAGE"
            echo "  ✓ 重命名完成: $IMAGE"
        fi
        
        echo ""
        echo "=========================================="
        echo "✓ 镜像拉取成功!"
        echo "=========================================="
        docker images | grep -E "(REPOSITORY|${IMAGE%%:*})"
        exit 0
    else
        echo "  ✗ 失败"
        echo ""
    fi
done

echo "=========================================="
echo "✗ 所有镜像源均拉取失败"
echo "=========================================="
exit 1
