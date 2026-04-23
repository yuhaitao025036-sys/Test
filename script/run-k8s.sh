#!/bin/bash
# 快速在 K8s 上运行 SWE-bench 评测

set -e

POD_NAME="swebench-evaluator"
NAMESPACE="${NAMESPACE:-default}"

echo "=========================================="
echo "SWE-bench K8s 快速运行"
echo "=========================================="

# 检查 Pod 是否存在
if kubectl get pod $POD_NAME -n $NAMESPACE &>/dev/null; then
    echo "✓ Pod 已存在"
else
    echo "✗ Pod 不存在，请先运行: ./deploy-k8s.sh"
    exit 1
fi

# 检查 Pod 状态
POD_STATUS=$(kubectl get pod $POD_NAME -n $NAMESPACE -o jsonpath='{.status.phase}')
if [ "$POD_STATUS" != "Running" ]; then
    echo "✗ Pod 状态异常: $POD_STATUS"
    exit 1
fi

echo "✓ Pod 运行中"
echo ""

# 允许传入参数
INDEX="${1:-0}"
VALIDATE="${2:-yes}"

if [ "$VALIDATE" = "no" ]; then
    VALIDATE_FLAG="--no-validate"
else
    VALIDATE_FLAG=""
fi

echo "运行参数:"
echo "  - 任务索引: $INDEX"
echo "  - 验证模式: $([ -z "$VALIDATE_FLAG" ] && echo '启用' || echo '禁用')"
echo ""

# 运行测试
echo "开始测试..."
kubectl exec -n $NAMESPACE $POD_NAME -c evaluator -it -- bash -c "
    cd /workspace && python test/test_llm_api.py --index $INDEX $VALIDATE_FLAG
"

# 下载结果
echo ""
echo "下载结果..."
mkdir -p ./swe_bench_output
kubectl cp $NAMESPACE/$POD_NAME:/workspace/swe_bench_output ./swe_bench_output -c evaluator

echo ""
echo "=========================================="
echo "✓ 完成！结果已保存到 ./swe_bench_output"
echo "=========================================="
