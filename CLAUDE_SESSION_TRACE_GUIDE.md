# Claude Session 轨迹一对一保存功能

## 功能说明

现在每个任务执行后，会自动将 Claude/ducc 的完整 session 轨迹复制到任务目录中，实现**一对一的轨迹保存**。

## 文件结构

运行任务后，每个任务目录下会包含以下 Claude session 相关文件：

```
./swe_bench_output_ducc/tasks/<instance_id>/
├── claude_session.jsonl          # ✨ 完整的 Claude session 轨迹
├── claude_session_info.json      # ✨ Session 元信息（原始路径等）
├── claude_session_summary.txt    # ✨ Session 摘要（事件统计）
├── ducc_execution.log            # ducc stdout/stderr
├── ducc_debug.log                # ducc debug 日志
├── ducc_raw_output.txt           # ducc 原始输出
├── extracted_patch.diff          # 提取的 patch
├── prompt.txt                    # 发送的 prompt
├── dataset_info.json             # 数据集信息
├── validation_result.json        # 验证结果
├── task_summary.json             # 任务摘要
└── README.txt                    # 文本摘要（含查看命令）
```

## Claude Session 轨迹文件说明

### 1. `claude_session.jsonl`

完整的 Claude/ducc session 轨迹，JSON Lines 格式（每行一个 JSON 对象）。

**包含的信息：**
- ✅ 用户输入（user messages）
- ✅ AI 回复（assistant messages）
- ✅ AI 思考过程（thinking）
- ✅ 所有工具调用（tool_use）：Read/Edit/Write/Bash
- ✅ 工具执行结果（tool_result）
- ✅ 时间戳和元数据

**事件类型：**
```json
{"type":"user","timestamp":...,"content":"用户输入"}
{"type":"thinking","timestamp":...,"content":"AI的思考过程"}
{"type":"tool_use","timestamp":...,"tool":"Read","path":"file.py"}
{"type":"tool_result","timestamp":...,"result":"执行结果"}
{"type":"assistant","timestamp":...,"content":"AI回复"}
```

### 2. `claude_session_info.json`

Session 的元信息：

```json
{
  "original_path": "~/.claude/projects/.../xxx.jsonl",
  "project_dir": "~/.claude/projects/...",
  "modified_time": "2026-04-27 11:30:45",
  "file_size_bytes": 123456,
  "workspace": "/tmp/workspace"
}
```

### 3. `claude_session_summary.txt`

可读的 session 摘要，包含：
- 总事件数
- 各类事件统计（user/assistant/tool_use/thinking 等）
- 常用查看命令

## 查看和分析 Session 轨迹

### 基本查看

```bash
# 进入任务目录
cd ./swe_bench_output_ducc/tasks/<instance_id>/

# 查看摘要
cat claude_session_summary.txt

# 查看完整轨迹（需要 jq）
cat claude_session.jsonl | jq

# 查看轨迹（不需要 jq）
cat claude_session.jsonl | python -m json.tool
```

### 统计分析

```bash
# 查看事件类型统计
cat claude_session.jsonl | jq -r '.type' | sort | uniq -c

# 统计工具调用次数
cat claude_session.jsonl | jq -r 'select(.type=="tool_use") | .tool' | sort | uniq -c

# 计算总事件数
cat claude_session.jsonl | wc -l
```

### 过滤特定事件

```bash
# 只看用户输入
cat claude_session.jsonl | jq 'select(.type=="user")'

# 只看 AI 回复
cat claude_session.jsonl | jq 'select(.type=="assistant")'

# 只看 AI 思考过程
cat claude_session.jsonl | jq -r 'select(.type=="thinking") | .content'

# 只看工具调用
cat claude_session.jsonl | jq 'select(.type=="tool_use")'

# 只看 Read 操作
cat claude_session.jsonl | jq 'select(.type=="tool_use" and .tool=="Read")'

# 只看 Edit 操作
cat claude_session.jsonl | jq 'select(.type=="tool_use" and .tool=="Edit")'
```

### 查看时间线

```bash
# 查看事件时间线
cat claude_session.jsonl | jq -r '{type: .type, time: .timestamp}'

# 查看工具调用时间线
cat claude_session.jsonl | jq -r 'select(.type=="tool_use") | {tool: .tool, time: .timestamp, path: .path}'
```

### 调试和分析

```bash
# 查看文件读取操作
cat claude_session.jsonl | jq 'select(.type=="tool_use" and .tool=="Read") | .path'

# 查看文件编辑操作
cat claude_session.jsonl | jq 'select(.type=="tool_use" and .tool=="Edit") | {path: .path, edits: .edits}'

# 查看失败的工具调用
cat claude_session.jsonl | jq 'select(.type=="tool_result" and .is_error==true)'

# 查看 AI 的完整思考链
cat claude_session.jsonl | jq -r 'select(.type=="thinking" or .type=="assistant") | "\(.type): \(.content[0:100])"'
```

## 批量分析

### 统计所有任务的工具使用

