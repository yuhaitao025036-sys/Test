#!/bin/bash
# 本地Docker测试脚本 - 测试SWE-bench镜像

set -e

echo "=========================================="
echo "Docker 本地测试 - SWE-bench 镜像"
echo "=========================================="
echo ""

# 步骤1: 检查Docker
echo "步骤1: 检查Docker环境..."
if ! docker ps &>/dev/null; then
    echo "✗ Docker未运行或无权限"
    echo "  请启动Docker Desktop或检查权限"
    exit 1
fi
echo "✓ Docker运行正常"
echo ""

# 步骤2: 拉取一个测试镜像
echo "步骤2: 拉取SWE-bench测试镜像..."
echo "  提示: 这些镜像通常比较大(几GB),首次下载需要时间"
echo ""

# 使用一个相对较小的测试镜像
# 实际的tag需要从数据集中获取,这里用一个示例
TEST_IMAGE="jefzda/sweap-images:django__django-11099"

echo "  正在拉取: $TEST_IMAGE"
echo "  (如果失败,可能是这个tag不存在,需要从数据集中获取真实的tag)"
echo ""

if docker pull "$TEST_IMAGE" 2>&1; then
    echo ""
    echo "✓ 镜像拉取成功!"
    echo ""
    
    # 步骤3: 启动容器测试
    echo "步骤3: 启动容器并测试..."
    CONTAINER_NAME="swebench-test-$$"
    
    docker run -d \
        --name "$CONTAINER_NAME" \
        --platform linux/amd64 \
        "$TEST_IMAGE" \
        sleep infinity
    
    echo "✓ 容器已启动: $CONTAINER_NAME"
    echo ""
    
    # 等待容器完全启动
    sleep 2
    
    # 步骤4: 测试容器内的代码访问
    echo "步骤4: 测试容器内代码访问..."
    
    echo "  检查 /testbed 目录:"
    docker exec "$CONTAINER_NAME" ls -la /testbed/ | head -10
    echo ""
    
    echo "  检查Python文件数量:"
    docker exec "$CONTAINER_NAME" sh -c "find /testbed -name '*.py' -type f | wc -l"
    echo ""
    
    echo "  测试grep搜索:"
    docker exec "$CONTAINER_NAME" sh -c "grep -r 'def' /testbed --include='*.py' | head -5"
    echo ""
    
    echo "  测试文件读取:"
    docker exec "$CONTAINER_NAME" sh -c "find /testbed -name '*.py' -type f | head -1 | xargs head -20"
    echo ""
    
    # 步骤5: 清理
    echo "步骤5: 清理容器..."
    docker stop "$CONTAINER_NAME" >/dev/null
    docker rm "$CONTAINER_NAME" >/dev/null
    echo "✓ 容器已清理"
    echo ""
    
    echo "=========================================="
    echo "✓ 测试完成!"
    echo "=========================================="
    echo ""
    echo "镜像测试成功,可以继续完整评测流程"
    echo ""
    
else
    echo ""
    echo "⚠ 镜像拉取失败"
    echo ""
    echo "可能的原因:"
    echo "1. 镜像tag不存在 (需要从数据集中获取真实的tag)"
    echo "2. 网络问题 (Docker Hub访问受限)"
    echo "3. 需要Docker Hub登录"
    echo ""
    echo "解决方案:"
    echo "1. 先加载数据集,获取真实的dockerhub_tag"
    echo "2. 配置Docker Hub镜像加速"
    echo "3. 或直接运行完整的评测程序,它会自动处理"
    echo ""
fi
