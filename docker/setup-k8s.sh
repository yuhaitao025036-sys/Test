#!/bin/bash
# SWE-bench K8s 部署准备脚本

set -e

echo "=========================================="
echo "SWE-bench K8s 部署准备"
echo "=========================================="
echo ""

# 步骤1: 检查K8s集群
echo "步骤1: 检查K8s集群状态..."
if ! kubectl cluster-info &>/dev/null; then
    echo "✗ 无法连接到K8s集群"
    echo "  请确保:"
    echo "  1. K8s集群已启动 (minikube/kind/真实集群)"
    echo "  2. kubeconfig已正确配置"
    exit 1
fi
echo "✓ K8s集群连接正常"
kubectl get nodes
echo ""

# 步骤2: 检查必要的镜像
echo "步骤2: 检查Docker镜像..."
IMAGES=(
    "python:3.13-slim"
    "docker:27-dind"
)

for img in "${IMAGES[@]}"; do
    echo "  检查镜像: $img"
    if docker pull "$img" 2>/dev/null; then
        echo "  ✓ $img"
    else
        echo "  ⚠ 无法拉取 $img (将由K8s自动拉取)"
    fi
done
echo ""

# 步骤3: 检查数据集
echo "步骤3: 检查数据集..."
DATASET_PATHS=(
    "$HOME/datasets/SWE-bench_Pro/test-00000-of-00001.parquet"
    "$HOME/datasets/SWE-bench_Pro"
    "./datasets/SWE-bench_Pro/test-00000-of-00001.parquet"
)

DATASET_FOUND=""
for path in "${DATASET_PATHS[@]}"; do
    if [ -e "$path" ]; then
        DATASET_FOUND="$path"
        echo "✓ 找到数据集: $path"
        break
    fi
done

if [ -z "$DATASET_FOUND" ]; then
    echo "⚠ 未找到本地数据集"
    echo "  建议下载: https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro"
    echo "  或使用在线加载(需要网络)"
fi
echo ""

# 步骤4: 检查配置文件
echo "步骤4: 检查配置文件..."
CONFIG_FILE="$HOME/.experience.json"
if [ -f "$CONFIG_FILE" ]; then
    echo "✓ 找到配置文件: $CONFIG_FILE"
    # 检查是否包含API key
    if grep -q "YOUR_API_KEY_HERE" "$CONFIG_FILE" 2>/dev/null || \
       ! grep -q "api_key" "$CONFIG_FILE" 2>/dev/null; then
        echo "⚠ 配置文件可能需要更新API_KEY"
    fi
else
    echo "⚠ 未找到配置文件: $CONFIG_FILE"
    echo "  需要创建包含 raw_llm_api 配置的文件"
fi
echo ""

# 步骤5: 给出下一步建议
echo "=========================================="
echo "准备工作检查完成!"
echo "=========================================="
echo ""
echo "下一步操作:"
echo ""
echo "1. 更新 ConfigMap 中的 API_KEY:"
echo "   vim test/docker/k8s-swebench.yaml"
echo "   (修改第130行的 YOUR_API_KEY_HERE)"
echo ""
echo "2. 选择数据集方案:"
if [ -n "$DATASET_FOUND" ]; then
    echo "   方案A: 使用本地数据集 (推荐)"
    echo "   修改 k8s-swebench.yaml:"
    echo "   - 注释掉 92-93行 (PVC)"
    echo "   - 取消注释 95-97行 (hostPath)"
    echo "   - 将 path 改为: $DATASET_FOUND"
else
    echo "   需要下载数据集或创建PVC"
fi
echo ""
echo "3. 部署到K8s:"
echo "   kubectl apply -f test/docker/k8s-swebench.yaml"
echo ""
echo "4. 等待Pod启动:"
echo "   kubectl wait --for=condition=Ready pod/swebench-evaluator --timeout=300s"
echo ""
echo "5. 进入容器:"
echo "   kubectl exec -it swebench-evaluator -c evaluator -- bash"
echo ""
