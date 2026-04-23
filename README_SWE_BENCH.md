# SWE-bench Pro LLM 评测工具

基于 LLM API 的 SWE-bench Pro 评测工具，支持单任务模式和批量评测。

## 功能特点

- ✅ 单任务单次运行（避免Docker镜像堆积）
- ✅ 兼容 SWE-bench harness 标准格式
- ✅ 自动容器复用和清理
- ✅ 断点续传支持
- ✅ 详细的评测报告

## 快速开始

### 1. 配置 API

确保 `~/.experience.json` 包含以下配置：

```json
{
  "raw_llm_api": {
    "base_url": "https://oneapi-comate.baidu-int.com/v1",
    "api_key": "sk-...",
    "model": "MiniMax-M2.5"
  }
}
```

### 2. 单任务评测

```bash
# 通过索引运行
python test_llm_api.py --index 0

# 通过任务ID运行
python test_llm_api.py --instance-id django__django-12345

# 只生成patch，不验证（快速模式）
python test_llm_api.py --index 0 --no-validate
```

### 3. 批量评测

```bash
# 评测索引 0-9 的任务
./run_batch.sh 0 9

# 评测索引 10-49 的任务
./run_batch.sh 10 49
```

### 4. 查看结果分析

```bash
# 详细分析（含评分）
python test_llm_api.py --analysis

# 可视化分析（图表展示）
python visualize_results.py
```

## 输出文件结构

```
swe_bench_output/
├── predictions/              # SWE-bench harness 标准格式
│   ├── instance_001.json
│   ├── instance_002.json
│   └── ...
├── instance_001_full.json   # 完整结果（包含验证信息）
├── instance_002_full.json
├── all_results.jsonl        # 所有结果汇总
└── analysis_report.txt      # 分析报告
```

## 评测指标与打分

### ⚠️ 重要说明

**官方认可的指标**：只有 **Resolved 率** 是 SWE-bench 官方标准，用于学术论文和排行榜对比。

**本工具的评分系统**：是辅助性的内部分析工具，帮助你：
- 诊断系统哪个环节有问题
- 对比不同配置的效果
- 追踪改进方向

❌ **不要用于**：学术论文、公开对比、官方排行榜  
✅ **适用于**：内部调试、方案优化、问题定位

---

### 1. SWE-bench 官方标准指标 ⭐

**唯一被学术界和工业界公认的指标**：

| 指标 | 定义 | 用途 |
|------|------|------|
| **Resolved 率** | `已解决任务数 / 总任务数 × 100%` | 官方排行榜、论文对比 |

**业界水平参考**（SWE-bench Lite / Pro）：

| 方法/模型 | Resolved率 | 来源 |
|-----------|-----------|------|
| **Devin (Cognition AI)** | ~13.8% | SWE-bench 官方排行榜 |
| **SWE-agent + GPT-4** | ~12.5% | Princeton 论文 |
| **Aider + Claude-3.5** | ~18-20% | 社区报告（非官方）|
| **AutoCodeRover** | ~19-22% | arXiv 论文 |
| **Raw LLM (无agent)** | ~3-5% | 基线 |

