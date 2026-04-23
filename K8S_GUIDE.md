# SWE-bench K8s 部署指南

## 前提条件

1. K8s 集群访问权限
2. `kubectl` 已配置
3. 数据集已准备好（parquet 文件）
4. API key 已准备

## 部署步骤

### 1. 修改配置

编辑 `test/docker/k8s-swebench.yaml`:

```yaml
# 修改 ConfigMap 中的 API key
data:
  experience.json: |
    {
      "raw_llm_api": {
        "api_key": "YOUR_ACTUAL_API_KEY",  # ← 改这里
        "base_url": "https://oneapi-comate.baidu-int.com/v1",
        "model": "MiniMax-M2.5"
      }
    }

# 修改数据集路径（如果使用 hostPath）
volumes:
  - name: dataset
    hostPath:
      path: /path/to/your/dataset  # ← 改这里
      type: Directory
```

### 2. 部署 Pod

```bash
cd test/script
./deploy-k8s.sh
```

这会自动：
- 创建 Pod
- 安装依赖
- 上传代码
- 等待就绪

### 3. 运行测试

**方式 A：自动化脚本**
```bash
# 测试索引 0，启用验证
./run-k8s.sh 0

# 测试索引 1，禁用验证
./run-k8s.sh 1 no
```

**方式 B：手动执行**
```bash
# 进入 Pod
kubectl exec -it swebench-evaluator -c evaluator -- bash

# 运行测试
cd /workspace
python test/test_llm_api.py --index 0

# 退出
exit
```

### 4. 下载结果

```bash
kubectl cp swebench-evaluator:/workspace/swe_bench_output ./swe_bench_output -c evaluator
```

## 重要配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LOCAL_DATASET_PATH` | 数据集路径 | `/datasets/SWE-bench_Pro/test-00000-of-00001.parquet` |
| `CONFIG_PATH` | 配置文件路径 | `/config/experience.json` |
| `DOCKER_HOST` | Docker 连接地址 | `tcp://localhost:2375` (DinD) |

### Docker 模式选择

**选项 1：Docker-in-Docker (DinD)** - 推荐
- 需要 `privileged: true`
- 容器独立，互不影响
- 配置：`DOCKER_HOST=tcp://localhost:2375`

**选项 2：宿主 Docker Socket**
- 挂载 `/var/run/docker.sock`
- 容器共享宿主 Docker
- 配置：`DOCKER_HOST=unix:///var/run/docker.sock`

当前 YAML 配置的是 DinD 模式。

### 资源需求

- **CPU**: 4-8 核
- **内存**: 8-16 GB
- **存储**: 50-100 GB（Docker 镜像）

## 常见问题

### 1. Pod 启动失败

```bash
# 查看日志
kubectl logs swebench-evaluator -c evaluator
kubectl logs swebench-evaluator -c docker-daemon

# 查看事件
kubectl describe pod swebench-evaluator
```

### 2. Docker 连接失败

检查 DinD sidecar 是否运行：
```bash
kubectl logs swebench-evaluator -c docker-daemon
```

### 3. 数据集加载失败

检查挂载：
```bash
kubectl exec swebench-evaluator -c evaluator -- ls -la /datasets
```

### 4. 权限问题

DinD 需要特权模式：
```yaml
securityContext:
  privileged: true  # 必须为 true
```

## 清理

```bash
# 删除 Pod
kubectl delete pod swebench-evaluator

# 清理 PVC（可选）
kubectl delete pvc swebench-dataset-pvc
```

## 批量测试

```bash
# 测试前 10 个任务
for i in {0..9}; do
    ./run-k8s.sh $i no  # 只生成 patch，不验证
done

# 验证所有 patch
./run-k8s.sh 0  # 任意一个即可，会自动验证所有
```