```bash
# 统计所有任务的工具调用
for task in ./swe_bench_output_ducc/tasks/*/; do
    echo "=== $(basename $task) ==="
    cat "$task/claude_session.jsonl" | jq -r 'select(.type=="tool_use") | .tool' | sort | uniq -c 2>/dev/null
done
```

### 找出最复杂的任务

```bash
# 按 session 文件大小排序
ls -lhS ./swe_bench_output_ducc/tasks/*/claude_session.jsonl | head -10

# 按事件数排序
for task in ./swe_bench_output_ducc/tasks/*/; do
    count=$(cat "$task/claude_session.jsonl" | wc -l 2>/dev/null)
    echo "$count $task"
done | sort -rn | head -10
```

### 找出失败的任务

```bash
# 查找包含错误的 session
for task in ./swe_bench_output_ducc/tasks/*/; do
    errors=$(cat "$task/claude_session.jsonl" 2>/dev/null | jq 'select(.type=="tool_result" and .is_error==true)' | wc -l)
    if [ $errors -gt 0 ]; then
        echo "[$errors errors] $task"
    fi
done
```

## Python 脚本分析示例

```python
import json
from pathlib import Path
from collections import Counter

def analyze_session(session_file):
    """分析单个 session 文件"""
    events = []
    with open(session_file, 'r') as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except:
                continue
    
    # 统计事件类型
    event_types = Counter(e['type'] for e in events)
    
    # 统计工具使用
    tools = Counter(e['tool'] for e in events if e.get('type') == 'tool_use')
    
    # 统计文件操作
    files = set(e.get('path') for e in events if e.get('type') == 'tool_use' and e.get('path'))
    
    return {
        'total_events': len(events),
        'event_types': dict(event_types),
        'tools': dict(tools),
        'files_touched': list(files),
        'num_files': len(files),
    }

# 使用示例
session_file = './swe_bench_output_ducc/tasks/repo__issue-123/claude_session.jsonl'
result = analyze_session(session_file)
print(json.dumps(result, indent=2))
```

## 对比不同任务的执行过程

```python
import json
from pathlib import Path

def compare_sessions(session1, session2):
    """对比两个 session 的执行差异"""
    def load_events(path):
        events = []
        with open(path, 'r') as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except:
                    continue
        return events
    
    events1 = load_events(session1)
    events2 = load_events(session2)
    
    # 对比工具调用序列
    tools1 = [e['tool'] for e in events1 if e.get('type') == 'tool_use']
    tools2 = [e['tool'] for e in events2 if e.get('type') == 'tool_use']
    
    print(f"Session 1: {len(tools1)} tool calls - {tools1}")
    print(f"Session 2: {len(tools2)} tool calls - {tools2}")
    
    # 对比文件操作
    files1 = set(e.get('path') for e in events1 if e.get('type') == 'tool_use' and e.get('path'))
    files2 = set(e.get('path') for e in events2 if e.get('type') == 'tool_use' and e.get('path'))
    
    print(f"\nFiles only in session 1: {files1 - files2}")
    print(f"Files only in session 2: {files2 - files1}")
    print(f"Common files: {files1 & files2}")
```

## 注意事项

1. **Session 匹配逻辑**
   - 通过时间范围匹配（任务开始前5分钟到结束后1分钟）
   - 如果有多个匹配的 session，选择最新的一个
   - 如果没有找到匹配的 session，会打印警告信息

2. **文件大小**
   - Session 文件大小通常在 10KB - 500KB
   - 复杂任务可能达到 1-2MB
   - 100个任务约占用 10-50MB 磁盘空间

3. **原始轨迹保留**
   - 复制到任务目录的是**副本**
   - 原始 session 仍保留在 `~/.claude/projects/`
   - 两者内容完全相同

## 故障排查

### 问题 1: 未找到 Claude session

```
⚠️ 未找到对应的 Claude session（时间范围: ...）
```

**原因：**
- Claude projects 目录不存在
- Session 保存被禁用
- 时间匹配失败

**解决：**
```bash
# 检查 Claude 目录
ls -la ~/.claude/projects/

# 检查最近的 session
find ~/.claude/projects/ -name "*.jsonl" -mtime -1 -ls

# 手动查找 session
# (根据时间和工作目录匹配)
```

### 问题 2: Session 文件为空

**检查原始 session：**
```bash
# 查看原始 session
cat ~/.claude/projects/.../xxx.jsonl

# 如果原始 session 也为空，说明 ducc 未保存轨迹
```

### 问题 3: jq 命令不可用

**安装 jq：**
```bash
# macOS
brew install jq

# Linux
sudo apt-get install jq  # Ubuntu/Debian
sudo yum install jq      # CentOS/RHEL

# 或使用 python 代替
cat claude_session.jsonl | python -m json.tool
```

## 总结

✅ **每个任务都有完整的、一对一对应的 Claude session 轨迹**

**优点：**
- 🎯 轨迹和任务一对一，不会混淆
- 📦 所有文件集中在任务目录，便于管理
- 🔍 可深入分析 AI 的决策过程
- 📊 便于批量分析和统计
- 🐛 便于调试和复现问题

现在你可以完整追踪每个任务的执行过程了！🚀
