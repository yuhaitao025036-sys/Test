#!/bin/bash
# 下载 HuggingFace SWE-bench Pro 数据集

set -e

OUTPUT_DIR="${HOME}/datasets/SWE-bench_Pro"
FILE_URL="https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro/resolve/main/test-00000-of-00001.parquet"
OUTPUT_FILE="${OUTPUT_DIR}/test-00000-of-00001.parquet"

echo "========================================================================"
echo "HuggingFace SWE-bench Pro 数据集下载工具"
echo "========================================================================"
echo ""
echo "目标: ${FILE_URL}"
echo "保存到: ${OUTPUT_FILE}"
echo ""

# 创建输出目录
mkdir -p "${OUTPUT_DIR}"

# 尝试 curl（最推荐）
echo "尝试方式 1: curl（支持断点续传）"
if command -v curl &> /dev/null; then
    echo "正在下载..."
    if curl -L -C - -o "${OUTPUT_FILE}" "${FILE_URL}" 2>/dev/null; then
        echo "✓ 下载完成！"
        echo ""
        echo "下一步：运行评测"
        echo "  LOCAL_DATASET_PATH=${OUTPUT_FILE} python test/test_llm_api.py --index 0 --no-validate"
        echo ""
        exit 0
    fi
fi

# 尝试 wget
echo ""
echo "尝试方式 2: wget"
if command -v wget &> /dev/null; then
    echo "正在下载..."
    if wget -c -O "${OUTPUT_FILE}" "${FILE_URL}" 2>/dev/null; then
        echo "✓ 下载完成！"
        echo ""
        echo "下一步：运行评测"
        echo "  LOCAL_DATASET_PATH=${OUTPUT_FILE} python test/test_llm_api.py --index 0 --no-validate"
        echo ""
        exit 0
    fi
fi

# 尝试 Python requests
echo ""
echo "尝试方式 3: Python requests"
if command -v python3 &> /dev/null; then
    python3 << 'PYTHON_SCRIPT'
import requests
import sys
from pathlib import Path

url = "https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro/resolve/main/test-00000-of-00001.parquet"
output_file = Path.home() / "datasets" / "SWE-bench_Pro" / "test-00000-of-00001.parquet"

try:
    print("正在下载...")
    response = requests.get(url, stream=True, timeout=300, allow_redirects=True)
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0
    
    with open(output_file, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    percent = (downloaded / total_size) * 100
                    print(f"\r进度: {downloaded / 1024 / 1024:.1f}MB ({percent:.1f}%)", end='', flush=True)
    
    print("\n✓ 下载完成！")
    sys.exit(0)
except Exception as e:
    print(f"✗ 下载失败: {e}")
    sys.exit(1)
PYTHON_SCRIPT
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "下一步：运行评测"
        echo "  LOCAL_DATASET_PATH=${OUTPUT_FILE} python test/test_llm_api.py --index 0 --no-validate"
        echo ""
        exit 0
    fi
fi

echo ""
echo "========================================================================"
echo "✗ 所有下载方式都失败了"
echo "========================================================================"
echo ""
echo "💡 解决方案："
echo "1. 手动下载："
echo "   - 访问: https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro"
echo "   - 点击 'Files' 标签"
echo "   - 下载 'test-00000-of-00001.parquet'"
echo ""
echo "2. 配置代理后重试："
echo "   export HTTP_PROXY=http://proxy:8080"
echo "   export HTTPS_PROXY=http://proxy:8080"
echo "   bash download_dataset.sh"
echo ""
echo "3. 使用 Python 脚本："
echo "   python download_dataset.py"
echo ""
exit 1
