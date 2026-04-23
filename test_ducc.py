import json
import docker
import openai
from datasets import load_dataset
from typing import Dict, List, Optional, Tuple
import os
import subprocess

# 配置
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MAX_TURNS = 50  # 最大交互轮数

class DUCCAgent:
    """
    DUCC Agent评估器
    核心特点：支持多轮工具调用，模型自主探索代码库
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.docker_client = docker.from_env()
        self.container = None
        
    # ============ 工具定义 ============
    
    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "search_code",
                "description": "在代码库中搜索关键词或正则表达式。返回匹配的文件路径和上下文。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词或正则表达式，如 'validate_username' 或 'UnicodeDecodeError'"
                        },
                        "file_pattern": {
                            "type": "string",
                            "description": "限定搜索的文件类型，如 '*.py' 或 '*.js'，默认为所有文件"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "最大返回结果数，默认10"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取指定文件的完整内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "相对于代码库根目录的文件路径，如 'src/auth/user.py'"
                        },
                        "start_line": {
                            "type": "integer",
                            "description": "开始行号（可选），不指定则从第1行开始"
                        },
                        "end_line": {
                            "type": "integer",
                            "description": "结束行号（可选），不指定则读到文件末尾"
                        }
                    },
                    "required": ["file_path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "列出目录下的文件和子目录。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "目录路径，默认为代码库根目录 '/'"
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "是否递归列出子目录，默认False"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_test",
                "description": "运行特定的测试用例，验证修复是否有效。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "test_pattern": {
                            "type": "string",
                            "description": "测试名称或模式，如 'test_unicode_username'"
                        },
                        "test_file": {
                            "type": "string",
                            "description": "测试文件路径（可选）"
                        }
                    },
                    "required": ["test_pattern"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "submit_patch",
                "description": "提交最终的修复patch。调用此工具后任务结束。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patch": {
                            "type": "string",
                            "description": "unified diff格式的patch内容"
                        },
                        "explanation": {
                            "type": "string",
                            "description": "修复说明（可选）"
                        }
                    },
                    "required": ["patch"]
                }
            }
        }
    ]
    
    # ============ 工具实现 ============
    
    def _search_code(self, query: str, file_pattern: str = "", max_results: int = 10) -> str:
        """在容器中搜索代码"""
        if not self.container:
            return "Error: Container not initialized"
        
        # 构建grep命令
        pattern_arg = f"--include='{file_pattern}'" if file_pattern else ""
        cmd = f"grep -r -n {pattern_arg} '{query}' /testbed 2>/dev/null | head -{max_results}"
        
        result = self.container.exec_run(cmd)
        output = result.output.decode()
        
        if not output.strip():
            return f"No results found for '{query}'"
        
        return output
    
    def _read_file(self, file_path: str, start_line: int = None, end_line: int = None) -> str:
        """读取容器中的文件"""
        if not self.container:
            return "Error: Container not initialized"
        
        if start_line and end_line:
            cmd = f"sed -n '{start_line},{end_line}p' /testbed/{file_path}"
        elif start_line:
            cmd = f"tail -n +{start_line} /testbed/{file_path}"
        else:
            cmd = f"cat /testbed/{file_path}"
        
        result = self.container.exec_run(cmd)
        output = result.output.decode()
        
        if result.exit_code != 0:
            return f"Error reading file: {output}"
        
        return output
    
    def _list_directory(self, path: str = "/", recursive: bool = False) -> str:
        """列出容器中的目录"""
        if not self.container:
            return "Error: Container not initialized"
        
        if recursive:
            cmd = f"find /testbed{path} -type f 2>/dev/null | head -100"
        else:
            cmd = f"ls -la /testbed{path} 2>/dev/null"
        
        result = self.container.exec_run(cmd)
        return result.output.decode()
    
    def _run_test(self, test_pattern: str, test_file: str = "") -> str:
        """在容器中运行测试"""
        if not self.container:
            return "Error: Container not initialized"
        
        # 根据仓库类型选择测试命令
        # 这里简化处理，实际需要根据具体项目调整
        if test_file:
            cmd = f"cd /testbed && python -m pytest {test_file} -k '{test_pattern}' -v 2>&1 | tail -50"
        else:
            cmd = f"cd /testbed && python -m pytest -k '{test_pattern}' -v 2>&1 | tail -50"
        
        result = self.container.exec_run(cmd)
        return result.output.decode()
    
    def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """执行工具调用"""
        if tool_name == "search_code":
            return self._search_code(
                arguments.get("query", ""),
                arguments.get("file_pattern", ""),
                arguments.get("max_results", 10)
            )
        elif tool_name == "read_file":
            return self._read_file(
                arguments.get("file_path", ""),
                arguments.get("start_line"),
                arguments.get("end_line")
            )
        elif tool_name == "list_directory":
            return self._list_directory(
                arguments.get("path", "/"),
                arguments.get("recursive", False)
            )
        elif tool_name == "run_test":
            return self._run_test(
                arguments.get("test_pattern", ""),
                arguments.get("test_file", "")
            )
        elif tool_name == "submit_patch":
            # 返回特殊标记，表示任务完成
            return "PATCH_SUBMITTED"
        else:
            return f"Unknown tool: {tool_name}"
    
    # ============ Agent核心循环 ============
    
    def _build_system_prompt(self, instance: Dict) -> str:
        """构建系统提示词"""
        # 构建需求文本
        requirements_text = ""
        if instance.get('requirements'):
            requirements_text = f"\n## Requirements\n{instance['requirements']}\n"
        
        interface_text = ""
        if instance.get('interface'):
            interface_text = f"\n## Interface Specification\n{instance['interface']}\n"
        
        return f"""You are a software engineer agent. Your task is to fix a bug in the codebase.

## Task Description
{instance['problem_statement']}
{requirements_text}
{interface_text}

## Environment
- The codebase is located at `/testbed` in the container
- You have access to the following tools:
  1. `search_code`: Search for keywords in the codebase
  2. `read_file`: Read file contents
  3. `list_directory`: List directory structure
  4. `run_test`: Run tests to verify your fix
  5. `submit_patch`: Submit your final patch

## Workflow
1. First, explore the codebase to understand the issue
2. Search for relevant functions/classes
3. Read files to understand the logic
4. Identify the root cause
5. Generate a fix
6. Run tests to verify
7. Submit the final patch

## Important
- Each tool call returns a result. Use it to inform your next action
- You can call tools multiple times
- Only call `submit_patch` when you are confident in your fix
- Your patch must be in unified diff format

## Output Format for submit_patch
```diff
diff --git a/path/to/file.py b/path/to/file.py
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -line,count +line,count @@
 context
+added line
-removed line