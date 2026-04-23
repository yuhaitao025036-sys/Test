# HuggingFace 数据集下载指南

网页可以访问但 `wget` 无法下载的原因通常是：

1. **HuggingFace CDN 的地域限制** - 对直接下载链接有限制
2. **需要特殊请求头** - 网页浏览器自动添加但命令行工具不会
3. **重定向处理** - wget 可能无法正确处理 HuggingFace 的重定向

## 快速下载

### 方法 1：使用 Python 脚本（推荐）

```bash
cd test
python download_dataset.py
```

这个脚本会自动尝试多种下载方式，直到成功为止。

### 方法 2：使用 Bash 脚本

```bash
cd test
bash download_dataset.sh
```

### 方法 3：使用诊断工具检查网络

```bash
cd test
python diagnose_network.py
```

这个工具会诊断网络连接问题并给出具体建议。

## 手动下载

如果自动脚本都失败了，可以手动下载：

1. 访问：https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro
2. 点击 **Files** 标签
3. 找到 `test-00000-of-00001.parquet` 文件
4. 点击文件右边的下载按钮（或三点菜单 → Download）
5. 下载后移动到 `~/datasets/SWE-bench_Pro/` 目录

## 使用离线数据集

下载完成后，运行评测：

```bash
# 方式 A：使用环境变量（推荐）
export LOCAL_DATASET_PATH=~/datasets/SWE-bench_Pro/test-00000-of-00001.parquet
python test_llm_api.py --index 0 --no-validate

# 方式 B：一行命令
LOCAL_DATASET_PATH=~/datasets/SWE-bench_Pro/test-00000-of-00001.parquet python test_llm_api.py --index 0 --no-validate

# 方式 C：使用目录
LOCAL_DATASET_PATH=~/datasets/SWE-bench_Pro python test_llm_api.py --index 0 --no-validate
```

## 网络配置

如果有代理，可以配置后再下载：

```bash
# 配置代理
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080

# 再运行下载脚本
python download_dataset.py
```

## 使用 `huggingface_hub` 库下载

如果安装了 `huggingface_hub` 库，可以直接用：

```bash
pip install huggingface_hub
```

然后 `download_dataset.py` 会自动使用这个库（最可靠）。

## 使用 Git LFS 克隆整个仓库

如果网络较好且想要完整的仓库：

```bash
# 安装 git-lfs
# macOS:
brew install git-lfs

# 克隆仓库
git lfs install
git clone https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro ~/datasets/SWE-bench_Pro

# 使用
LOCAL_DATASET_PATH=~/datasets/SWE-bench_Pro python test_llm_api.py --index 0 --no-validate
```

## 常见问题

### Q: 为什么网页可以访问但 wget 不行？

A: HuggingFace 使用了 CDN 和重定向机制，简单的 wget 无法正确处理。使用 Python 脚本会自动添加必要的请求头和处理重定向。

### Q: 下载很慢？

A: 
1. 尝试配置代理
2. 在网络较好的时段下载
3. 使用 `curl -C -` 支持断点续传
4. 等待一段时间后重试

### Q: 下载中断了怎么办？

A: Python 脚本和 curl 都支持断点续传，再次运行相同命令会从中断处继续下载。

### Q: 能用其他镜像吗？

A: 目前没有 SWE-bench Pro 的官方镜像，但可以：
1. 在网络较好的机器上下载后转移
2. 联系 ScaleAI 获取直接下载链接
3. 等待官方提供镜像服务

## 支持的离线数据格式

脚本支持以下格式的离线数据集：

| 格式 | 说明 |
|------|------|
| `.parquet` | HuggingFace 标准格式（推荐） |
| `.json` | JSON 数组格式 |
| `.pkl`/`.pickle` | Python pickle 格式 |
| 目录 | HuggingFace 数据集目录 |

## 获取帮助

运行诊断工具：

```bash
python diagnose_network.py
```

这会显示详细的网络连接信息和建议。