> 数据来源：[SWE-bench 官方排行榜](https://www.swebench.com/) (截至 2024)

---

### 2. 本工具的辅助评分系统（非官方）

这是为了**内部调试和优化**设计的诊断工具，**不被学术界认可**：

| 维度 | 说明 | 用途 |
|------|------|------|
| Patch生成能力 | 生成patch数 / 总数 × 100 | 诊断 prompt 和模型问题 |
| 问题解决能力 | = Resolved 率 | 等同于官方指标 |
| Patch质量 | 解决数 / 验证数 × 100 | 诊断 patch 格式/逻辑问题 |
| 代码检索能力 | 有上下文数 / 总数 × 100 | 诊断检索策略问题 |
| 系统稳定性 | (总数 - 错误数) / 总数 × 100 | 诊断工程实现问题 |
| **综合评分** | 五维平均 | 快速了解整体情况 |

**⚠️ 注意**：
- 这些维度是我们自定义的，不是学术标准
- 仅用于内部对比（如：优化前 vs 优化后）
- 如果要发论文或公开对比，只用 **Resolved 率**

### 3. 示例输出说明

```
📊 核心指标 (SWE-bench 标准)
──────────────────────────────────────────────────────────────────────
  总任务数:        50
  生成Patch:       45/50 (90.0%)
  已验证:          45/50 (90.0%)
  ✓ 已解决:        18/45 (40.0%)
  ★ Resolved率:    36.0% ← 【唯一官方认可指标】用于论文/排行榜

🎯 评分系统 ← 【非官方，仅供内部参考】
──────────────────────────────────────────────────────────────────────
  Patch生成能力........... 90.0/100 ★★★★☆  ← 诊断工具
  问题解决能力........... 36.0/100 ★★☆☆☆  ← = Resolved率
  Patch质量............... 40.0/100 ★★☆☆☆  ← 诊断工具
  代码检索能力........... 88.0/100 ★★★★☆  ← 诊断工具
  系统稳定性............. 100.0/100 ★★★★★ ← 诊断工具
  ──────────────────────────────────────────────────────────────────────
  综合评分............... 70.8/100 ★★★★☆  ← 非标准指标

❌ 失败原因分析 (共 27 个) ← 【诊断工具，帮助定位问题】
──────────────────────────────────────────────────────────────────────
  Patch应用失败:   8 (29.6%)  ← 说明 patch 格式有问题
  测试未通过:      15 (55.6%) ← 说明逻辑修复不正确
  超时:            2 (7.4%)   ← 说明测试太慢
  其他错误:        2 (7.4%)
```

**如何使用这些数据**：

✅ **对外报告**（论文/分享）：
```
我们的方法在 SWE-bench Pro 上达到了 36.0% 的 Resolved 率
```

✅ **内部优化**：
```
- Patch生成率90%但解决率只36% → 重点优化 patch 质量
- 55.6%失败是测试未通过 → 需要改进代码理解和修复逻辑
- 代码检索88%说明检索策略较好 → 不是主要瓶颈
```

---

### 4. 官方评测方法

如果需要**官方认可的结果**，使用 SWE-bench 官方 harness：

```bash
# 1. 生成 predictions
python test_llm_api.py --index 0

# 2. 使用官方工具评测（需要安装 swebench）
python -m swebench.harness.run_evaluation \
    --predictions_path ./swe_bench_output/predictions \
    --swe_bench_tasks testbed \
    --log_dir ./logs

# 3. 官方工具会输出标准的 Resolved 率
```

**为什么要用官方工具**：
- ✅ 保证测试环境一致性
- ✅ 结果可被学术界认可
- ✅ 可与论文中的方法对比

---

## 与业界对比（仅 Resolved 率）

| 系统/方法 | Resolved率 | 发布时间 | 备注 |
|-----------|-----------|----------|------|
| **基线（无工具）** | 3-5% | - | 直接调用 LLM |
| **Devin** | 13.8% | 2024.03 | Cognition AI |
| **SWE-agent** | 12.5% | 2024.04 | Princeton |
| **AutoCodeRover** | 19-22% | 2024.04 | 结合检索和修复 |
| **本工具（示例）** | 取决于配置 | - | 需实际测试 |

> **数据来源**：
> - [SWE-bench 官方排行榜](https://www.swebench.com/)
> - 相关论文和技术报告
> - 社区测试结果

**⚠️ 注意**：
1. 不同版本数据集（Lite vs Pro）结果不同，不可直接对比
2. 官方排行榜会持续更新
3. 本工具的结果取决于使用的模型和配置

## 结果分析工具

### 1. 基础分析
```bash
python test_llm_api.py --analysis
```
输出：
- ✅ 核心指标统计
- 🎯 评分系统（5个维度 + 综合分）
- ❌ 失败原因分析
- 📝 代码上下文质量
- 📋 任务详情列表

生成文件：
- `analysis_report.txt` - 详细文本报告
- `analysis_report.json` - JSON格式报告（便于程序读取）

### 2. 可视化分析
```bash
python visualize_results.py
```
输出：
- 📈 任务完成情况分布（ASCII条形图）
- ❌ 失败原因分布
- 📝 代码上下文质量分布
- 🏆 困难任务 Top 10
- ✅ 成功解决的任务列表
- 📊 按项目统计

### 主要指标 (SWE-bench 标准)

- **Resolved 率**: 成功解决的任务数 / 总任务数
- **Patch 生成率**: 生成有效patch的任务数 / 总任务数



## 评测流程

每个任务的评测流程：

1. **加载数据集** - 从 HuggingFace 加载 SWE-bench Pro
2. **获取代码上下文** - 在 Docker 容器中 grep 搜索相关文件
3. **构建 Prompt** - 组合问题描述和代码上下文
4. **调用 LLM** - 生成修复 patch
5. **验证 Patch**（可选）
   - 应用 patch 到容器
   - 运行测试
   - 判断是否解决问题

## 命令行参数

### test_llm_api.py

```
--instance-id ID    指定任务ID
--index N           指定任务索引（从0开始）
--no-validate       跳过验证（只生成patch）
--output-dir DIR    输出目录（默认: ./swe_bench_output）
--analysis          分析已有结果
```

### run_batch.sh

```bash
./run_batch.sh [start_index] [end_index]
```

## 性能优化

- **容器复用**: 同一镜像的容器会被复用
- **Git reset**: 验证时通过 `git reset --hard` 恢复环境，无需重启容器
- **资源限制**: 容器限制内存 4GB，避免系统卡顿
- **自动清理**: 每个任务完成后清理退出的容器

## 注意事项

1. **Docker 镜像很大**（几GB），首次运行会拉取镜像
2. **每个任务独立运行**，避免长时间占用镜像
3. **验证模式较慢**（每个任务 2-5 分钟），可用 `--no-validate` 快速生成 patch
4. **断点续传**: 脚本会追加到 `all_results.jsonl`，已完成的任务不会重复

## 与官方 harness 对接

生成的 `predictions/` 目录可直接用于官方评测工具：

```bash
# 使用官方 harness 评测
python -m swebench.harness.run_evaluation \
    --predictions_path ./swe_bench_output/predictions \
    --swe_bench_tasks testbed \
    --log_dir ./logs
```

## 故障排查

### 问题: Docker 容器启动失败
```bash
# 检查 Docker 是否运行
docker ps

# 手动拉取镜像
docker pull jefzda/sweap-images:TAG
```

### 问题: API 调用失败
```bash
# 检查配置文件
cat ~/.experience.json

# 测试 API 连接
curl -X POST https://oneapi-comate.baidu-int.com/v1/chat/completions \
  -H "Authorization: Bearer sk-..." \
  -d '{"model":"MiniMax-M2.5","messages":[{"role":"user","content":"test"}]}'
```

### 问题: 内存不足
```bash
# 清理所有容器
docker system prune -a

# 限制并发任务数（修改批量脚本）
```

## 参考资料

**官方资源**：
- [SWE-bench 官方网站](https://www.swebench.com/) - 排行榜和数据集
- [SWE-bench GitHub](https://github.com/princeton-nlp/SWE-bench) - 代码和文档
- [SWE-bench 论文](https://arxiv.org/abs/2310.06770) - 原始论文

**相关论文**：
- SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering (2024)
- AutoCodeRover: Autonomous Program Improvement (2024)

**数据集说明**：
- SWE-bench Lite: ~300个任务，用于快速验证
- SWE-bench Pro: ~2,294个任务，用于完整评测
- 评测标准：运行测试套件，Pass→Pass 和 Fail→Pass






# 1. 生成 patch（不需要Docker）
python test/test_llm_api.py --index 0 --no-validate

# 2. 简化验证（只检查format，不需要Docker）
python test/verify_with_swebench.py
