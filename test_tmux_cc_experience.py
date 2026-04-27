#!/usr/bin/env python3
"""
SWE-bench Pro 评测 - DUCC 独立版本

完全不依赖 Experience 框架,直接调用 ducc

⚠️  注意: SWE-bench Pro (41 repos, 多语言) 不被官方 swebench.harness 支持
   官方工具只支持原始 SWE-bench (Python repos)
   所以本脚本使用自己的验证逻辑 (--validate)

工作流程:
  1. 从 Docker 容器提取完整代码库
  2. 调用 ducc agent 生成修复 patch  
  3. 保存 patch 为标准格式
  4. (可选) 在容器内验证: git apply + pytest

用法:
  # 单个任务 + 验证
  python test_ducc_standalone.py --index 0 --validate
  
  # 批量处理 (不验证,快速生成patches)
  python test_ducc_standalone.py --max-tasks 10
  
  # 批量处理 + 验证
  python test_ducc_standalone.py --max-tasks 10 --validate
"""

# python convert_to_hf_dataset.py --input /ssd1/Dejavu/datasets/SWE-bench_Pro/test-00000-of-00001.parquet   --output ./swebench_dataset_local

# python -m swebench.harness.run_evaluation --dataset_name ./swebench_dataset_local --split test --predictions_path ./swe_bench_output_ducc/all_preds.jsonl --max_workers 1 --run_id ducc_eval

import os
import sys
import json
import time
import tempfile
import shlex
import subprocess
import shutil
from typing import Dict, List, Optional
import docker
import docker.types

# 配置
LOCAL_DATASET_PATH = os.getenv(
    'SWE_BENCH_DATASET',
    '/ssd1/Dejavu/datasets/SWE-bench_Pro/test-00000-of-00001.parquet'
)

# Docker 镜像仓库前缀 (可通过环境变量覆盖)
# 例如: export DOCKER_IMAGE_PREFIX="aorwall/swe-bench"
# 或者: export DOCKER_IMAGE_PREFIX="" (空字符串表示本地构建的镜像)
# 注意: jefzda/sweap-images 镜像无法执行二进制文件，只能用于提取代码
DOCKER_IMAGE_PREFIX = os.getenv('DOCKER_IMAGE_PREFIX', 'jefzda/sweap-images')

if os.path.exists(LOCAL_DATASET_PATH):
    print(f"✓ 自动检测到本地数据集: {LOCAL_DATASET_PATH}")
else:
    print(f"⚠️  本地数据集不存在: {LOCAL_DATASET_PATH}")
    LOCAL_DATASET_PATH = None

print(f"✓ Docker 镜像前缀: {DOCKER_IMAGE_PREFIX if DOCKER_IMAGE_PREFIX else '(本地构建)'}")

# 默认启用验证 (SWE-bench Pro 无官方评估工具)
ENABLE_VALIDATION = True


def find_ducc_binary() -> str:
    """查找 ducc 或 baidu-cc 二进制文件"""
    # 1. 环境变量
    if os.environ.get("DUCC_BIN"):
        return os.environ["DUCC_BIN"]
    
    # 2. PATH 中查找
    for name in ["ducc", "baidu-cc", "claude-code"]:
        path = shutil.which(name)
        if path:
            print(f"✓ 找到 ducc: {path}")
            return path
    
    # 3. 常见安装位置
    common_paths = [
        os.path.expanduser("~/.comate/extensions/baidu-cc/baidu-cc"),
        "/usr/local/bin/ducc",
        "/usr/local/bin/baidu-cc",
    ]
    for path in common_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            print(f"✓ 找到 ducc: {path}")
            return path
    
    raise FileNotFoundError(
        "找不到 ducc 或 baidu-cc!\n"
        "请安装: bash <(curl -fsSL http://baidu-cc-client.bj.bcebos.com/baidu-cc/install.sh)\n"
        "或设置环境变量: export DUCC_BIN=/path/to/ducc"
    )


