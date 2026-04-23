#!/bin/bash
# 诊断容器启动问题

IMAGE="jefzda/sweap-images:nodebb.nodebb-NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5"

echo "=========================================="
echo "诊断容器启动问题"
echo "=========================================="
echo ""

echo "1. 检查镜像是否存在..."
if docker inspect "$IMAGE" &>/dev/null; then
    echo "✓ 镜像存在"
else
    echo "✗ 镜像不存在"
    exit 1
fi
echo ""

echo "2. 尝试不同的启动方式..."
echo ""

echo "方式1: 使用默认命令"
docker run -d --name test1 "$IMAGE" && echo "✓ 成功" || echo "✗ 失败"
sleep 2
docker ps -a | grep test1
docker logs test1 2>&1 | head -20
docker rm -f test1 &>/dev/null
echo ""

echo "方式2: 使用 sleep infinity"
docker run -d --name test2 "$IMAGE" sleep infinity && echo "✓ 成功" || echo "✗ 失败"
sleep 2
docker ps -a | grep test2
docker logs test2 2>&1 | head -20
docker rm -f test2 &>/dev/null
echo ""

echo "方式3: 覆盖entrypoint + sleep"
docker run -d --name test3 --entrypoint "" "$IMAGE" sleep infinity && echo "✓ 成功" || echo "✗ 失败"
sleep 2
docker ps -a | grep test3
docker logs test3 2>&1 | head -20
docker rm -f test3 &>/dev/null
echo ""

echo "方式4: 使用 sh -c"
docker run -d --name test4 "$IMAGE" sh -c 'sleep infinity' && echo "✓ 成功" || echo "✗ 失败"
sleep 2
docker ps -a | grep test4
docker logs test4 2>&1 | head -20
docker rm -f test4 &>/dev/null
echo ""

echo "=========================================="
echo "诊断完成"
echo "=========================================="
