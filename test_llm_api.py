import json
import docker
import openai
from datasets import load_dataset
from typing import Dict, List, Optional
import os
import re
import time
import shlex
import base64
import tarfile
import io

# ============ 配置 ============
CONFIG_PATH = os.path.expanduser("./.experience.json")
# CONFIG_PATH = os.path.expanduser("~/.experience.json")
DATASET_NAME = "ScaleAI/SWE-bench_Pro"
MAX_FILES_TO_INCLUDE = 10
MAX_LINES_PER_FILE = 300
CONTAINER_TIMEOUT = 300
ENABLE_VALIDATION = True

# 本地数据集路径 - 自动检测
LOCAL_DATASET_PATH = os.environ.get('LOCAL_DATASET_PATH', None)
if not LOCAL_DATASET_PATH:
    possible_paths = [
        os.path.expanduser("/ssd1/Dejavu/datasets/SWE-bench_Pro/test-00000-of-00001.parquet"),
        #os.path.expanduser("~/datasets/SWE-bench_Pro/test-00000-of-00001.parquet"),
        os.path.expanduser("/ssd1/Dejavu/datasets/SWE-bench_Pro"),
        # os.path.expanduser("~/datasets/SWE-bench_Pro"),
        "./datasets/SWE-bench_Pro/test-00000-of-00001.parquet",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            LOCAL_DATASET_PATH = path
            print(f"✓ 自动检测到本地数据集: {path}")
            break


def load_config():
    """从配置文件加载API配置"""
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    return config.get('raw_llm_api', {})


class PureLLMEvaluator:
    """SWE-bench LLM评估器"""

    def __init__(self, api_config: Dict):
        self.client = openai.OpenAI(
            api_key=api_config['api_key'],
            base_url=api_config.get('base_url')
        )
        self.model = api_config.get('model', 'MiniMax-M2.5')
        self.docker_client = None
        self._container_cache = {}

    def _get_docker_client(self):
        """初始化Docker客户端"""
        if self.docker_client is None:
            try:
                self.docker_client = docker.from_env()
                print(f"✓ Docker 连接成功")
            except Exception as e:
                print(f"✗ Docker 初始化失败: {e}")
                raise
        return self.docker_client

    def _pull_image_with_mirror(self, image_tag: str):
        """使用镜像源拉取镜像（如果本地没有）"""
        docker_client = self._get_docker_client()
        
        # 检查本地是否已有镜像
        try:
            docker_client.images.get(image_tag)
            print(f"✓ 本地已有镜像: {image_tag}")
            return
        except docker.errors.ImageNotFound:
            pass
        
        print(f"本地没有镜像,开始拉取: {image_tag}")
        
        # 直接拉取,不使用镜像源(镜像源不支持第三方仓库)
        try:
            print(f"  正在从Docker Hub拉取...")
            docker_client.images.pull(image_tag)
            print(f"  ✓ 拉取成功")
            return
        except Exception as e:
            print(f"  ✗ 拉取失败: {e}")
            raise RuntimeError(f"镜像拉取失败: {image_tag}")

    def _get_or_create_container(self, image_tag: str):
        """获取或创建容器（复用机制）"""
        docker_client = self._get_docker_client()
        
        # 检查缓存
        if image_tag in self._container_cache:
            container = self._container_cache[image_tag]
            try:
                container.reload()
                if container.status == 'running':
                    return container
            except:
                pass
            del self._container_cache[image_tag]

        # 确保镜像已拉取
        print(f"准备容器: {image_tag}")
        self._pull_image_with_mirror(image_tag)
        
        # 创建新容器
        print(f"启动容器: {image_tag}")
        
        # 尝试检测Docker API版本,决定是否使用platform参数
        try:
            api_version = docker_client.api.api_version
            use_platform = float(api_version) >= 1.41
        except:
            use_platform = False
        
        container_args = {
            'image': image_tag,
            'command': ["/bin/sh", "-c", "tail -f /dev/null"],  # 使用tail保持运行,不依赖sleep
            'entrypoint': "",  # 覆盖默认entrypoint
            'detach': True,
            'remove': False,
            'mem_limit': '4g',
            'stdin_open': True,
            'tty': True,
            'privileged': True,  # 给予特权模式,避免权限问题
            'security_opt': ['seccomp=unconfined'],  # 禁用seccomp安全限制
        }
        
        # 只在支持的API版本上使用platform参数
        if use_platform:
            container_args['platform'] = "linux/amd64"
        
        container = docker_client.containers.run(**container_args)
        self._container_cache[image_tag] = container
        
        # 等待容器启动（增加重试）
        max_retries = 10
        for i in range(max_retries):
            time.sleep(1)
            container.reload()
            if container.status == 'running':
                print(f"✓ 容器已启动")
                return container
            if i == max_retries - 1:
                try:
                    logs = container.logs(tail=50).decode()
                    raise RuntimeError(f"容器启动失败. 日志:\n{logs}")
                except:
                    raise RuntimeError(f"容器启动失败 (status: {container.status})")

    def cleanup(self):
        """清理所有容器和资源"""
        for image_tag, container in list(self._container_cache.items()):
            try:
                print(f"清理容器: {image_tag}")
                container.kill()
                container.remove(force=True, v=True)
            except docker.errors.NotFound:
                pass
            except Exception as e:
                print(f"清理容器失败: {e}")
            finally:
                self._container_cache.pop(image_tag, None)
        
        # 关闭Docker客户端
        if self.docker_client:
            try:
                self.docker_client.close()
            except:
                pass
            self.docker_client = None

    def load_dataset(self, limit: Optional[int] = None):
        """加载数据集"""
        if LOCAL_DATASET_PATH:
            try:
                print(f"正在从本地加载: {LOCAL_DATASET_PATH}")
                if LOCAL_DATASET_PATH.endswith('.parquet'):
                    from datasets import load_dataset as hf_load
                    dataset = hf_load('parquet', data_files=LOCAL_DATASET_PATH)['train']
                elif LOCAL_DATASET_PATH.endswith('.json'):
                    with open(LOCAL_DATASET_PATH, 'r') as f:
                        data = json.load(f)
                    from datasets import Dataset
                    dataset = Dataset.from_dict({k: [item[k] for item in data] for k in data[0].keys()})
                else:
                    from datasets import load_from_disk
                    dataset = load_from_disk(LOCAL_DATASET_PATH)
                
                if limit:
                    dataset = dataset.select(range(min(limit, len(dataset))))
                print(f"✓ 数据集加载完成: {len(dataset)} 个任务")
                return dataset
            except Exception as e:
                print(f"✗ 本地数据集加载失败: {e}")
                raise
        
        # 在线加载
        print(f"正在从HuggingFace加载: {DATASET_NAME}")
        dataset = load_dataset(DATASET_NAME, split='test', trust_remote_code=True)
        if limit:
            dataset = dataset.select(range(min(limit, len(dataset))))
        print(f"✓ 数据集加载完成: {len(dataset)} 个任务")
        return dataset

    def get_codebase_context(self, instance: Dict) -> str:
        """从容器中检索相关代码"""
        image_tag = f"jefzda/sweap-images:{instance['dockerhub_tag']}"
        
        try:
            container = self._get_or_create_container(image_tag)
            container.reload()
            if container.status != 'running':
                return ""
        except Exception as e:
            print(f"容器启动失败: {e}")
            return ""

        # 先检查容器内的目录结构和可用命令
        check_cmd = "/bin/sh -c 'echo === Architecture ===; uname -m; echo === Root directory ===; ls / 2>&1 | head -20; echo === Testbed ===; ls /testbed 2>&1 | head -20; echo === App directory ===; ls /app 2>&1 | head -20; echo === Available commands ===; which python python3 grep find 2>&1; echo === Python version ===; python3 --version 2>&1 || echo no python3'"
        check_result = container.exec_run(check_cmd)
        check_output = check_result.output.decode()
        print(f"容器检查:\n{check_output}")
        
        # 检查架构
        if 'aarch64' in check_output or 'arm64' in check_output:
            print("⚠️  警告: 容器是ARM架构,可能导致问题!")
        
        # 自动检测工作目录
        workdir = '/testbed'
        if b'No such file or directory' in check_result.output and b'app' in check_result.output:
            workdir = '/app'
            print(f"✓ 检测到工作目录: {workdir}")
        
        # 提取关键词
        keywords = self._extract_keywords(instance['problem_statement'])
        print(f"搜索关键词: {keywords[:5]}")

        # 根据repo_language确定文件扩展名
        repo_lang = instance.get('repo_language', 'Python').lower()
        if 'javascript' in repo_lang or 'js' in repo_lang or 'node' in repo_lang:
            file_patterns = "*.js"
            print(f"✓ 检测到JavaScript项目")
        elif 'python' in repo_lang:
            file_patterns = "*.py"
            print(f"✓ 检测到Python项目")
        else:
            file_patterns = "*"  # 默认所有文件
            print(f"✓ 未知语言,搜索所有文件")

        # 使用grep搜索相关文件(现在架构正确了)
        relevant_files = []
        for keyword in keywords[:3]:  # 只用前3个关键词
            safe_keyword = keyword.replace("'", "'\\''")
            grep_cmd = f"timeout 90 grep -l -r '{safe_keyword}' {workdir} --include='{file_patterns}' --exclude-dir='.git' --exclude-dir='node_modules' --exclude-dir='__pycache__' --exclude-dir='.venv' 2>/dev/null | head -5"
            result = container.exec_run(["/bin/sh", "-c", grep_cmd])
            
            if result.exit_code == 0:
                output = result.output.decode().strip()
                if output:
                    files = output.split('\n')
                    for f in files:
                        if f and f not in relevant_files:
                            relevant_files.append(f)
                            if len(relevant_files) >= 10:
                                break
            if len(relevant_files) >= 10:
                break
        
        print(f"找到相关文件: {len(relevant_files)}")
        if relevant_files:
            print(f"  文件列表: {relevant_files[:5]}")

        # 读取文件内容
        code_context = ""
        for file_path in relevant_files[:MAX_FILES_TO_INCLUDE]:
            try:
                cmd = f"head -{MAX_LINES_PER_FILE} {shlex.quote(file_path)}"
                result = container.exec_run(cmd, workdir=workdir)
                if result.exit_code == 0:
                    content = result.output.decode()
                    code_context += f"\n### File: {file_path}\n```\n{content}\n```\n"
            except Exception as e:
                print(f"读取文件失败 {file_path}: {e}")

        return code_context

    def _extract_keywords(self, problem_statement: str) -> List[str]:
        """从问题描述中提取关键词"""
        patterns = [
            r'[A-Z][a-zA-Z0-9]+',      # 驼峰类名
            r'[a-z]+_[a-z_]+',          # 下划线函数名
            r'[A-Z][A-Z_]+',            # 常量
            r'\b\w+Error\b',            # 错误类型
        ]
        keywords = set()
        for pattern in patterns:
            matches = re.findall(pattern, problem_statement)
            keywords.update(matches[:3])
        return list(keywords)[:10]

    def build_prompt(self, instance: Dict, code_context: str) -> str:
        """构建prompt"""
        requirements = f"\n## Requirements\n{instance['requirements']}\n" if instance.get('requirements') else ""
        interface = f"\n## Interface\n{instance['interface']}\n" if instance.get('interface') else ""

        return f"""You are a software engineer tasked with fixing a bug.

## Problem Statement
{instance['problem_statement']}
{requirements}{interface}

## Codebase Context (Relevant Files)
{code_context}

## Task
Generate a patch that fixes the issue.

## Output Format
Output ONLY the patch in unified diff format:
```diff
diff --git a/path/to/file.py b/path/to/file.py
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -42,6 +42,10 @@ def function_name():
     old_line()
+    new_line()
     return result
```

Generate the patch now:"""

    def call_llm(self, prompt: str) -> str:
        """调用LLM生成patch"""
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
            print(f"LLM调用失败: {e}")
            return ""

    def extract_patch(self, llm_output: str) -> str:
        """从LLM输出中提取patch"""
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

        # 获取代码上下文
        print("正在获取代码上下文...")
        start_time = time.time()
        code_context = self.get_codebase_context(instance)
        elapsed = time.time() - start_time
        
        if not code_context:
            print(f"⚠️  代码上下文为空 ({elapsed:.2f}s)")
        else:
            print(f"✓ 代码上下文获取完成: {elapsed:.2f}s ({len(code_context)} 字符)")

        # 构建prompt并调用LLM
        prompt = self.build_prompt(instance, code_context)
        print("正在调用LLM...")
        start_time = time.time()
        llm_output = self.call_llm(prompt)
        print(f"✓ LLM调用完成: {time.time() - start_time:.2f}s")

        # 提取patch
        patch = self.extract_patch(llm_output)

        # 验证patch
        validation_result = None
        if ENABLE_VALIDATION and patch:
            print("正在验证patch...")
            try:
                validation_result = self.validate_patch(instance, patch)
                print(f"验证结果: {'✓ 通过' if validation_result.get('success') else '✗ 失败'}")
            except Exception as e:
                print(f"验证失败: {e}")
                validation_result = {'success': False, 'error': str(e)}

        return {
            'instance_id': instance_id,
            'patch': patch,
            'raw_output': llm_output,
            'code_context_length': len(code_context),
            'validation': validation_result,
        }

    def apply_and_test_patch(self, instance: Dict, patch: str, container) -> Dict:
        """应用patch并测试"""
        if not patch:
            return {'success': False, 'error': 'Empty patch'}

        try:
            # 使用heredoc写入patch（修复：避免长度限制）
            patch_escaped = patch.replace("'", "'\\''")
            write_cmd = f"""cat > /tmp/fix.patch << 'PATCH_EOF'
{patch}
PATCH_EOF"""
            result = container.exec_run(['sh', '-c', write_cmd], workdir='/testbed')
            if result.exit_code != 0:
                return {'success': False, 'error': 'Failed to write patch'}

            # 应用patch
            result = container.exec_run("git apply /tmp/fix.patch 2>&1", workdir='/testbed')
            if result.exit_code != 0:
                # 尝试patch命令
                result = container.exec_run("patch -p1 < /tmp/fix.patch 2>&1", workdir='/testbed')
                if result.exit_code != 0:
                    return {'success': False, 'error': f'Patch apply failed: {result.output.decode()}'}

            print("✓ Patch应用成功")

            # 运行测试
            test_cmd = self._get_test_command(instance)
            if not test_cmd:
                return {'success': False, 'error': 'No test command'}

            print(f"运行测试: {test_cmd[:100]}...")
            result = container.exec_run(test_cmd, workdir='/testbed')
            test_output = result.output.decode()

            success = result.exit_code == 0 and 'FAILED' not in test_output and 'ERROR' not in test_output

            return {
                'success': success,
                'test_output': test_output[-5000:],
                'exit_code': result.exit_code
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _get_test_command(self, instance: Dict) -> str:
        """获取测试命令"""
        if 'test_cmd' in instance:
            return instance['test_cmd']
        elif 'test_patch' in instance:
            return f"cd /testbed && {instance['test_patch']}"
        return "cd /testbed && python -m pytest -xvs"

    def validate_patch(self, instance: Dict, patch: str) -> Dict:
        """验证patch"""
        image_tag = f"jefzda/sweap-images:{instance['dockerhub_tag']}"
        container = self._get_or_create_container(image_tag)

        try:
            # 重置git状态
            container.exec_run("git reset --hard HEAD && git clean -fdx", workdir='/testbed')
            return self.apply_and_test_patch(instance, patch, container)
        except Exception as e:
            return {'success': False, 'error': f'Validation error: {str(e)}'}

    def evaluate(self, limit: Optional[int] = None, output_file: str = "results.jsonl"):
        """运行评测"""
        dataset = self.load_dataset(limit)
        results = []
        
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

                    with open(output_file, 'a') as f:
                        f.write(json.dumps(result, ensure_ascii=False) + '\n')

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
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description='SWE-bench Pro LLM 评测')
    parser.add_argument('--instance-id', type=str, help='指定任务ID')
    parser.add_argument('--index', type=int, help='任务索引（从0开始）')
    parser.add_argument('--no-validate', action='store_true', help='跳过验证')
    parser.add_argument('--output-dir', default='./swe_bench_output', help='输出目录')
    parser.add_argument('--analysis', action='store_true', help='分析已有结果')
    args = parser.parse_args()

    if args.analysis:
        analyze_results(args.output_dir)
        return

    global ENABLE_VALIDATION
    ENABLE_VALIDATION = not args.no_validate

    if not args.instance_id and args.index is None:
        parser.error("必须指定 --instance-id 或 --index")

    # 加载配置
    try:
        api_config = load_config()
    except Exception as e:
        print(f"✗ 无法读取配置文件 {CONFIG_PATH}: {e}")
        return

    if not api_config or not api_config.get('api_key'):
        print(f"✗ 请检查配置文件 {CONFIG_PATH}")
        return

    print(f"使用模型: {api_config.get('model')}")
    print(f"API地址: {api_config.get('base_url')}")
    print(f"验证模式: {'启用' if ENABLE_VALIDATION else '禁用'}")

    os.makedirs(args.output_dir, exist_ok=True)
    predictions_dir = os.path.join(args.output_dir, 'predictions')
    os.makedirs(predictions_dir, exist_ok=True)

    evaluator = PureLLMEvaluator(api_config=api_config)

    try:
        dataset = evaluator.load_dataset()
        
        # 选择任务
        if args.instance_id:
            instance = None
            for item in dataset:
                if item['instance_id'] == args.instance_id:
                    instance = item
                    break
            if not instance:
                print(f"✗ 未找到任务 {args.instance_id}")
                return
        else:
            if args.index >= len(dataset):
                print(f"✗ 索引超出范围（数据集共 {len(dataset)} 个任务）")
                return
            instance = dataset[args.index]

        instance_id = instance['instance_id']
        print(f"\n开始评测任务: {instance_id}")
        
        result = evaluator.evaluate_single(instance)
        
        # 保存结果
        save_result_harness_format(result, predictions_dir, args.output_dir)
        
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
        print(f"\n✗ 评测失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        evaluator.cleanup()


def save_result_harness_format(result: Dict, predictions_dir: str, output_dir: str):
    """保存为SWE-bench harness格式"""
    instance_id = result['instance_id']
    
    # 保存prediction
    prediction = {
        'instance_id': instance_id,
        'model_patch': result.get('patch', ''),
        'model_name_or_path': 'llm_api',
    }
    pred_file = os.path.join(predictions_dir, f"{instance_id}.json")
    with open(pred_file, 'w') as f:
        json.dump(prediction, f, indent=2, ensure_ascii=False)
    
    # 保存完整结果
    full_result_file = os.path.join(output_dir, f"{instance_id}_full.json")
    with open(full_result_file, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    # 追加到汇总文件
    summary_file = os.path.join(output_dir, 'all_results.jsonl')
    with open(summary_file, 'a') as f:
        f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    print(f"✓ 结果已保存:")
    print(f"  - Prediction: {pred_file}")
    print(f"  - Full result: {full_result_file}")


def analyze_results(output_dir: str):
    """分析评测结果"""
    summary_file = os.path.join(output_dir, 'all_results.jsonl')
    
    if not os.path.exists(summary_file):
        print(f"✗ 未找到结果文件 {summary_file}")
        return
    
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
    
    # 统计
    total = len(results)
    with_patch = [r for r in results if r.get('patch')]
    validated = [r for r in results if r.get('validation') is not None]
    resolved = [r for r in validated if r.get('validation', {}).get('success')]
    
    print(f"\n{'='*70}")
    print(f"SWE-bench Pro 评测结果分析")
    print(f"{'='*70}\n")
    print(f"总任务数: {total}")
    print(f"生成Patch: {len(with_patch)}/{total} ({len(with_patch)/total*100:.1f}%)")
    if validated:
        print(f"已验证: {len(validated)}/{total}")
        print(f"✓ 已解决: {len(resolved)}/{len(validated)} ({len(resolved)/len(validated)*100:.1f}%)")
        print(f"★ Resolved率: {len(resolved)/total*100:.1f}%")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
