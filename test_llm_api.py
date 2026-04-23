import json
import docker
import openai
from datasets import load_dataset
from typing import Dict, List, Optional
import os
import re
import time
import shlex
import tempfile

# 配置
# K8s 环境下从环境变量读取配置文件路径
CONFIG_PATH = os.environ.get('CONFIG_PATH', os.path.expanduser("~/.experience.json"))
DATASET_NAME = "ScaleAI/SWE-bench_Pro"
MAX_FILES_TO_INCLUDE = 10
MAX_LINES_PER_FILE = 300
CONTAINER_TIMEOUT = 300  # 容器操作超时时间(秒)
ENABLE_VALIDATION = True  # 是否启用验证（耗时）
HF_CACHE_DIR = os.path.expanduser("~/.cache/huggingface/datasets")  # HuggingFace 官方缓存目录

# Docker 连接配置（K8s DinD 支持）
DOCKER_HOST = os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock')

# 本地数据集路径 - 优先级：环境变量 > 自动检测 > 默认位置
LOCAL_DATASET_PATH = os.environ.get('LOCAL_DATASET_PATH', None)

# 如果未指定，自动检测常见位置
if not LOCAL_DATASET_PATH:
    possible_paths = [
        os.path.expanduser("~/datasets/SWE-bench_Pro/test-00000-of-00001.parquet"),
        os.path.expanduser("~/datasets/SWE-bench_Pro"),
        os.path.expanduser("~/SWE-bench_Pro"),
        "./datasets/SWE-bench_Pro/test-00000-of-00001.parquet",
        "./datasets/SWE-bench_Pro",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            LOCAL_DATASET_PATH = path
            print(f"✓ 自动检测到本地数据集: {path}")
            break

# 代理配置（可选）
# 支持环境变量或直接配置
HTTP_PROXY = os.environ.get('HTTP_PROXY', os.environ.get('http_proxy', None))
HTTPS_PROXY = os.environ.get('HTTPS_PROXY', os.environ.get('https_proxy', None))
# 如果需要手动配置，取消下面的注释并设置代理地址
# HTTP_PROXY = "http://proxy.example.com:8080"
# HTTPS_PROXY = "http://proxy.example.com:8080"


def load_config():
    """从配置文件加载API配置"""
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    return config.get('raw_llm_api', {})


class PureLLMEvaluator:
    """纯LLM API评估器 - 复用Docker容器以提高性能"""

    def __init__(self, api_config: Dict):
        self.client = openai.OpenAI(
            api_key=api_config['api_key'],
            base_url=api_config.get('base_url')
        )
        self.model = api_config.get('model', 'MiniMax-M2.5')
        self.docker_client = None  # 延迟初始化Docker客户端
        self._container_cache = {}  # 镜像标签 -> 容器 的缓存

    def _get_docker_client(self):
        """延迟初始化 Docker 客户端"""
        if self.docker_client is None:
            try:
                # K8s DinD 环境支持
                docker_host = os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock')
                if docker_host.startswith('tcp://'):
                    # TCP 连接（DinD sidecar）
                    self.docker_client = docker.DockerClient(base_url=docker_host)
                else:
                    # Unix socket（默认）
                    self.docker_client = docker.from_env()
                print(f"✓ Docker 连接成功: {docker_host}")
            except Exception as e:
                print(f"Docker 初始化失败: {e}")
                raise
        return self.docker_client

    def _get_or_create_container(self, image_tag: str):
        """获取或创建容器（复用已运行的容器）"""
        docker_client = self._get_docker_client()
        if image_tag in self._container_cache:
            container = self._container_cache[image_tag]
            try:
                # 检查容器是否还在运行
                container.reload()
                if container.status == 'running':
                    return container
            except:
                pass
            # 容器已停止，从缓存移除
            del self._container_cache[image_tag]

        # 创建新容器
        print(f"启动容器: {image_tag}")
        try:
            # 强制使用 linux/amd64 平台（用于 Mac 兼容）
            # 注意：在 Apple Silicon Mac 上会使用 Rosetta 2 模拟，速度较慢
            container = docker_client.containers.run(
                image_tag,
                platform="linux/amd64",  # 强制 x86_64 架构
                command="sleep infinity",
                detach=True,
                remove=False,
                mem_limit='4g',
                cpu_quota=100000,
            )
            self._container_cache[image_tag] = container
            
            # 启动后立即检查容器状态
            import time as time_module
            time_module.sleep(1)  # 给容器点时间启动
            container.reload()
            
            if container.status != 'running':
                print(f"✗ 容器启动失败: 状态为 {container.status}")
                # 查看容器日志了解原因
                try:
                    logs = container.logs(tail=20).decode()
                    if logs.strip():
                        print(f"容器日志:\n{logs}")
                except:
                    pass
                raise RuntimeError(f"Container failed to start (status: {container.status})")
            
            print(f"✓ 容器已启动并运行")
            return container
            
        except Exception as e:
            print(f"✗ 容器启动异常: {e}")
            raise

    def cleanup(self):
        """清理所有容器"""
        for image_tag, container in self._container_cache.items():
            try:
                print(f"停止容器: {image_tag}")
                container.stop(timeout=10)
                container.remove(force=True)
            except Exception as e:
                print(f"清理容器失败: {e}")
        self._container_cache.clear()

    def load_dataset(self, limit: Optional[int] = None):
        """加载数据集（支持离线、重试、超时和代理配置）"""
        import os
        from requests.exceptions import Timeout, ConnectionError
        
        # 优先使用本地离线数据集
        if LOCAL_DATASET_PATH:
            try:
                print(f"正在从本地路径加载数据集: {LOCAL_DATASET_PATH}")
                import pickle
                import json as json_lib
                
                # 支持多种格式
                if LOCAL_DATASET_PATH.endswith('.pkl') or LOCAL_DATASET_PATH.endswith('.pickle'):
                    with open(LOCAL_DATASET_PATH, 'rb') as f:
                        dataset = pickle.load(f)
                    print(f"✓ 本地 pickle 数据集加载成功")
                elif LOCAL_DATASET_PATH.endswith('.json'):
                    with open(LOCAL_DATASET_PATH, 'r') as f:
                        data = json_lib.load(f)
                    # 如果是列表格式，转换为 Dataset
                    from datasets import Dataset
                    dataset = Dataset.from_dict({k: [item[k] for item in data] for k in data[0].keys()})
                    print(f"✓ 本地 JSON 数据集加载成功")
                elif LOCAL_DATASET_PATH.endswith('.parquet'):
                    from datasets import load_dataset as hf_load
                    dataset = hf_load('parquet', data_files=LOCAL_DATASET_PATH)['train']
                    print(f"✓ 本地 Parquet 数据集加载成功")
                else:
                    # 尝试用 HuggingFace 加载本地文件
                    from datasets import load_from_disk
                    dataset = load_from_disk(LOCAL_DATASET_PATH)
                    print(f"✓ 本地数据集加载成功")
                
                if limit:
                    dataset = dataset.select(range(min(limit, len(dataset))))
                print(f"✓ 数据集加载完成，共 {len(dataset)} 个任务")
                return dataset
            except Exception as e:
                print(f"✗ 本地数据集加载失败: {e}")
                raise
        
        # 配置代理
        if HTTP_PROXY or HTTPS_PROXY:
            print(f"配置代理: HTTP={HTTP_PROXY}, HTTPS={HTTPS_PROXY}")
            if HTTP_PROXY:
                os.environ['HTTP_PROXY'] = HTTP_PROXY
            if HTTPS_PROXY:
                os.environ['HTTPS_PROXY'] = HTTPS_PROXY
        
        # 设置更大的超时和重试次数
        os.environ['HF_DATASETS_TIMEOUT'] = '60'  # 增加超时时间到 60 秒
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"正在加载数据集: {DATASET_NAME} (尝试 {attempt + 1}/{max_retries})")
                dataset = load_dataset(
                    DATASET_NAME,
                    split='test',
                    trust_remote_code=True,
                    download_mode='force_redownload' if attempt > 0 else 'reuse_dataset_if_exists'
                )
                if limit:
                    dataset = dataset.select(range(min(limit, len(dataset))))
                print(f"✓ 数据集加载完成，共 {len(dataset)} 个任务")
                return dataset
            except (Timeout, ConnectionError, OSError) as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避: 1s, 2s, 4s
                    print(f"✗ 网络错误: {str(e)[:50]}... 等待 {wait_time}s 后重试")
                    time.sleep(wait_time)
                else:
                    print(f"✗ 数据集加载失败（已重试 {max_retries} 次）: {e}")
                    raise
            except Exception as e:
                print(f"✗ 数据集加载失败: {e}")
                raise

    def get_codebase_context(self, instance: Dict) -> str:
        """从Docker容器中检索相关代码（复用容器）"""
        image_tag = f"jefzda/sweap-images:{instance['dockerhub_tag']}"
        
        try:
            container = self._get_or_create_container(image_tag)
            # 检查容器是否真的在运行
            container.reload()
            if container.status != 'running':
                print(f"⚠️ 容器状态异常: {container.status}")
                return ""
        except Exception as e:
            print(f"容器启动失败: {e}")
            return ""

        try:
            # 提取关键词
            keywords = self._extract_keywords(instance['problem_statement'])
            print(f"关键词: {keywords[:5]}")

            # 搜索相关文件
            relevant_files = []
            for keyword in keywords[:5]:
                # 转义关键词防止命令注入
                safe_keyword = shlex.quote(keyword)
                cmd = f"timeout 30 grep -l -r {safe_keyword} /testbed --include='*.py' --include='*.js' --include='*.ts' --include='*.go' 2>/dev/null | head -5"
                try:
                    # 尝试使用 timeout 参数（新版本 Docker SDK）
                    result = container.exec_run(cmd, timeout=CONTAINER_TIMEOUT)
                except TypeError:
                    # 如果 timeout 不支持，不传该参数（旧版本 Docker SDK）
                    result = container.exec_run(cmd)
                    
                if result.exit_code == 0:
                    files = result.output.decode().strip().split('\n')
                    relevant_files.extend([f for f in files if f and f not in relevant_files])

            print(f"找到相关文件: {len(relevant_files)}")

            # 读取文件内容
            code_context = ""
            for file_path in relevant_files[:MAX_FILES_TO_INCLUDE]:
                try:
                    cmd = f"head -{MAX_LINES_PER_FILE} {shlex.quote(file_path)}"
                    try:
                        # 尝试使用 timeout 参数
                        result = container.exec_run(cmd, timeout=30)
                    except TypeError:
                        # 如果不支持，不传 timeout
                        result = container.exec_run(cmd)
                    
                    if result.exit_code == 0:
                        content = result.output.decode()
                        code_context += f"\n### File: {file_path}\n```\n{content}\n```\n"
                except Exception as e:
                    print(f"读取文件失败 {file_path}: {e}")

            return code_context

        except Exception as e:
            print(f"获取代码上下文失败: {e}")
            return ""

    def _extract_keywords(self, problem_statement: str) -> List[str]:
        """从问题描述中提取搜索关键词"""
        patterns = [
            r'[A-Z][a-zA-Z0-9]+',           # 驼峰类名
            r'[a-z]+_[a-z_]+',               # 下划线函数名
            r'[A-Z][A-Z_]+',                 # 常量
            r'\b\w+Error\b',                 # 错误类型
        ]
        keywords = set()
        for pattern in patterns:
            matches = re.findall(pattern, problem_statement)
            keywords.update(matches[:3])
        return list(keywords)[:10]

    def build_prompt(self, instance: Dict, code_context: str) -> str:
        """构建prompt"""
        requirements_text = ""
        if instance.get('requirements'):
            requirements_text = f"\n## Requirements\n{instance['requirements']}\n"

        interface_text = ""
        if instance.get('interface'):
            interface_text = f"\n## Interface\n{instance['interface']}\n"

        prompt = f"""You are a software engineer tasked with fixing a bug.

## Problem Statement
{instance['problem_statement']}
{requirements_text}{interface_text}

## Codebase Context (Relevant Files)
Here are the relevant files from the codebase that may be related to this issue:

{code_context}

## Task
Based on the problem description and the codebase context above, generate a patch that fixes the issue.

## Output Format
Output ONLY the patch in unified diff format (git diff). Example:
```diff
diff --git a/path/to/file.py b/path/to/file.py
index abc123..def456 100644
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -42,6 +42,10 @@ def function_name():
     old_line()
+    # your fix here
+    new_line()
     return result
```

Generate the patch now:"""
        return prompt

    def call_llm(self, prompt: str) -> str:
        """调用LLM API生成patch"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful coding assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=4000,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM API调用失败: {e}")
            return ""

    def extract_patch(self, llm_output: str) -> str:
        """从LLM输出中提取patch"""
        # 查找diff代码块
        if "```diff" in llm_output:
            start = llm_output.find("```diff") + 7
            end = llm_output.find("```", start)
            return llm_output[start:end].strip()
        elif "```" in llm_output:
            start = llm_output.find("```") + 3
            end = llm_output.find("```", start)
            return llm_output[start:end].strip()
        return llm_output.strip()

    def evaluate_single(self, instance: Dict) -> Dict:
        """评估单个任务"""
        instance_id = instance.get('instance_id', 'unknown')
        print(f"\n{'='*60}")
        print(f"处理任务: {instance_id}")
        print(f"{'='*60}")

        # 1. 获取代码上下文
        print("正在获取代码上下文...")
        start_time = time.time()
        code_context = self.get_codebase_context(instance)
        elapsed = time.time() - start_time
        
        if not code_context or len(code_context.strip()) == 0:
            print(f"⚠️ 代码上下文为空（{elapsed:.2f}s）")
            print("  → 容器可能启动失败或无法访问代码")
            print("  → 将使用仅问题描述进行LLM调用")
        else:
            print(f"✓ 代码上下文获取完成，耗时: {elapsed:.2f}s ({len(code_context)} 字符)")

        # 2. 构建prompt
        prompt = self.build_prompt(instance, code_context)

        # 3. 调用LLM
        print("正在调用LLM...")
        start_time = time.time()
        llm_output = self.call_llm(prompt)
        print(f"LLM调用完成，耗时: {time.time() - start_time:.2f}s")

        # 4. 提取patch
        patch = self.extract_patch(llm_output)

        # 5. 验证patch（可选，耗时较长）
        validation_result = None
        if ENABLE_VALIDATION and patch and patch.strip():
            print("正在验证patch...")
            try:
                validation_result = self.validate_patch(instance, patch)
                print(f"验证结果: {'✓ 通过' if validation_result.get('success') else '✗ 失败'}")
            except Exception as e:
                print(f"验证失败: {e}")
                validation_result = {'success': False, 'error': str(e)}

        result = {
            'instance_id': instance_id,
            'patch': patch,
            'raw_output': llm_output,
            'code_context_length': len(code_context),
            'validation': validation_result,
        }

        return result

    def apply_and_test_patch(self, instance: Dict, patch: str, container) -> Dict:
        """
        应用patch并运行测试验证
        返回: {'success': bool, 'test_output': str, 'error': str}
        """
        if not patch or not patch.strip():
            return {'success': False, 'error': 'Empty patch'}

        try:
            # 1. 使用 Python 正确写入 patch（支持多行和特殊字符）
            # 通过 base64 编码避免特殊字符问题
            import base64
            patch_b64 = base64.b64encode(patch.encode()).decode()
            cmd = f"echo '{patch_b64}' | base64 -d > /tmp/fix.patch"
            try:
                result = container.exec_run(["sh", "-c", cmd], timeout=30)
            except TypeError:
                result = container.exec_run(["sh", "-c", cmd])
            if result.exit_code != 0:
                return {'success': False, 'error': 'Failed to write patch'}

            # 2. 应用patch（先尝试 git apply，失败再尝试 patch 命令）
            try:
                result = container.exec_run("cd /testbed && git apply /tmp/fix.patch 2>&1", timeout=30)
            except TypeError:
                result = container.exec_run("cd /testbed && git apply /tmp/fix.patch 2>&1")
            if result.exit_code != 0:
                error_msg = result.output.decode()
                # 尝试使用 patch 命令
                try:
                    result = container.exec_run("cd /testbed && patch -p1 < /tmp/fix.patch 2>&1", timeout=30)
                except TypeError:
                    result = container.exec_run("cd /testbed && patch -p1 < /tmp/fix.patch 2>&1")
                if result.exit_code != 0:
                    return {'success': False, 'error': f'Patch apply failed: {error_msg}'}

            print("Patch 应用成功")

            # 3. 获取测试命令（SWE-bench Pro 格式）
            test_cmd = self._get_test_command(instance)
            if not test_cmd:
                return {'success': False, 'error': 'No test command found'}

            print(f"运行测试: {test_cmd[:100]}...")
            try:
                result = container.exec_run(["sh", "-c", test_cmd], timeout=300)
            except TypeError:
                result = container.exec_run(["sh", "-c", test_cmd])
            test_output = result.output.decode()

            # 4. 判断是否成功
            success = result.exit_code == 0 and 'FAILED' not in test_output and 'ERROR' not in test_output

            return {
                'success': success,
                'test_output': test_output[-5000:],  # 保留最后5000字符
                'exit_code': result.exit_code
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _get_test_command(self, instance: Dict) -> str:
        """获取测试命令"""
        # SWE-bench Pro 可能有不同字段
        if 'test_cmd' in instance:
            return instance['test_cmd']
        elif 'test_patch' in instance:
            # 有些数据集使用 test_patch
            return f"cd /testbed && {instance['test_patch']}"
        else:
            # 默认使用 pytest
            return "cd /testbed && python -m pytest -xvs"

    def validate_patch(self, instance: Dict, patch: str) -> Dict:
        """验证patch是否正确（复用容器但重置状态）"""
        image_tag = f"jefzda/sweap-images:{instance['dockerhub_tag']}"

        # 复用容器但通过 git reset 重置状态
        container = self._get_or_create_container(image_tag)

        try:
            # 先重置 git 状态，确保干净环境
            try:
                container.exec_run("cd /testbed && git reset --hard HEAD && git clean -fdx", timeout=30)
            except TypeError:
                container.exec_run("cd /testbed && git reset --hard HEAD && git clean -fdx")
            
            result = self.apply_and_test_patch(instance, patch, container)
            return result
        except Exception as e:
            return {'success': False, 'error': f'Validation error: {str(e)}'}

    def evaluate(self, limit: Optional[int] = None, output_file: str = "results.jsonl"):
        """运行评测"""
        dataset = self.load_dataset(limit)
        results = []
        
        # 清空或创建输出文件
        with open(output_file, 'w') as f:
            pass

        try:
            for i, instance in enumerate(dataset):
                print(f"\n{'='*60}")
                print(f"进度: {i+1}/{len(dataset)}")
                print(f"{'='*60}")

                try:
                    result = self.evaluate_single(instance)
                    results.append(result)

                    # 实时保存结果
                    with open(output_file, 'a') as f:
                        f.write(json.dumps(result, ensure_ascii=False) + '\n')

                    # 打印摘要
                    success = result.get('validation', {}).get('success', False) if result.get('validation') else None
                    status = "✓" if success else ("✗" if success is False else "⊘")
                    print(f"{status} {result['instance_id']}: patch={'有' if result.get('patch') else '无'}")

                except Exception as e:
                    print(f"任务处理失败: {e}")
                    error_result = {
                        'instance_id': instance.get('instance_id', 'unknown'),
                        'error': str(e)
                    }
                    results.append(error_result)
                    with open(output_file, 'a') as f:
                        f.write(json.dumps(error_result, ensure_ascii=False) + '\n')

        finally:
            # 确保清理容器
            self.cleanup()

        # 打印统计
        total = len(results)
        with_patch = sum(1 for r in results if r.get('patch'))
        validated = sum(1 for r in results if r.get('validation') is not None)
        success = sum(1 for r in results if r.get('validation', {}).get('success'))
        
        print(f"\n{'='*60}")
        print(f"评测完成统计:")
        print(f"总任务数: {total}")
        print(f"生成patch: {with_patch}/{total} ({with_patch/total*100:.1f}%)")
        if validated > 0:
            print(f"验证通过: {success}/{validated} ({success/validated*100:.1f}%)")
        print(f"{'='*60}")

        return results


def main():
    """主函数 - 单任务评测模式"""
    import argparse
    parser = argparse.ArgumentParser(description='SWE-bench Pro LLM 评测（单任务模式）')
    parser.add_argument('--instance-id', type=str, help='指定任务ID（如 django__django-12345）')
    parser.add_argument('--index', type=int, help='任务索引（从0开始）')
    parser.add_argument('--no-validate', action='store_true', help='跳过验证（只生成patch）')
    parser.add_argument('--output-dir', default='./swe_bench_output', help='输出目录')
    parser.add_argument('--analysis', action='store_true', help='分析已有结果')
    args = parser.parse_args()

    # 如果是分析模式
    if args.analysis:
        analyze_results(args.output_dir)
        return

    # 全局配置
    global ENABLE_VALIDATION
    ENABLE_VALIDATION = not args.no_validate

    # 检查参数
    if not args.instance_id and args.index is None:
        parser.error("必须指定 --instance-id 或 --index")

    # 从配置文件加载API配置
    try:
        api_config = load_config()
    except Exception as e:
        print(f"错误: 无法读取配置文件 {CONFIG_PATH}: {e}")
        return

    if not api_config or not api_config.get('api_key'):
        print(f"错误: 请检查配置文件 {CONFIG_PATH} 中的 raw_llm_api 配置")
        return

    print(f"使用模型: {api_config.get('model')}")
    print(f"API地址: {api_config.get('base_url')}")
    print(f"验证模式: {'启用' if ENABLE_VALIDATION else '禁用'}")

    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    predictions_dir = os.path.join(args.output_dir, 'predictions')
    os.makedirs(predictions_dir, exist_ok=True)

    evaluator = PureLLMEvaluator(api_config=api_config)

    try:
        # 加载数据集
        dataset = evaluator.load_dataset()
        
        # 选择任务
        if args.instance_id:
            # 通过 instance_id 查找
            instance = None
            for item in dataset:
                if item['instance_id'] == args.instance_id:
                    instance = item
                    break
            if not instance:
                print(f"错误: 未找到任务 {args.instance_id}")
                return
        else:
            # 通过索引选择
            if args.index >= len(dataset):
                print(f"错误: 索引 {args.index} 超出范围（数据集共 {len(dataset)} 个任务）")
                return
            instance = dataset[args.index]

        instance_id = instance['instance_id']
        print(f"\n开始评测任务: {instance_id} (索引: {dataset.tolist().index(instance) if hasattr(dataset, 'tolist') else '?'})")
        
        # 评估单个任务
        result = evaluator.evaluate_single(instance)
        
        # 保存结果（SWE-bench harness 格式）
        save_result_harness_format(result, predictions_dir, args.output_dir)
        
        # 打印摘要
        print(f"\n{'='*60}")
        print(f"任务ID: {instance_id}")
        print(f"Patch生成: {'✓' if result.get('patch') else '✗'}")
        if result.get('validation'):
            print(f"验证结果: {'✓ 通过' if result.get('validation', {}).get('success') else '✗ 失败'}")
        print(f"结果保存到: {args.output_dir}")
        print(f"{'='*60}")

    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        error_msg = str(e)
        if 'timed out' in error_msg.lower() or 'connection reset' in error_msg.lower() or 'connection' in error_msg.lower():
            print(f"\n✗ 网络连接问题: {e}")
            print("\n💡 解决方案:")
            print("  1. 检查网络连接")
            print("  2. 数据集已缓存位置:", HF_CACHE_DIR)
            print("  3. 使用本地离线数据集（推荐）:")
            print("     - 从 https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro 下载")
            print("     - 运行: LOCAL_DATASET_PATH=/path/to/dataset.parquet python test_llm_api.py --index 0")
            print("  4. 配置代理（如需要）:")
            print("     - 方案A: 环境变量")
            print("       export HTTP_PROXY=http://proxy.example.com:8080")
            print("       export HTTPS_PROXY=http://proxy.example.com:8080")
            print("     - 方案B: 直接编辑代码")
            print("       修改 test_llm_api.py 第 28-29 行配置")
            print("  5. 可尝试重新运行，会使用已缓存的数据")
            print("  6. 或在网络稳定后重新加载")
        else:
            print(f"\n评测失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        evaluator.cleanup()


def save_result_harness_format(result: Dict, predictions_dir: str, output_dir: str):
    """保存为 SWE-bench harness 兼容格式"""
    instance_id = result['instance_id']
    
    # 1. 保存 prediction (harness 标准格式)
    prediction = {
        'instance_id': instance_id,
        'model_patch': result.get('patch', ''),
        'model_name_or_path': 'llm_api',
    }
    pred_file = os.path.join(predictions_dir, f"{instance_id}.json")
    with open(pred_file, 'w') as f:
        json.dump(prediction, f, indent=2, ensure_ascii=False)
    
    # 2. 保存完整结果（包含验证信息）
    full_result_file = os.path.join(output_dir, f"{instance_id}_full.json")
    with open(full_result_file, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    # 3. 追加到汇总文件
    summary_file = os.path.join(output_dir, 'all_results.jsonl')
    with open(summary_file, 'a') as f:
        f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    print(f"✓ 结果已保存:")
    print(f"  - Prediction: {pred_file}")
    print(f"  - Full result: {full_result_file}")


def analyze_results(output_dir: str):
    """详细评测结果分析与打分"""
    summary_file = os.path.join(output_dir, 'all_results.jsonl')
    
    if not os.path.exists(summary_file):
        print(f"错误: 未找到结果文件 {summary_file}")
        return
    
    # 读取所有结果
    results = []
    with open(summary_file, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    results.append(json.loads(line))
                except:
                    continue
    
    if not results:
        print("没有找到评测结果")
        return
    
    # ========== 基础统计 ==========
    total = len(results)
    with_patch = [r for r in results if r.get('patch') and r.get('patch').strip()]
    no_patch = [r for r in results if not r.get('patch') or not r.get('patch').strip()]
    has_error = [r for r in results if r.get('error')]
    
    validated = [r for r in results if r.get('validation') is not None]
    resolved = [r for r in validated if r.get('validation', {}).get('success')]
    failed = [r for r in validated if not r.get('validation', {}).get('success')]
    
    # ========== 失败原因分析 ==========
    patch_apply_errors = []
    test_failures = []
    timeout_errors = []
    other_errors = []
    
    for r in failed:
        error_msg = r.get('validation', {}).get('error', '')
        if 'Patch apply failed' in error_msg:
            patch_apply_errors.append(r)
        elif 'FAILED' in r.get('validation', {}).get('test_output', ''):
            test_failures.append(r)
        elif 'timeout' in error_msg.lower():
            timeout_errors.append(r)
        else:
            other_errors.append(r)
    
    # ========== 代码上下文质量分析 ==========
    context_lengths = [r.get('code_context_length', 0) for r in results if 'code_context_length' in r]
    avg_context_length = sum(context_lengths) / len(context_lengths) if context_lengths else 0
    
    # ========== 计算评分 ==========
    scores = calculate_scores(results, resolved, with_patch, total)
    
    # ========== 打印详细报告 ==========
    print(f"\n{'='*70}")
    print(f"{'SWE-bench Pro 评测结果分析':^70}")
    print(f"{'='*70}\n")
    
    # 1. 核心指标
    print(f"📊 核心指标 (SWE-bench 标准)")
    print(f"{'─'*70}")
    print(f"  总任务数:        {total}")
    print(f"  生成Patch:       {len(with_patch)}/{total} ({len(with_patch)/total*100:.1f}%)")
    if validated:
        print(f"  已验证:          {len(validated)}/{total} ({len(validated)/total*100:.1f}%)")
        print(f"  ✓ 已解决:        {len(resolved)}/{len(validated)} ({len(resolved)/len(validated)*100:.1f}%)")
        print(f"  ★ Resolved率:    {len(resolved)/total*100:.1f}% ← 官方排行榜指标")
    print()
    
    # 2. 评分系统
    print(f"🎯 评分系统")
    print(f"{'─'*70}")
    for metric, score in scores.items():
        stars = '★' * int(score / 20) + '☆' * (5 - int(score / 20))
        print(f"  {metric:.<25} {score:>5.1f}/100 {stars}")
    overall_score = sum(scores.values()) / len(scores)
    stars = '★' * int(overall_score / 20) + '☆' * (5 - int(overall_score / 20))
    print(f"  {'─'*70}")
    print(f"  {'综合评分':.<25} {overall_score:>5.1f}/100 {stars}")
    print()
    
    # 3. 失败分析
    if failed:
        print(f"❌ 失败原因分析 (共 {len(failed)} 个)")
        print(f"{'─'*70}")
        print(f"  Patch应用失败:   {len(patch_apply_errors)} ({len(patch_apply_errors)/len(failed)*100:.1f}%)")
        print(f"  测试未通过:      {len(test_failures)} ({len(test_failures)/len(failed)*100:.1f}%)")
        print(f"  超时:            {len(timeout_errors)} ({len(timeout_errors)/len(failed)*100:.1f}%)")
        print(f"  其他错误:        {len(other_errors)} ({len(other_errors)/len(failed)*100:.1f}%)")
        print()
    
    # 4. 代码上下文质量
    print(f"📝 代码上下文统计")
    print(f"{'─'*70}")
    print(f"  平均长度:        {avg_context_length:.0f} 字符")
    print(f"  无上下文任务:    {sum(1 for l in context_lengths if l == 0)}/{len(context_lengths)}")
    print()
    
    # 5. 任务详情列表
    print(f"📋 任务详情")
    print(f"{'─'*70}")
    print(f"{'状态':<6} {'任务ID':<40} {'Patch':<8} {'验证':<8}")
    print(f"{'─'*70}")
    
    # 按结果分组显示
    for status_name, task_list in [
        ("✓ 通过", resolved),
        ("✗ 失败", failed),
        ("⊘ 未验证", [r for r in with_patch if r not in validated]),
        ("⊗ 无Patch", no_patch),
    ]:
        for r in task_list[:20]:  # 每类最多显示20个
            instance_id = r.get('instance_id', 'unknown')[:40]
            has_patch = '✓' if r.get('patch') else '✗'
            val_status = '通过' if r in resolved else ('失败' if r in failed else '-')
            print(f"{status_name:<6} {instance_id:<40} {has_patch:<8} {val_status:<8}")
        
        remaining = len(task_list) - 20
        if remaining > 0:
            print(f"{'...':<6} (还有 {remaining} 个)")
    
    print(f"{'─'*70}\n")
    
    # ========== 保存详细报告 ==========
    report_file = os.path.join(output_dir, 'analysis_report.txt')
    save_detailed_report(report_file, {
        'total': total,
        'with_patch': len(with_patch),
        'validated': len(validated),
        'resolved': len(resolved),
        'failed': len(failed),
        'scores': scores,
        'overall_score': overall_score,
        'failure_analysis': {
            'patch_apply_errors': len(patch_apply_errors),
            'test_failures': len(test_failures),
            'timeout_errors': len(timeout_errors),
            'other_errors': len(other_errors),
        },
        'avg_context_length': avg_context_length,
        'results': results,
    })
    
    # ========== 生成 JSON 报告 ==========
    json_report_file = os.path.join(output_dir, 'analysis_report.json')
    with open(json_report_file, 'w') as f:
        json.dump({
            'summary': {
                'total_tasks': total,
                'patches_generated': len(with_patch),
                'validated': len(validated),
                'resolved': len(resolved),
                'resolved_rate': len(resolved) / total * 100 if total > 0 else 0,
            },
            'scores': scores,
            'overall_score': overall_score,
            'failure_analysis': {
                'patch_apply_errors': len(patch_apply_errors),
                'test_failures': len(test_failures),
                'timeout_errors': len(timeout_errors),
                'other_errors': len(other_errors),
            },
        }, f, indent=2, ensure_ascii=False)
    
    print(f"📄 报告已保存:")
    print(f"  - 文本报告: {report_file}")
    print(f"  - JSON报告: {json_report_file}")
    print(f"{'='*70}\n")


def calculate_scores(results, resolved, with_patch, total):
    """计算各项评分（0-100分）"""
    scores = {}
    
    # 1. Patch生成能力 (0-100)
    scores['Patch生成能力'] = (len(with_patch) / total * 100) if total > 0 else 0
    
    # 2. 解决问题能力 (0-100)
    scores['问题解决能力'] = (len(resolved) / total * 100) if total > 0 else 0
    
    # 3. Patch质量 (基于验证通过率, 0-100)
    validated = [r for r in results if r.get('validation') is not None]
    if validated:
        scores['Patch质量'] = (len(resolved) / len(validated) * 100)
    else:
        scores['Patch质量'] = 0
    
    # 4. 代码检索能力 (基于是否找到相关代码, 0-100)
    with_context = sum(1 for r in results if r.get('code_context_length', 0) > 100)
    scores['代码检索能力'] = (with_context / total * 100) if total > 0 else 0
    
    # 5. 稳定性 (基于错误率, 0-100)
    errors = sum(1 for r in results if r.get('error'))
    scores['系统稳定性'] = ((total - errors) / total * 100) if total > 0 else 0
    
    return scores


def save_detailed_report(report_file, data):
    """保存详细的文本报告"""
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("SWE-bench Pro 评测详细报告\n")
        f.write("=" * 70 + "\n\n")
        
        # 核心指标
        f.write("核心指标\n")
        f.write("-" * 70 + "\n")
        f.write(f"总任务数: {data['total']}\n")
        f.write(f"生成Patch: {data['with_patch']}/{data['total']} ({data['with_patch']/data['total']*100:.1f}%)\n")
        if data['validated'] > 0:
            f.write(f"已验证: {data['validated']}/{data['total']} ({data['validated']/data['total']*100:.1f}%)\n")
            f.write(f"已解决: {data['resolved']}/{data['validated']} ({data['resolved']/data['validated']*100:.1f}%)\n")
            f.write(f"Resolved率: {data['resolved']/data['total']*100:.1f}%\n")
        f.write("\n")
        
        # 评分
        f.write("评分系统\n")
        f.write("-" * 70 + "\n")
        for metric, score in data['scores'].items():
            f.write(f"{metric}: {score:.1f}/100\n")
        f.write(f"综合评分: {data['overall_score']:.1f}/100\n")
        f.write("\n")
        
        # 失败分析
        if data['failed'] > 0:
            f.write("失败原因分析\n")
            f.write("-" * 70 + "\n")
            fa = data['failure_analysis']
            f.write(f"Patch应用失败: {fa['patch_apply_errors']}\n")
            f.write(f"测试未通过: {fa['test_failures']}\n")
            f.write(f"超时: {fa['timeout_errors']}\n")
            f.write(f"其他错误: {fa['other_errors']}\n")
            f.write("\n")
        
        # 所有任务详情
        f.write("完整任务列表\n")
        f.write("-" * 70 + "\n")
        for r in data['results']:
            instance_id = r.get('instance_id', 'unknown')
            has_patch = '✓' if r.get('patch') else '✗'
            val = r.get('validation')
            status = '✓通过' if val and val.get('success') else ('✗失败' if val else '⊘未验证')
            f.write(f"{status} | {instance_id} | Patch:{has_patch}\n")
            
            # 如果有错误，记录错误信息
            if val and not val.get('success'):
                error = val.get('error', 'Unknown error')[:100]
                f.write(f"    错误: {error}\n")


if __name__ == "__main__":
    main()