class SimpleDuccEvaluator:
    """简化的 DUCC 评估器 - 完全独立"""
    
    def __init__(self):
        self.docker_client = None
        self._container_cache = {}
        self.ducc_bin = find_ducc_binary()
        
    def __del__(self):
        self.cleanup()
    
    def cleanup(self):
        """清理所有容器"""
        for image_tag, container in list(self._container_cache.items()):
            try:
                print(f"清理容器: {image_tag}")
                container.kill()
                container.remove(force=True, v=True)
            except:
                pass
            finally:
                self._container_cache.pop(image_tag, None)
        
        if self.docker_client:
            try:
                self.docker_client.close()
            except:
                pass
    
    def _get_or_create_container(self, image_tag: str):
        """获取或创建 Docker 容器"""
        if image_tag in self._container_cache:
            container = self._container_cache[image_tag]
            try:
                container.reload()
                if container.status == 'running':
                    return container
                else:
                    print(f"容器已停止,重新创建...")
                    container.remove(force=True)
                    del self._container_cache[image_tag]
            except Exception as e:
                # 容器引用失效(比如 Docker daemon 重启)
                print(f"容器引用失效,重新创建: {e}")
                self._container_cache.pop(image_tag, None)
        
        if not self.docker_client:
            self.docker_client = docker.from_env()
            print("✓ Docker 连接成功")
        
        print(f"准备容器: {image_tag}")
        
        # 检查镜像是否存在,不存在则拉取
        try:
            self.docker_client.images.get(image_tag)
            print(f"✓ 本地已有镜像")
        except docker.errors.ImageNotFound:
            print(f"镜像不存在,正在拉取: {image_tag}")
            # 检查是否需要指定 platform
            try:
                info = self.docker_client.info()
                experimental = info.get('ExperimentalBuild', False)
                if experimental:
                    print(f"  使用 platform: linux/amd64")
                    self.docker_client.images.pull(image_tag, platform="linux/amd64")
                else:
                    print(f"  ⚠️  Docker experimental 未启用,无法指定 platform")
                    self.docker_client.images.pull(image_tag)
            except Exception as e:
                print(f"✗ 拉取失败: {e}")
                raise
        
        # 准备容器参数
        # 关键: 使用 sh 作为 entrypoint (镜像默认的 bash 可能有问题)
        container_args = {
            'image': image_tag,
            'command': ["-c", "tail -f /dev/null"],
            'entrypoint': "sh",  # 使用 sh 而不是清空 entrypoint
            'detach': True,
            'remove': False,
            'mem_limit': '8g',
            'cpu_quota': 400000,  # 4 CPUs
            'stdin_open': True,
            'tty': True,
            'privileged': True,
            'security_opt': ['seccomp=unconfined'],
            'ulimits': [
                docker.types.Ulimit(name='nproc', soft=65535, hard=65535),
                docker.types.Ulimit(name='nofile', soft=65535, hard=65535),
            ],
        }
        
        # Docker API >= 1.41 且启用 experimental 才支持 platform 参数
        try:
            api_version = self.docker_client.api.api_version
            # 检查是否支持 platform (需要 experimental features)
            info = self.docker_client.info()
            experimental = info.get('ExperimentalBuild', False)
            
            if tuple(map(int, api_version.split('.'))) >= (1, 41) and experimental:
                container_args['platform'] = "linux/amd64"
                print(f"  使用 platform: linux/amd64 (experimental 已启用)")
            else:
                print(f"  ⚠️  Docker experimental 未启用,跳过 platform 参数")
                print(f"     如需多架构支持,请启用: experimental=true in /etc/docker/daemon.json")
        except Exception as e:
            print(f"  ⚠️  无法检测 platform 支持: {e}")
            # 继续运行,不设置 platform
        
        container = self.docker_client.containers.run(**container_args)
        self._container_cache[image_tag] = container
        
        # 等待启动
        max_retries = 10
        for i in range(max_retries):
            time.sleep(1)
            container.reload()
            if container.status == 'running':
                print(f"✓ 容器已启动")
                return container
        
        # 超时后打印诊断信息
        container.reload()
        raise RuntimeError(f"容器启动超时 (状态: {container.status}, ID: {container.id[:12]})")
    
    def load_dataset(self):
        """加载数据集"""
        if LOCAL_DATASET_PATH and LOCAL_DATASET_PATH.endswith('.parquet'):
            from datasets import load_dataset as hf_load
            dataset = hf_load('parquet', data_files=LOCAL_DATASET_PATH)['train']
            print(f"✓ 数据集加载完成: {len(dataset)} 个任务")
            return dataset
        raise RuntimeError("未找到数据集")
    
    def extract_codebase(self, instance: Dict) -> str:
        """从容器提取整个代码库到本地目录,返回 workdir 路径"""
        # 构建完整镜像标签
        if DOCKER_IMAGE_PREFIX:
            image_tag = f"{DOCKER_IMAGE_PREFIX}:{instance['dockerhub_tag']}"
        else:
            # 空前缀表示使用本地构建的镜像,直接使用 dockerhub_tag
            image_tag = instance['dockerhub_tag']
        
        container = self._get_or_create_container(image_tag)
        
        # 检测工作目录 (优先 /app)
        # 注意: jefzda/sweap-images 镜像无法执行命令，所以直接尝试提取
        workdir = None
        for candidate in ['/app', '/testbed']:
            try:
                # 尝试获取目录信息 (不执行命令)
                bits, stat = container.get_archive(candidate)
                # 如果成功，说明目录存在
                workdir = candidate
                print(f"✓ 容器工作目录: {workdir}")
                # 清理这次试探性的数据流
                for _ in bits:
                    pass
                break
            except Exception:
                continue
        
        if not workdir:
            workdir = '/app'
            print(f"⚠️  使用默认工作目录: {workdir}")
        
        # 创建临时目录准备接收代码
        import tempfile
        tmpdir = tempfile.mkdtemp(prefix='swe_bench_')
        local_workspace = os.path.join(tmpdir, 'workspace')
        os.makedirs(local_workspace, exist_ok=True)
        
        print(f"正在提取整个代码库...")
        print(f"  容器路径: {workdir}")
        print(f"  本地路径: {local_workspace}")
        
        # 使用 docker API 直接提取目录
        try:
            import tarfile
            import io
            
            # get_archive 直接返回 tar 流 (不是 gzip)
            bits, stat = container.get_archive(workdir)
            
            # 写入临时文件
            tar_path = os.path.join(tmpdir, 'codebase.tar')
            with open(tar_path, 'wb') as f:
                for chunk in bits:
                    f.write(chunk)
            
            # 解压到 workspace (使用 data filter 兼容 Python 3.14+)
            with tarfile.open(tar_path, 'r') as tar:
                # 使用 data filter 防止路径遍历等安全问题
                tar.extractall(local_workspace, filter='data')
            
            # 清理临时文件
            os.remove(tar_path)
            
            # 统计文件数
            file_count = sum(len(files) for _, _, files in os.walk(local_workspace))
            print(f"✓ 提取完成: {file_count} 个文件")
            
            return local_workspace, workdir, tmpdir
            
        except Exception as e:
            print(f"✗ 提取失败: {e}")
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise
    
    def call_ducc(self, prompt: str, workspace: str, timeout: int = 600) -> str:
        """直接调用 ducc
        
        Args:
            prompt: 任务描述
            workspace: 工作目录
            timeout: 超时时间（秒），默认600秒（10分钟）
        """
        print(f"\n正在调用 ducc...")
        print(f"  二进制: {self.ducc_bin}")
        print(f"  工作目录: {workspace}")
        print(f"  超时设置: {timeout}秒")
        print(f"  prompt: {prompt}")
        
        # 构建命令
        cmd = [
            self.ducc_bin,
            "-p", prompt,
            "--allowedTools", "Read,Edit,Write",
        ]
        
        # 权限模式: 尽量自动批准,避免等待确认
        # 检查 ducc 是否支持 --auto-approve 或类似参数
        if os.geteuid() != 0:
            # 非 root: 使用 bypassPermissions
            cmd.extend(["--permission-mode", "bypassPermissions"])
            print("  权限模式: bypassPermissions (自动批准)")
        else:
            # root 用户不能用 bypassPermissions
            # 方案 1: 设置环境变量强制非交互
            print("  权限模式: 默认 (root 用户)")
            print("  ⚠️  注意: 如果 ducc 询问确认,可能会超时")
        
        # 准备环境变量(强制非交互模式)
        env = os.environ.copy()
        env['DUCC_AUTO_APPROVE'] = '1'  # 如果 ducc 支持这个环境变量
        env['CI'] = 'true'               # 很多工具检测 CI 环境会跳过交互
        
        try:
            # 执行 ducc
            print(f"  开始时间: {time.strftime('%H:%M:%S')}")
            result = subprocess.run(
                cmd,
                cwd=workspace,
                env=env,                    # ← 传递环境变量
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                input='y\n' * 100,          # ← 预先输入100个 'y',自动确认 (会自动设置 stdin=PIPE)
            )
            print(f"  完成时间: {time.strftime('%H:%M:%S')}")
            
            if result.returncode != 0:
                print(f"⚠️  ducc 返回非零退出码: {result.returncode}")
                print(f"stderr: {result.stderr[:500]}")
                # 即使失败也返回 stdout,可能有部分输出
            
            output = result.stdout
            if not output and result.returncode != 0:
                print(f"✗ ducc 执行失败且无输出")
                print(f"  可能原因:")
                print(f"    1. 缺少语言环境 (如 node, python, go 等)")
                print(f"    2. ducc 崩溃或权限问题")
                print(f"    3. 工作目录问题")
            else:
                print(f"✓ ducc 执行完成,输出长度: {len(output)} 字符")
            
            return output
        
        except subprocess.TimeoutExpired:
            print(f"✗ ducc 执行超时 ({timeout}秒 = {timeout//60}分钟)")
            print(f"  可能原因:")
            print(f"    1. DUCC 在等待用户输入")
            print(f"    2. 任务过于复杂")
            print(f"    3. 某个子进程卡住")
            print(f"  建议: 增加 timeout 参数或检查 DUCC 日志")
            return ""
        except Exception as e:
            print(f"✗ ducc 执行失败: {e}")
            return ""
    
    def evaluate_single(self, instance: Dict) -> Dict:
        """评估单个任务"""
        instance_id = instance['instance_id']
        
        print(f"\n{'='*60}")
        print(f"处理任务: {instance_id}")
        print(f"{'='*60}")
        
        start_time = time.time()
        tmpdir_to_cleanup = None
        
        try:
            # 1. 提取整个代码库到本地
            print("正在提取代码库...")
            workspace, container_workdir, tmpdir_to_cleanup = self.extract_codebase(instance)
            
            # 2. 构建简化的 prompt (agent 可以自己探索代码)
            prompt = self._build_prompt(instance)
            
            # 3. 调用 ducc (agent 在 workspace 目录操作)
            output = self.call_ducc(prompt, workspace)
            
            if not output:
                return {
                    'instance_id': instance_id,
                    'patch': '',
                    'error': 'ducc returned empty output',
                    'validation': {'success': False, 'error': 'Empty output'}
                }
            
            # 4. 提取 patch
            patch = self._extract_patch(output)
            
            duration = time.time() - start_time
            print(f"\n✓ 处理完成: {duration:.2f}s")
            print(f"  Patch 长度: {len(patch)} 字符")
            
            # 检查 patch 是否有效
            has_valid_patch = 'diff --git' in patch or '@@' in patch
            if not has_valid_patch and patch:
                print(f"  ⚠️  警告: 提取的内容不像有效的 patch")
                print(f"  前200字符: {patch[:200]}")
            
            if patch:
                print(f"\nPatch 预览:")
                print("-" * 60)
                print(patch[:300])
                if len(patch) > 300:
                    print(f"... (还有 {len(patch) - 300} 字符)")
                print("-" * 60)
            else:
                print(f"\n✗ 未生成 patch!")
                print(f"DUCC 输出前500字符:")
                print(output[:500])
            
            # 5. 验证 patch
            validation_result = {}
            if ENABLE_VALIDATION and patch:
                print("\n正在验证 patch...")
                validation_result = self.validate_patch(instance, patch, container_workdir)
                print(f"验证结果: {'✓ 通过' if validation_result.get('success') else '✗ 失败'}")
            
            return {
                'instance_id': instance_id,
                'patch': patch,
                'duration': duration,
                'validation': validation_result,
            }
        
        finally:
            # 清理临时目录
            if tmpdir_to_cleanup:
                import shutil
                shutil.rmtree(tmpdir_to_cleanup, ignore_errors=True)
    
    def _build_prompt(self, instance: Dict) -> str:
        """构建 prompt (agent 可以自己探索代码,不需要提供文件列表)"""
        requirements = f"\n## Requirements\n{instance['requirements']}\n" if instance.get('requirements') else ""
        interface = f"\n## Interface\n{instance['interface']}\n" if instance.get('interface') else ""
        
        return f"""You are a software engineer fixing a bug. The codebase is in the current directory.

## Problem Statement
{instance['problem_statement']}
{requirements}{interface}

## Task
1. Explore the codebase in the current directory to understand the structure
2. Locate the relevant files related to this issue
3. Generate a patch that fixes the issue with minimal, targeted changes
4. Output the patch in unified diff format

## Output Format
Output the patch in unified diff format:
```diff
diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -10,5 +10,5 @@ def func():
-    old_line
+    new_line
```

Generate the patch now."""
    
    def _extract_patch(self, output: str) -> str:
        """从 ducc 输出提取 patch"""
        # 1. 尝试提取 markdown 代码块中的 diff
        if '```diff' in output:
            start = output.find('```diff') + 7
            end = output.find('```', start)
            if end > start:
                return output[start:end].strip()
        
        # 2. 清理 XML 标签 (移除 <think>, <minimax:tool_call> 等)
        import re
        # 移除所有 XML 标签
        cleaned = re.sub(r'<[^>]+>', '', output)
        
        # 3. 查找 diff --git 开头的内容
        if 'diff --git' in cleaned:
            # 找到第一个 diff --git 的位置
            diff_start = cleaned.find('diff --git')
            patch_content = cleaned[diff_start:]
            
            # 可选: 清理 patch 后面的无关内容 (比如多余的解释)
            # 但保留完整的 diff 内容
            return patch_content.strip()
        
        # 4. 如果没有找到标准 diff,返回清理后的内容
        return cleaned.strip()
    
    def validate_patch(self, instance: Dict, patch: str, workdir: str) -> Dict:
        """验证 patch (详细日志版本)"""
        print(f"\n{'='*70}")
        print(f"📋 开始验证 Patch")
        print(f"{'='*70}")
        print(f"Instance ID: {instance['instance_id']}")
        print(f"Repo: {instance.get('repo', 'N/A')}")
        print(f"Language: {instance.get('repo_language', 'N/A')}")
        print(f"Work Dir: {workdir}")

        # 构建完整镜像标签
        if DOCKER_IMAGE_PREFIX:
            image_tag = f"{DOCKER_IMAGE_PREFIX}:{instance['dockerhub_tag']}"
        else:
            image_tag = instance['dockerhub_tag']
        
        print(f"\n查找容器缓存...")
        print(f"  Image tag: {image_tag}")
        print(f"  缓存中的容器数: {len(self._container_cache)}")
        print(f"  缓存的 tags: {list(self._container_cache.keys())}")
        
        container = self._container_cache.get(image_tag)
        
        if not container:
            print(f"✗ 容器未找到: {image_tag}")
            print(f"  这意味着 extract_codebase 没有正确缓存容器")
            return {'success': False, 'error': 'Container not found in cache'}
        
        print(f"✓ 使用容器: {container.id[:12]}")
        print(f"  容器对象类型: {type(container)}")
        print(f"  容器镜像: {container.image.tags if hasattr(container.image, 'tags') else 'N/A'}")
        
        try:
            # 0. 检查容器状态和环境
            print(f"\n[0/6] 检查容器环境...")
            try:
                container.reload()
                print(f"  容器状态: {container.status}")
                if container.status != 'running':
                    return {'success': False, 'error': f'Container not running: {container.status}'}
            except Exception as e:
                print(f"  ✗ 容器状态检查失败: {str(e)}")
                return {'success': False, 'error': f'Container reload failed: {str(e)}'}
            
            # 检查工作目录
            result = container.exec_run(f"test -d {workdir}")
            if result.exit_code != 0:
                print(f"  ✗ 工作目录不存在: {workdir}")
                return {'success': False, 'error': f'Workdir not found: {workdir}'}
            print(f"  ✓ 工作目录存在: {workdir}")
            
            # 检查是否有 git
            result = container.exec_run("which git")
            has_git = result.exit_code == 0
            if has_git:
                git_path = result.output.decode().strip()
                print(f"  ✓ Git 可用: {git_path}")
                
                # 检查是否是 git 仓库
                result = container.exec_run(f"test -d {workdir}/.git")
                is_git_repo = result.exit_code == 0
                if is_git_repo:
                    print(f"  ✓ Git 仓库: {workdir}/.git")
                    # 查看 git 状态
                    result = container.exec_run(f"git -C {workdir} status --short")
                    if result.exit_code == 0:
                        git_status = result.output.decode().strip()
                        print(f"  Git 状态: {git_status if git_status else '(clean)'}")
                else:
                    print(f"  ⚠️  不是 git 仓库,跳过 git 操作")
                    has_git = False
            else:
                print(f"  ⚠️  Git 不可用,将跳过 git 相关操作")
            
            # 1. 重置代码库 (如果有 git)
            if has_git and is_git_repo:
                print(f"\n[1/6] 重置代码库 (git reset)...")
                reset_cmd = f"git reset --hard HEAD && git clean -fdx"
                print(f"  执行: cd {workdir} && {reset_cmd}")
                result = container.exec_run(reset_cmd, workdir=workdir)
                print(f"  退出码: {result.exit_code}")
                reset_output = result.output.decode()
                if reset_output:
                    print(f"  输出: {reset_output[:500]}")
                
                if result.exit_code != 0:
                    print(f"  ⚠️  重置失败,但继续: {reset_output[:200]}")
                else:
                    print(f"  ✓ 重置成功")
            else:
                print(f"\n[1/6] 跳过 git 重置 (无 git 或非 git 仓库)")
            
            # 2. 保存原始文件 (备份,用于非 git 场景)
            print(f"\n[2/6] 准备应用 patch...")
            if not has_git:
                print(f"  创建备份目录...")
                result = container.exec_run(f"cp -r {workdir} /tmp/backup_code")
                if result.exit_code == 0:
                    print(f"  ✓ 备份完成: /tmp/backup_code")
                else:
                    print(f"  ⚠️  备份失败,继续")
            
            # 3. 写入 patch
            print(f"\n[3/6] 写入 patch 文件...")
            write_cmd = f"cat > /tmp/fix.patch << 'EOF'\n{patch}\nEOF"
            print(f"  Patch 长度: {len(patch)} 字符")
            print(f"  Patch 预览 (前 300 字符):")
            for line in patch[:300].split('\n'):
                print(f"    {line}")
            
            result = container.exec_run(['sh', '-c', write_cmd])
            if result.exit_code != 0:
                print(f"  ✗ 写入失败 (exit_code={result.exit_code})")
                return {'success': False, 'error': 'Failed to write patch'}
            
            # 验证文件写入
            result = container.exec_run("wc -l /tmp/fix.patch")
            if result.exit_code == 0:
                print(f"  ✓ Patch 已写入: {result.output.decode().strip()}")
            else:
                print(f"  ✓ 写入成功")
            
            # 4. 应用 patch
            print(f"\n[4/6] 应用 patch...")
            
            if has_git and is_git_repo:
                # 使用 git apply
                check_cmd = "git apply --check /tmp/fix.patch 2>&1"
                print(f"  检查: cd {workdir} && {check_cmd}")
                result = container.exec_run(check_cmd, workdir=workdir)
                check_output = result.output.decode()
                print(f"  检查退出码: {result.exit_code}")
                if check_output:
                    print(f"  检查输出: {check_output[:500]}")
                
                apply_cmd = "git apply /tmp/fix.patch 2>&1"
                print(f"  应用: cd {workdir} && {apply_cmd}")
                result = container.exec_run(apply_cmd, workdir=workdir)
                print(f"  应用退出码: {result.exit_code}")
                apply_output = result.output.decode()
                if apply_output:
                    print(f"  应用输出: {apply_output[:500]}")
                
                if result.exit_code != 0:
                    print(f"  ✗ git apply 失败,尝试 patch 命令")
                    # 尝试 patch 命令
                    result = container.exec_run("patch -p1 < /tmp/fix.patch 2>&1", workdir=workdir)
                    if result.exit_code != 0:
                        print(f"  ✗ patch 命令也失败")
                        return {'success': False, 'error': f'Apply failed: {apply_output[:500]}'}
                
                # 查看改动
                result = container.exec_run(f"git -C {workdir} diff --stat")
                if result.exit_code == 0:
                    diff_stat = result.output.decode().strip()
                    if diff_stat:
                        print(f"  ✓ 应用成功,改动:")
                        for line in diff_stat.split('\n')[:10]:
                            print(f"    {line}")
                    else:
                        print(f"  ✓ 应用成功 (git diff 无输出)")
            else:
                # 没有 git,使用 patch 命令
                print(f"  使用 patch 命令 (无 git)")
                patch_cmd = "patch -p1 < /tmp/fix.patch 2>&1"
                print(f"  执行: cd {workdir} && {patch_cmd}")
                result = container.exec_run(patch_cmd, workdir=workdir)
                print(f"  退出码: {result.exit_code}")
                patch_output = result.output.decode()
                if patch_output:
                    print(f"  输出: {patch_output[:500]}")
                
                if result.exit_code != 0:
                    print(f"  ✗ patch 失败")
                    return {'success': False, 'error': f'Patch failed: {patch_output[:500]}'}
                print(f"  ✓ patch 成功")
            
            # 5. 检测测试命令
            print(f"\n[5/6] 检测测试环境...")
            repo_lang = instance.get('repo_language', 'Python').lower()
            
            if 'javascript' in repo_lang or 'js' in repo_lang or 'node' in repo_lang:
                # JavaScript/Node.js 项目
                result = container.exec_run("test -f package.json", workdir=workdir)
                if result.exit_code == 0:
                    print(f"  ✓ 检测到 Node.js 项目 (package.json)")
                    # 检查 test script
                    result = container.exec_run("cat package.json | grep '\"test\"'", workdir=workdir)
                    if result.exit_code == 0:
                        test_script = result.output.decode().strip()
                        print(f"    Test script: {test_script}")
                    test_cmd = "npm test"
                else:
                    print(f"  ⚠️  未找到 package.json,使用默认命令")
                    test_cmd = "npm test"
            else:
                # Python 项目
                result = container.exec_run("which pytest", workdir=workdir)
                if result.exit_code == 0:
                    pytest_path = result.output.decode().strip()
                    print(f"  ✓ 检测到 pytest: {pytest_path}")
                    # 禁用 faulthandler 避免容器内线程限制问题
                    test_cmd = "python -m pytest -xvs -p no:faulthandler"
                else:
                    print(f"  ⚠️  pytest 不可用,使用 unittest")
                    test_cmd = "python -m unittest discover -v"
            
            print(f"  测试命令: {test_cmd}")
            
            # 6. 运行测试
            print(f"\n[6/6] 运行测试...")
            full_test_cmd = f"cd {workdir} && {test_cmd}"
            print(f"  执行: {full_test_cmd}")
            print(f"  超时: 300秒")
            print(f"  开始时间: {time.strftime('%H:%M:%S')}")
            
            test_start = time.time()
            result = container.exec_run(test_cmd, workdir=workdir, timeout=300)
            test_duration = time.time() - test_start
            test_output = result.output.decode()
            
            print(f"  结束时间: {time.strftime('%H:%M:%S')}")
            print(f"  运行时长: {test_duration:.2f}秒")
            
            print(f"\n{'='*70}")
            print(f"📊 测试结果")
            print(f"{'='*70}")
            print(f"退出码: {result.exit_code}")
            print(f"输出长度: {len(test_output)} 字符")
            
            # 分析测试输出
            passed = test_output.count('PASSED') + test_output.count(' passed')
            failed = test_output.count('FAILED') + test_output.count(' failed')
            errors = test_output.count('ERROR')
            
            print(f"\n测试统计:")
            print(f"  PASSED: {passed}")
            print(f"  FAILED: {failed}")
            print(f"  ERROR: {errors}")
            
            print(f"\n完整输出:")
            print("-" * 70)
            print(test_output)
            print("-" * 70)
            
            # 判断成功
            success = result.exit_code == 0 and failed == 0
            
            print(f"\n{'='*70}")
            if success:
                print(f"✅ 验证通过!")
                print(f"   - 退出码: 0")
                print(f"   - 失败测试: 0")
            else:
                print(f"❌ 验证失败!")
                if result.exit_code != 0:
                    print(f"   - 退出码非零: {result.exit_code}")
                if failed > 0:
                    print(f"   - 失败测试: {failed}")
                if errors > 0:
                    print(f"   - 错误: {errors}")
            print(f"{'='*70}")
            
            return {
                'success': success,
                'test_output': test_output,
                'exit_code': result.exit_code,
                'test_duration': test_duration,
                'stats': {
                    'passed': passed,
                    'failed': failed,
                    'errors': errors,
                }
            }
        
        except Exception as e:
            print(f"\n✗ 验证异常: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}


def save_result(result: Dict, output_dir: str):
    """保存结果 (兼容官方 SWE-bench 评估格式)"""
    os.makedirs(output_dir, exist_ok=True)
    predictions_dir = os.path.join(output_dir, 'predictions')
    os.makedirs(predictions_dir, exist_ok=True)
    
    instance_id = result['instance_id']
    
    # 官方格式: 单个预测 (用于调试)
    prediction = {
        'instance_id': instance_id,
        'model_patch': result.get('patch', ''),
        'model_name_or_path': 'ducc_standalone',
    }
    with open(os.path.join(predictions_dir, f"{instance_id}.json"), 'w') as f:
        json.dump(prediction, f, indent=2)
    
    # 官方格式: JSONL (用于批量评估)
    with open(os.path.join(output_dir, 'all_preds.jsonl'), 'a') as f:
        f.write(json.dumps(prediction) + '\n')
    
    # 完整结果 (包含 validation 等额外信息)
    with open(os.path.join(output_dir, f"{instance_id}_full.json"), 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"✓ 结果已保存到 {output_dir}")


def generate_report(results: list, output_dir: str):
    """生成报告"""
    if not results:
        return
    
    resolved = [r for r in results if r.get('validation', {}).get('success')]
    
    report = {
        'total_instances': len(results),
        'resolved_instances': len(resolved),
        'resolve_rate': round(len(resolved) / len(results), 4),
        'resolved': [r['instance_id'] for r in resolved],
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'model': 'ducc_standalone'
    }
    
    with open(os.path.join(output_dir, 'report.json'), 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n{'='*70}")
    print(f"📊 评测报告")
    print(f"{'='*70}")
    print(f"Total: {len(results)}")
    print(f"Resolved: {len(resolved)} ({len(resolved)/len(results)*100:.1f}%)")
    print(f"{'='*70}\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='SWE-bench Pro DUCC 评测 (无 Experience 依赖, 无官方评估工具支持)',
        epilog="""
说明:
  SWE-bench Pro 包含41个多语言仓库,官方 swebench.harness 不支持
  本脚本使用自己的验证逻辑 (在 Docker 容器内 git apply + 运行测试)
  
推荐工作流程:
  1. 快速生成 patches (不验证):
     python test_ducc_standalone.py --max-tasks 100
     
  2. 完整评估 (包含验证):
     python test_ducc_standalone.py --max-tasks 100 --validate
     
  3. 查看结果:
     cat swe_bench_output_ducc/report.json
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--index', type=int, help='任务索引')
    parser.add_argument('--max-tasks', type=int, help='最多处理 N 个任务')
    parser.add_argument('--no-validate', action='store_true', 
                       help='跳过验证 (默认启用验证)')
    parser.add_argument('--output-dir', default='./swe_bench_output_ducc', help='输出目录')
    args = parser.parse_args()
    
    global ENABLE_VALIDATION
    ENABLE_VALIDATION = not args.no_validate
    
    if args.index is None and not args.max_tasks:
        parser.error("必须指定 --index 或 --max-tasks")
    
    # 检查输出目录
    if os.path.exists(args.output_dir):
        # 检查是否有旧的 all_results.jsonl (旧版本)
        old_file = os.path.join(args.output_dir, 'all_results.jsonl')
        new_file = os.path.join(args.output_dir, 'all_preds.jsonl')
        if os.path.exists(old_file) and not os.path.exists(new_file):
            print(f"⚠️  检测到旧版本输出,建议清理: rm -rf {args.output_dir}")
        
        # 警告: all_preds.jsonl 已存在,会追加
        if os.path.exists(new_file):
            import time
            backup_file = new_file + f'.backup_{int(time.time())}'
            print(f"⚠️  检测到已有结果文件: {new_file}")
            print(f"   备份为: {backup_file}")
            print(f"   如需重新开始,请删除输出目录: rm -rf {args.output_dir}")
            shutil.copy(new_file, backup_file)
    
    print(f"使用模型: DUCC (独立版,无 Experience 依赖)")
    print(f"数据集: SWE-bench Pro (41 repos, 多语言)")
    print(f"输出目录: {args.output_dir}")
    print(f"验证模式: {'启用' if ENABLE_VALIDATION else '禁用'}")
    if not ENABLE_VALIDATION:
        print("⚠️  跳过验证,只生成 patches")
    print()
    
    evaluator = SimpleDuccEvaluator()
    
    try:
        dataset = evaluator.load_dataset()
        
        # 选择任务
        if args.index is not None:
            instances = [dataset[args.index]]
        else:
            max_tasks = min(args.max_tasks, len(dataset))
            instances = [dataset[i] for i in range(max_tasks)]
        
        print(f"\n将处理 {len(instances)} 个任务")
        
        # 处理
        results = []
        for idx, instance in enumerate(instances, 1):
            print(f"\n{'='*70}")
            print(f"[{idx}/{len(instances)}] {instance['instance_id']}")
            print(f"{'='*70}")
            
            try:
                result = evaluator.evaluate_single(instance)
                results.append(result)
                save_result(result, args.output_dir)
            except Exception as e:
                print(f"✗ 失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 报告
        if len(instances) > 1:
            generate_report(results, args.output_dir)
    
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n✗ 失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        evaluator.cleanup()


if __name__ == "__main__":
    main()
