#!/bin/bash
# SWE-bench 在 K8s 上的部署和运行脚本

set -e

# 配置
POD_NAME="swebench-evaluator"
NAMESPACE="default"  # 修改为你的命名空间

echo "=========================================="
echo "SWE-bench K8s 部署脚本"
echo "=========================================="

# 1. 创建 Pod
echo ""
echo "步骤 1: 部署 Pod..."
kubectl apply -f k8s-swebench.yaml -n $NAMESPACE

# 2. 等待 Pod 就绪
echo ""
echo "步骤 2: 等待 Pod 启动..."
kubectl wait --for=condition=Ready pod/$POD_NAME -n $NAMESPACE --timeout=300s

# 3. 安装依赖
echo ""
echo "步骤 3: 安装依赖..."
kubectl exec -n $NAMESPACE $POD_NAME -c evaluator -- bash -c "
    apt-get update && apt-get install -y git curl docker.io
    pip install --no-cache-dir docker openai datasets requests swebench
"

# 4. 上传代码和配置
echo ""
echo "步骤 4: 上传代码..."
kubectl cp test/ $NAMESPACE/$POD_NAME:/workspace/test/ -c evaluator
kubectl cp ~/.experience.json $NAMESPACE/$POD_NAME:/root/.experience.json -c evaluator

# 5. 预拉取镜像（可选，加速后续测试）
echo ""
echo "步骤 5: 预拉取 Docker 镜像（可选，按 Ctrl+C 跳过）..."
echo "提示: 这会下载 3-5GB，可以跳过让测试时自动拉取"
read -p "是否预拉取镜像? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    kubectl exec -n $NAMESPACE $POD_NAME -c evaluator -- bash -c "
        docker pull jefzda/sweap-images:nodebb.nodebb-NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5
    "
fi

# 6. 运行测试
echo ""
echo "步骤 6: 开始测试..."
echo "运行命令: python test/test_llm_api.py --index 0"
kubectl exec -n $NAMESPACE $POD_NAME -c evaluator -it -- bash -c "
    cd /workspace && python test/test_llm_api.py --index 0
"

# 7. 下载结果
echo ""
echo "步骤 7: 下载结果..."
mkdir -p ./swe_bench_output
kubectl cp $NAMESPACE/$POD_NAME:/workspace/swe_bench_output ./swe_bench_output -c evaluator

echo ""
echo "=========================================="
echo "✓ 完成！结果已保存到 ./swe_bench_output"
echo "=========================================="
echo ""
echo "其他命令:"
echo "  # 进入 Pod"
echo "  kubectl exec -n $NAMESPACE $POD_NAME -c evaluator -it -- bash"
echo ""
echo "  # 查看日志"
echo "  kubectl logs -n $NAMESPACE $POD_NAME -c evaluator"
echo ""
echo "  # 删除 Pod"
echo "  kubectl delete pod $POD_NAME -n $NAMESPACE"
