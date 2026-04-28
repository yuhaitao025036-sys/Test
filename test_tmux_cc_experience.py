#!/usr/bin/env python3
"""
SWE-bench Pro 评测 - DUCC 独立版本 (支持 tmux 模式)

完全不依赖 Experience 框架,直接调用 ducc

⚠️  注意: SWE-bench Pro (41 repos, 多语言) 不被官方 swebench.harness 支持
   官方工具只支持原始 SWE-bench (Python repos)
   所以本脚本使用自己的验证逻辑 (--validate)

工作流程:
  1. 从 Docker 容器提取完整代码库
  2. 调用 ducc agent 生成修复 patch (支持直接模式和tmux模式)
  3. 保存 patch 为标准格式
  4. (可选) 在容器内验证: git apply + pytest

用法:
  # 直接模式 - 单个任务 + 验证
  python test_tmux_cc_experience.py --index 0 --validate
  
  # tmux 模式 - 可实时查看执行过程
  python test_tmux_cc_experience.py --index 0 --use-tmux --no-validate
  # 然后在另一个终端: tmux attach -t swe_bench_<instance_id>
  
  # 批量处理 (不验证,快速生成patches)
  python test_tmux_cc_experience.py --max-tasks 2 --no-validate
  
  # 批量处理 + 验证 + tmux模式
  python test_tmux_cc_experience.py --max-tasks 2 --use-tmux
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
    
    def __init__(self, use_tmux=False, timeout=1800):
        self.docker_client = None
        self._container_cache = {}
        self.ducc_bin = find_ducc_binary()
        self.use_tmux = use_tmux
        self.timeout = timeout
        
    def __del__(self):
        self.cleanup()
    
    def _copy_claude_session_trace(self, workspace: str, task_dir: str, start_time: float):
        """查找并复制 Claude/ducc 的 session 轨迹到任务目录
        
        Args:
            workspace: ducc 运行的工作目录
            task_dir: 任务目录
            start_time: 任务开始时间（用于过滤最近的 session）
        """
        try:
            import glob
            
            # Claude session 保存在 ~/.claude/projects/ 下
            claude_projects_dir = os.path.expanduser("~/.claude/projects")
            if not os.path.exists(claude_projects_dir):
                print(f"  ⚠️  未找到 Claude projects 目录: {claude_projects_dir}")
                return
            
            # 根据 workspace 路径生成 project hash（简化版：查找包含相关路径的目录）
            workspace_basename = os.path.basename(workspace)
            
            # 查找最近创建/修改的 session 文件（在任务开始时间之后）
            all_sessions = []
            for project_dir in glob.glob(os.path.join(claude_projects_dir, "*")):
                if not os.path.isdir(project_dir):
                    continue
                
                for session_file in glob.glob(os.path.join(project_dir, "*.jsonl")):
                    # 检查文件修改时间是否在任务时间范围内
                    file_mtime = os.path.getmtime(session_file)
                    # 允许一些时间误差（前后5分钟）
                    if file_mtime >= start_time - 300 and file_mtime <= time.time() + 60:
                        all_sessions.append({
                            'path': session_file,
                            'mtime': file_mtime,
                            'size': os.path.getsize(session_file),
                            'project_dir': project_dir
                        })
            
            if not all_sessions:
                print(f"  ⚠️  未找到对应的 Claude session（时间范围: {time.strftime('%H:%M:%S', time.localtime(start_time))} - 现在）")
                return
            
            # 按修改时间排序，取最近的一个
            all_sessions.sort(key=lambda x: x['mtime'], reverse=True)
            latest_session = all_sessions[0]
            
            # 复制到任务目录
            session_dest = os.path.join(task_dir, 'claude_session.jsonl')
            shutil.copy2(latest_session['path'], session_dest)
            
            # 也保存 session 元信息
            session_info = {
                'original_path': latest_session['path'],
                'project_dir': latest_session['project_dir'],
                'modified_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest_session['mtime'])),
                'file_size_bytes': latest_session['size'],
                'workspace': workspace,
            }
            
            session_info_file = os.path.join(task_dir, 'claude_session_info.json')
            with open(session_info_file, 'w', encoding='utf-8') as f:
                json.dump(session_info, f, indent=2)
            
            print(f"  ✓ Claude session 轨迹已复制: claude_session.jsonl")
            print(f"    原始位置: {latest_session['path']}")
            print(f"    文件大小: {latest_session['size']/1024:.1f} KB")
            
            # 生成可读的摘要
            try:
                summary_lines = []
                with open(session_dest, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            event = json.loads(line)
                            event_type = event.get('type', 'unknown')
                            summary_lines.append(event_type)
                        except:
                            continue
                
                # 统计事件类型
                from collections import Counter
                event_counts = Counter(summary_lines)
                
                summary_file = os.path.join(task_dir, 'claude_session_summary.txt')
                with open(summary_file, 'w', encoding='utf-8') as f:
                    f.write("=" * 80 + "\n")
                    f.write("Claude Session 轨迹摘要\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(f"Session 文件: claude_session.jsonl\n")
                    f.write(f"总事件数: {len(summary_lines)}\n\n")
                    f.write("事件类型统计:\n")
                    for event_type, count in event_counts.most_common():
                        f.write(f"  {event_type:20s}: {count:5d}\n")
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("查看完整轨迹:\n")
                    f.write("  cat claude_session.jsonl | jq\n")
                    f.write("  cat claude_session.jsonl | jq -r '.type' | sort | uniq -c\n")
                    f.write("  cat claude_session.jsonl | jq 'select(.type==\"tool_use\")'\n")
                
                print(f"  ✓ Session 摘要已生成: claude_session_summary.txt")
                
            except Exception as e:
                print(f"  ⚠️  生成 session 摘要失败: {e}")
            
        except Exception as e:
            print(f"  ⚠️  复制 Claude session 失败: {e}")
            import traceback
            traceback.print_exc()
    
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
        # 使用 /ssd1/Dejavu/tmp 避免 /tmp 空间不足
        custom_tmp_dir = '/ssd1/Dejavu/tmp'
        os.makedirs(custom_tmp_dir, exist_ok=True)
        tmpdir = tempfile.mkdtemp(prefix='swe_bench_', dir=custom_tmp_dir)
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
    
    def call_ducc(self, prompt: str, workspace: str, timeout: int = 1800, use_tmux: bool = False, instance_id: str = "", task_dir: str = "") -> str:
        """调用 ducc - 支持直接调用和tmux模式
        
        Args:
            prompt: 任务描述
            workspace: 工作目录
            timeout: 超时时间（秒），默认600秒（10分钟）
            use_tmux: 是否使用tmux模式运行
            instance_id: 任务ID，用于生成tmux session名称
            task_dir: 任务输出目录，用于保存日志
        """
        print(f"\n正在调用 ducc...")
        print(f"  二进制: {self.ducc_bin}")
        print(f"  工作目录: {workspace}")
        print(f"  超时设置: {timeout}秒")
        print(f"  运行模式: {'tmux模式' if use_tmux else '直接模式'}")
        print(f"  prompt 长度: {len(prompt)} 字符")
        
        # 保存完整 prompt 到文件
        if task_dir:
            prompt_file = os.path.join(task_dir, 'prompt.txt')
            try:
                with open(prompt_file, 'w', encoding='utf-8') as f:
                    f.write(prompt)
                print(f"  ✓ Prompt 已保存: {prompt_file}")
            except Exception as e:
                print(f"  ⚠️  保存 prompt 失败: {e}")
        
        # 打印 prompt 预览
        lines = prompt.split('\n')
        print(f"  Prompt 预览 (前5行):")
        for i, line in enumerate(lines[:5], 1):
            print(f"    {i}. {line[:80]}{'...' if len(line) > 80 else ''}")
        if len(lines) > 5:
            print(f"    ... (共 {len(lines)} 行)")
        
        if use_tmux:
            # 使用tmux模式
            return self._call_ducc_tmux(prompt, workspace, timeout, instance_id, task_dir)
        else:
            # 直接调用模式（原有逻辑）
            return self._call_ducc_direct(prompt, workspace, timeout, task_dir)
    
    def _call_ducc_direct(self, prompt: str, workspace: str, timeout: int, task_dir: str = "") -> str:
        """直接调用 ducc（原有实现）"""
        # 构建命令
        cmd = [
            self.ducc_bin,
            "-p", prompt,
            "--allowedTools", "Read,Edit,Write",
        ]
        
        # 权限模式: 尽量自动批准,避免等待确认
        if os.geteuid() != 0:
            cmd.extend(["--permission-mode", "bypassPermissions"])
            print("  权限模式: bypassPermissions (自动批准)")
        else:
            print("  权限模式: 默认 (root 用户)")
            print("  ⚠️  注意: 如果 ducc 询问确认,可能会超时")
        
        # 准备环境变量(强制非交互模式)
        env = os.environ.copy()
        env['DUCC_AUTO_APPROVE'] = '1'
        env['CI'] = 'true'
        
        # 准备日志文件
        log_file = None
        debug_file = None
        if task_dir:
            log_file = os.path.join(task_dir, 'ducc_execution.log')
            debug_file = os.path.join(task_dir, 'ducc_debug.log')
            # 添加 --debug-file 参数，保存详细的调试信息
            cmd.extend(["--debug-file", debug_file])
            print(f"  Debug 日志: {debug_file}")
        
        try:
            print(f"  开始时间: {time.strftime('%H:%M:%S')}")
            start_time = time.time()
            
            # ✨ 改进：实时保存日志，防止中途崩溃丢失
            if log_file:
                # 预先写入日志头
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write("=" * 80 + "\n")
                    f.write("DUCC 执行日志（实时保存）\n")
                    f.write("=" * 80 + "\n")
                    f.write(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}\n")
                    f.write(f"工作目录: {workspace}\n")
                    f.write(f"命令: {' '.join(cmd)}\n")
                    f.write("=" * 80 + "\n\n")
                    f.write("执行中...\n\n")
                
                # 使用 tee 方式实时保存：同时捕获到变量和文件
                stdout_file = log_file + '.stdout.tmp'
                stderr_file = log_file + '.stderr.tmp'
                
                with open(stdout_file, 'w', encoding='utf-8') as stdout_f, \
                     open(stderr_file, 'w', encoding='utf-8') as stderr_f:
                    
                    process = subprocess.Popen(
                        cmd,
                        cwd=workspace,
                        env=env,
                        stdout=stdout_f,
                        stderr=stderr_f,
                        stdin=subprocess.PIPE,
                        text=True,
                    )
                    
                    # 发送自动确认输入
                    try:
                        process.stdin.write('y\n' * 100)
                        process.stdin.flush()
                        process.stdin.close()
                    except:
                        pass
                    
                    # 等待完成或超时
                    try:
                        process.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                        print(f"  ✗ 超时 ({timeout}秒)")
                
                # 读取输出
                with open(stdout_file, 'r', encoding='utf-8') as f:
                    stdout = f.read()
                with open(stderr_file, 'r', encoding='utf-8') as f:
                    stderr = f.read()
                
                # 合并到最终日志文件
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write("STDOUT:\n")
                    f.write("-" * 80 + "\n")
                    f.write(stdout)
                    f.write("\n" + "-" * 80 + "\n\n")
                    f.write("STDERR:\n")
                    f.write("-" * 80 + "\n")
                    f.write(stderr)
                    f.write("\n" + "-" * 80 + "\n\n")
                    duration = time.time() - start_time
                    f.write(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"执行耗时: {duration:.2f}秒\n")
                    f.write(f"退出码: {process.returncode}\n")
                
                # 删除临时文件
                try:
                    os.remove(stdout_file)
                    os.remove(stderr_file)
                except:
                    pass
                
                print(f"  ✓ 执行日志已实时保存: {log_file}")
                
                # 创建 result 对象模拟 subprocess.run 返回值
                class Result:
                    def __init__(self, returncode, stdout, stderr):
                        self.returncode = returncode
                        self.stdout = stdout
                        self.stderr = stderr
                
                result = Result(process.returncode, stdout, stderr)
                
            else:
                # 没有日志文件，使用原来的简单方式
                result = subprocess.run(
                    cmd,
                    cwd=workspace,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout,
                    input='y\n' * 100,
                )
            
            duration = time.time() - start_time
            print(f"  完成时间: {time.strftime('%H:%M:%S')}")
            print(f"  执行耗时: {duration:.2f}秒")
            
            if result.returncode != 0:
                print(f"⚠️  ducc 返回非零退出码: {result.returncode}")
                print(f"stderr 预览: {result.stderr[:200]}...")
            
            output = result.stdout
            if not output and result.returncode != 0:
                print(f"✗ ducc 执行失败且无输出")
            else:
                print(f"✓ ducc 执行完成,输出长度: {len(output)} 字符")
            
            return output
        
        except subprocess.TimeoutExpired:
            print(f"✗ ducc 执行超时 ({timeout}秒 = {timeout//60}分钟)")
            
            # 保存超时信息
            if log_file:
                try:
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write("=" * 80 + "\n")
                        f.write("DUCC 执行超时\n")
                        f.write("=" * 80 + "\n")
                        f.write(f"超时时间: {timeout}秒\n")
                        f.write(f"工作目录: {workspace}\n")
                except:
                    pass
            
            return ""
        except Exception as e:
            print(f"✗ ducc 执行失败: {e}")
            
            # 保存错误信息
            if log_file:
                try:
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write("=" * 80 + "\n")
                        f.write("DUCC 执行异常\n")
                        f.write("=" * 80 + "\n")
                        f.write(f"错误: {str(e)}\n")
                        f.write(f"工作目录: {workspace}\n")
                except:
                    pass
            
            return ""
    
    def _call_ducc_tmux(self, prompt: str, workspace: str, timeout: int, instance_id: str, task_dir: str = "") -> str:
        """使用tmux模式调用 ducc"""
        import re
        
        # 生成tmux session名称
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', instance_id)
        session_name = f"swe_bench_{safe_id}_{int(time.time())}"
        
        print(f"\n{'='*60}")
        print(f"启动 tmux session: {session_name}")
        print(f"工作目录: {workspace}")
        print(f"查看执行过程: tmux attach -t {session_name}")
        print(f"{'='*60}\n")
        
        try:
            # 1. 创建tmux session，使用登录 shell 以确保环境正确初始化
            # 检测当前使用的 shell
            current_shell = os.environ.get('SHELL', '/bin/bash')
            
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name, "-c", workspace],
                check=True
            )
            print(f"✓ tmux session 已创建")
            
            # ✨ 关键修复：设置超大的 history-limit 以避免输出被截断
            # ducc 输出可能非常长，默认的 2000 行会导致早期内容丢失
            subprocess.run(
                ["tmux", "set-option", "-t", session_name, "history-limit", "500000"],
                check=True
            )
            print(f"  ✓ 已设置 history-limit: 500000 行")
            
            # 2. 检测并激活 conda 环境（如果需要）
            # 优先级: CONDA_DEFAULT_ENV > DEFAULT_CONDA_ENV > 硬编码默认值
            conda_env = os.environ.get('CONDA_DEFAULT_ENV') or \
                       os.environ.get('DEFAULT_CONDA_ENV', 'dejavu')
            
            if os.environ.get('CONDA_DEFAULT_ENV'):
                print(f"  检测到当前 conda 环境: {conda_env}")
            else:
                print(f"  使用默认 conda 环境: {conda_env}")
            
            # 尝试激活 conda 环境
            if conda_env:
                # 方案A: 如果用户在 bashrc/zshrc 中配置了 conda init，直接激活
                # 方案B: 手动 source conda.sh
                
                # 尝试找到 conda 安装路径
                conda_exe = shutil.which('conda')
                if conda_exe:
                    # 获取 conda 基础路径
                    conda_base = os.path.dirname(os.path.dirname(conda_exe))
                    conda_sh = os.path.join(conda_base, 'etc/profile.d/conda.sh')
                    
                    if os.path.exists(conda_sh):
                        # 使用 conda.sh 初始化
                        init_and_activate = f'source {conda_sh} && conda activate {conda_env}'
                        subprocess.run(
                            ["tmux", "send-keys", "-t", session_name, init_and_activate, "Enter"],
                            check=True
                        )
                        print(f"  ✓ 使用 conda.sh 初始化: {conda_sh}")
                    else:
                        # 直接尝试 conda activate
                        subprocess.run(
                            ["tmux", "send-keys", "-t", session_name, f"conda activate {conda_env}", "Enter"],
                            check=True
                        )
                        print(f"  ⚠️  直接调用 conda activate（可能需要在 shell 配置中初始化 conda）")
                else:
                    print(f"  ⚠️  未找到 conda 命令，跳过环境激活")
                
                # 等待环境激活
                time.sleep(2)
                
                # 验证环境
                subprocess.run(
                    ["tmux", "send-keys", "-t", session_name, "echo 'ENV: '$CONDA_DEFAULT_ENV", "Enter"],
                    check=True
                )
                time.sleep(0.5)
                content = self._tmux_capture_pane(session_name)
                if conda_env in content:
                    print(f"  ✓ conda 环境激活成功: {conda_env}")
                else:
                    print(f"  ⚠️  环境激活可能失败，继续尝试...")
            else:
                print(f"  跳过 conda 环境激活")
            
            # 3. 设置环境变量 - 与直接模式保持一致
            # 关键：设置 DUCC_AUTO_APPROVE 和 CI 环境变量
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "export DUCC_AUTO_APPROVE=1", "Enter"],
                check=True
            )
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "export CI=true", "Enter"],
                check=True
            )
            time.sleep(0.5)
            print(f"  ✓ 环境变量已设置: DUCC_AUTO_APPROVE=1, CI=true")
            
            # 4. 构建ducc命令 - 使用交互模式
            permission_mode = "bypassPermissions" if os.geteuid() != 0 else "default"
            
            # 准备文件路径（必须使用绝对路径，因为tmux工作目录是workspace）
            debug_file = None
            prompt_file = None
            
            if task_dir:
                debug_file = os.path.abspath(os.path.join(task_dir, 'ducc_debug.log'))
                prompt_file = os.path.abspath(os.path.join(task_dir, 'prompt.txt'))
                
                # 保存prompt到文件（用于后续分析）
                with open(prompt_file, 'w', encoding='utf-8') as f:
                    f.write(prompt)
                print(f"  Prompt已保存: {prompt_file}")
            
            # 使用交互模式（不用-p参数），这样可以实时查看
            ducc_cmd = f'{self.ducc_bin} --permission-mode {permission_mode} --allowedTools "Read,Edit,Write"'
            
            if debug_file:
                ducc_cmd += f' --debug-file "{debug_file}"'
                print(f"  Debug 日志: {debug_file}")
            
            print(f"  命令: {ducc_cmd}")
            
            # 5. 在tmux中启动ducc
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, ducc_cmd, "Enter"],
                check=True
            )
            print(f"✓ ducc 命令已发送")
            
            # 6. 等待ducc启动
            time.sleep(3)
            
            # 7. 自动确认trust folder等提示
            auto_confirm_patterns = {
                "Do you want to proceed": "Enter",
                "Yes, I trust this folder": "Enter",
                "allow all edits during this session": "Down Enter",
                "Press Enter to continue": "Enter",
                "Yes, I accept": "Down Enter",
                "No, exit": "Down Enter",
            }
            
            # 循环检查并确认提示
            print(f"  检查并自动确认提示...")
            for i in range(10):
                content = self._tmux_capture_pane(session_name)
                import re
                ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
                clean_content = ansi_escape.sub('', content)
                
                confirmed = False
                for pattern, keys in auto_confirm_patterns.items():
                    if pattern in clean_content:
                        print(f"  检测到提示: '{pattern}', 自动发送: {keys}")
                        for key in keys.split():
                            subprocess.run(["tmux", "send-keys", "-t", session_name, key])
                        confirmed = True
                        time.sleep(1)
                        break
                if confirmed:
                    continue
                time.sleep(1)
            
            # 8. 发送prompt
            print(f"✓ 发送任务prompt")
            time.sleep(2)
            
            try:
                # 使用 tmux buffer 发送prompt
                import tempfile
                custom_tmp_dir = '/ssd1/Dejavu/tmp'
                os.makedirs(custom_tmp_dir, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', dir=custom_tmp_dir) as f:
                    f.write(prompt)
                    prompt_tmp_file = f.name
                
                subprocess.run(["tmux", "load-buffer", prompt_tmp_file], check=True)
                subprocess.run(["tmux", "paste-buffer", "-t", session_name], check=True)
                subprocess.run(["tmux", "send-keys", "-t", session_name, "Enter"], check=True)
                
                try:
                    os.remove(prompt_tmp_file)
                except:
                    pass
                
                print(f"  ✓ Prompt 已通过 tmux buffer 发送")
            except Exception as e:
                print(f"  ⚠️  tmux buffer 方式失败: {e}")
            
            # 9. 监控执行直到完成
            print(f"✓ 开始监控执行...")
            start_time = time.time()
            output = self._wait_for_ducc_completion(session_name, timeout)
            duration = time.time() - start_time
            
            # 保存tmux输出到日志
            if task_dir:
                log_file = os.path.join(task_dir, 'ducc_execution.log')
                try:
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write("=" * 80 + "\n")
                        f.write("DUCC 执行日志 (tmux模式)\n")
                        f.write("=" * 80 + "\n")
                        f.write(f"Session: {session_name}\n")
                        f.write(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}\n")
                        f.write(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"执行耗时: {duration:.2f}秒\n")
                        f.write(f"工作目录: {workspace}\n")
                        f.write("=" * 80 + "\n\n")
                        
                        f.write("Tmux 捕获内容:\n")
                        f.write("-" * 80 + "\n")
                        f.write(output)
                        f.write("\n" + "-" * 80 + "\n")
                    print(f"  ✓ 执行日志已保存: {log_file}")
                except Exception as e:
                    print(f"  ⚠️  保存日志失败: {e}")
            
            print(f"\n✓ 任务执行完成 (耗时: {duration:.2f}秒)")
            
            # 自动关闭tmux session以防止批量运行时session堆积
            try:
                subprocess.run(
                    ["tmux", "kill-session", "-t", session_name],
                    check=False,  # 即使失败也不影响结果
                    capture_output=True
                )
                print(f"  ✓ Tmux session已关闭: {session_name}")
            except Exception as e:
                print(f"  ⚠ 无法关闭tmux session: {e}")
            
            return output
            
        except subprocess.CalledProcessError as e:
            print(f"✗ tmux命令执行失败: {e}")
            # 清理失败的session
            try:
                subprocess.run(["tmux", "kill-session", "-t", session_name], check=False, capture_output=True)
            except:
                pass
            return ""
        except Exception as e:
            print(f"✗ tmux模式执行失败: {e}")
            # 清理失败的session
            try:
                subprocess.run(["tmux", "kill-session", "-t", session_name], check=False, capture_output=True)
            except:
                pass
            return ""
    
    def _tmux_capture_pane(self, session_name: str) -> str:
        """捕获tmux pane内容"""
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-p", "-e", "-S", "-", "-t", session_name],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except:
            return ""
    
    def _wait_for_shell_prompt(self, session_name: str, timeout: int, check_interval: int = 5) -> None:
        """等待shell返回prompt（简化版，用于-p模式）"""
        import re
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        
        start_time = time.time()
        print(f"  等待ducc执行完成...")
        
        while True:
            if time.time() - start_time > timeout:
                print(f"  ⚠️  达到超时时间 ({timeout}秒)")
                break
            
            # 检查session是否还存在
            result = subprocess.run(
                ["tmux", "has-session", "-t", session_name],
                capture_output=True
            )
            if result.returncode != 0:
                print(f"  Session已关闭")
                break
            
            # 捕获内容
            content = self._tmux_capture_pane(session_name)
            clean_content = ansi_escape.sub('', content)
            
            # 检测shell prompt返回（说明ducc执行完毕）
            lines = clean_content.strip().split('\n')
            last_line = lines[-1] if lines else ""
            
            # 常见的shell prompt标志
            if any(marker in last_line for marker in ['❯', '$', '#', '>']):
                # 确认是真的返回prompt，不是ducc内部输出
                if len(last_line.strip()) < 50:  # prompt通常很短
                    print(f"  ✓ 检测到shell prompt返回: {last_line.strip()[:20]}")
                    time.sleep(2)  # 额外等待确保所有输出flush
                    break
            
            time.sleep(check_interval)
    
    def _wait_for_ducc_completion(self, session_name: str, timeout: int, check_interval: int = 3) -> str:
        """等待ducc执行完成"""
        import re
        
        # ANSI转义序列清理
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
        
        # 自动确认模式
        auto_confirm_patterns = {
            "Do you want to proceed": "Enter",
            "Yes, I trust this folder": "Enter",
            "allow all edits during this session": "Down Enter",
            "Press Enter to continue": "Enter",
            "Yes, I accept": "Down Enter",
            "No, exit": "Down Enter",
            "Pasted text": "Enter",  # ✨ 修复：自动确认粘贴文本提示
        }
        
        start_time = time.time()
        last_content = ""
        idle_count = 0
        task_started = False
        
        while True:
            if time.time() - start_time > timeout:
                print(f"  ⚠️  达到超时时间 ({timeout}秒)")
                break
            
            # 检查session是否还存在
            result = subprocess.run(
                ["tmux", "has-session", "-t", session_name],
                capture_output=True
            )
            if result.returncode != 0:
                print(f"  Session已关闭")
                break
            
            # 捕获当前内容
            content = self._tmux_capture_pane(session_name)
            clean_content = ansi_escape.sub('', content)
            
            # ✨ 自动确认提示（在整个等待过程中持续检查）
            for pattern, keys in auto_confirm_patterns.items():
                if pattern in clean_content:
                    print(f"  检测到提示: '{pattern}', 自动发送: {keys}")
                    for key in keys.split():
                        subprocess.run(["tmux", "send-keys", "-t", session_name, key])
                    time.sleep(1)
                    # 重置状态，重新开始检测
                    last_content = ""
                    idle_count = 0
                    continue
            
            # 检测任务是否开始
            if not task_started:
                task_indicators = ['Read(', 'Write(', 'Edit(', 'Thinking', 'Reading', 'Writing']
                for indicator in task_indicators:
                    if indicator in clean_content:
                        task_started = True
                        print(f"  ✓ 任务已开始 (检测到: {indicator})")
                        break
            
            if not task_started:
                print(f"  等待任务开始...")
                time.sleep(check_interval)
                continue
            
            # 检测是否仍在执行
            still_working = any(
                ind in clean_content
                for ind in ['Thinking', 'Searching', 'Reading', 'Writing', 'Editing', 'Proofing']
            )
            
            if still_working:
                print(f"  ducc 正在工作...")
                last_content = content
                time.sleep(check_interval)
                continue
            
            # 检测完成标志
            lines = clean_content.strip().split('\n')
            last_lines = '\n'.join(lines[-5:]) if len(lines) >= 5 else clean_content
            
            # 检测idle状态（❯ prompt）
            is_idle = False
            if '❯' in last_lines:
                for line in lines[-3:]:
                    stripped = line.strip()
                    if stripped == '❯' or (stripped.endswith('❯') and len(stripped) < 5):
                        is_idle = True
                        break
            
            # 判断是否完成
            if is_idle or 'Done.' in clean_content:
                if content == last_content:
                    idle_count += 1
                    print(f"  屏幕无变化 ({idle_count}/3)")
                    if idle_count >= 3:
                        print(f"  ✓ 任务完成")
                        break
                else:
                    idle_count = 0
                    last_content = content
            else:
                idle_count = 0
                last_content = content
            
            time.sleep(check_interval)
        
        # 返回最终内容（清理 ANSI 转义序列）
        # ✨ 增强：多次捕获确保完整性，等待可能的延迟输出
        print(f"  等待最终输出稳定...")
        time.sleep(2)  # 额外等待确保所有输出都到buffer
        
        final_content = self._tmux_capture_pane(session_name)
        clean_final_content = ansi_escape.sub('', final_content)
        
        print(f"  ✓ 最终捕获内容长度: {len(clean_final_content)} 字符")
        return clean_final_content
    
    def _save_task_summary(self, task_dir: str, result: Dict, start_time: float):
        """保存任务执行摘要"""
        summary_file = os.path.join(task_dir, 'task_summary.json')
        try:
            end_time = time.time()
            summary = {
                'instance_id': result.get('instance_id', ''),
                'start_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time)),
                'end_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time)),
                'duration_seconds': result.get('duration', end_time - start_time),
                'patch_generated': bool(result.get('patch', '')),
                'patch_length': len(result.get('patch', '')),
                'validation_performed': bool(result.get('validation')),
                'validation_success': result.get('validation', {}).get('success', False) if result.get('validation') else None,
                'error': result.get('error', ''),
                'task_directory': task_dir,
            }
            
            # 添加验证详情
            if result.get('validation'):
                summary['validation_details'] = {
                    'test_output_length': len(result['validation'].get('test_output', '')),
                    'exit_code': result['validation'].get('exit_code'),
                    'test_duration': result['validation'].get('test_duration'),
                    'stats': result['validation'].get('stats', {}),
                }
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            print(f"✓ 任务摘要已保存: {summary_file}")
            
            # 同时保存一个简洁的文本摘要
            summary_text_file = os.path.join(task_dir, 'README.txt')
            with open(summary_text_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"SWE-bench 任务执行摘要\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"任务 ID: {summary['instance_id']}\n")
                f.write(f"开始时间: {summary['start_time']}\n")
                f.write(f"结束时间: {summary['end_time']}\n")
                f.write(f"执行耗时: {summary['duration_seconds']:.2f}秒\n\n")
                
                f.write(f"Patch 生成: {'✓ 是' if summary['patch_generated'] else '✗ 否'}\n")
                if summary['patch_generated']:
                    f.write(f"Patch 长度: {summary['patch_length']} 字符\n")
                f.write("\n")
                
                if summary['validation_performed']:
                    f.write(f"验证执行: ✓ 是\n")
                    f.write(f"验证结果: {'✓ 通过' if summary['validation_success'] else '✗ 失败'}\n")
                    if summary.get('validation_details'):
                        vd = summary['validation_details']
                        f.write(f"  - 退出码: {vd.get('exit_code')}\n")
                        f.write(f"  - 测试耗时: {vd.get('test_duration', 0):.2f}秒\n")
                        if vd.get('stats'):
                            stats = vd['stats']
                            f.write(f"  - 通过: {stats.get('passed', 0)}\n")
                            f.write(f"  - 失败: {stats.get('failed', 0)}\n")
                            f.write(f"  - 错误: {stats.get('errors', 0)}\n")
                else:
                    f.write(f"验证执行: ✗ 否\n")
                
                if summary['error']:
                    f.write(f"\n错误: {summary['error']}\n")
                
                f.write("\n" + "=" * 80 + "\n")
                f.write("文件说明:\n")
                f.write("=" * 80 + "\n")
                f.write("  dataset_info.json         - 数据集原始信息\n")
                f.write("  prompt.txt                - 发送给 ducc 的 prompt\n")
                f.write("  ducc_execution.log        - ducc 执行日志（含stdout/stderr）\n")
                f.write("  ducc_debug.log            - ducc 详细调试日志（API调用、工具使用等）\n")
                f.write("  ducc_raw_output.txt       - ducc 原始输出\n")
                f.write("  claude_session.jsonl      - ✨ Claude 完整 session 轨迹（一对一）\n")
                f.write("  claude_session_info.json  - ✨ Session 元信息（原始路径等）\n")
                f.write("  claude_session_summary.txt- ✨ Session 轨迹摘要（事件统计）\n")
                f.write("  extracted_patch.diff      - 提取的 patch\n")
                f.write("  validation_result.json    - 验证结果详情\n")
                f.write("  task_summary.json         - 任务摘要（JSON格式）\n")
                f.write("  README.txt                - 本文件（文本摘要）\n")
                f.write("\n")
                f.write("=" * 80 + "\n")
                f.write("查看 Claude session 轨迹:\n")
                f.write("=" * 80 + "\n")
                f.write("  # 查看完整轨迹（JSON Lines 格式）\n")
                f.write("  cat claude_session.jsonl | jq\n")
                f.write("\n")
                f.write("  # 查看事件类型统计\n")
                f.write("  cat claude_session.jsonl | jq -r '.type' | sort | uniq -c\n")
                f.write("\n")
                f.write("  # 只看工具调用\n")
                f.write("  cat claude_session.jsonl | jq 'select(.type==\"tool_use\")'\n")
                f.write("\n")
                f.write("  # 只看 AI 思考过程\n")
                f.write("  cat claude_session.jsonl | jq -r 'select(.type==\"thinking\") | .content'\n")
                f.write("\n")
                f.write("  # 查看对话流程\n")
                f.write("  cat claude_session.jsonl | jq -r '{type: .type, time: .timestamp}'\n")
                
            print(f"✓ 文本摘要已保存: {summary_text_file}")
            
        except Exception as e:
            print(f"⚠️  保存任务摘要失败: {e}")
    
    def evaluate_single(self, instance: Dict, output_dir: str = './swe_bench_output_ducc') -> Dict:
        """评估单个任务"""
        instance_id = instance['instance_id']
        
        print(f"\n{'='*60}")
        print(f"处理任务: {instance_id}")
        print(f"{'='*60}")
        
        # 创建任务专属目录
        # 使用安全的文件名（替换特殊字符）
        safe_instance_id = instance_id.replace('/', '_').replace('\\', '_').replace(':', '_')
        task_dir = os.path.join(output_dir, 'tasks', safe_instance_id)
        os.makedirs(task_dir, exist_ok=True)
        print(f"任务目录: {task_dir}")
        
        # 保存原始数据集信息
        dataset_info_file = os.path.join(task_dir, 'dataset_info.json')
        try:
            with open(dataset_info_file, 'w', encoding='utf-8') as f:
                # 保存数据集的完整信息（包括 ground truth patch）
                dataset_info = {
                    'instance_id': instance_id,
                    'repo': instance.get('repo', ''),
                    'repo_language': instance.get('repo_language', ''),
                    'problem_statement': instance.get('problem_statement', ''),
                    'requirements': instance.get('requirements', ''),
                    'interface': instance.get('interface', ''),
                    'dockerhub_tag': instance.get('dockerhub_tag', ''),
                    'base_commit': instance.get('base_commit', ''),
                    'hints': instance.get('hints', ''),
                    'created_at': instance.get('created_at', ''),
                    # Ground truth patch (参考答案)
                    'patch': instance.get('patch', ''),
                    'test_patch': instance.get('test_patch', ''),
                    'FAIL_TO_PASS': instance.get('FAIL_TO_PASS', ''),
                    'PASS_TO_PASS': instance.get('PASS_TO_PASS', ''),
                }
                json.dump(dataset_info, f, indent=2, ensure_ascii=False)
            print(f"✓ 数据集信息已保存: {dataset_info_file}")
        except Exception as e:
            print(f"⚠️  保存数据集信息失败: {e}")
        
        start_time = time.time()
        tmpdir_to_cleanup = None
        
        try:
            # 1. 提取整个代码库到本地
            print("\n正在提取代码库...")
            workspace, container_workdir, tmpdir_to_cleanup = self.extract_codebase(instance)
            
            # 2. 构建简化的 prompt (agent 可以自己探索代码)
            prompt = self._build_prompt(instance)
            
            # 3. 调用 ducc (agent 在 workspace 目录操作)
            output = self.call_ducc(
                prompt, 
                workspace,
                timeout=self.timeout,
                use_tmux=self.use_tmux, 
                instance_id=instance_id,
                task_dir=task_dir
            )
            
            # 保存ducc原始输出
            raw_output_file = os.path.join(task_dir, 'ducc_raw_output.txt')
            try:
                with open(raw_output_file, 'w', encoding='utf-8') as f:
                    f.write(output if output else "(空输出)")
                print(f"✓ Ducc 原始输出已保存: {raw_output_file}")
            except Exception as e:
                print(f"⚠️  保存原始输出失败: {e}")
            
            # 复制 Claude session 轨迹到任务目录
            print("\n正在复制 Claude session 轨迹...")
            self._copy_claude_session_trace(workspace, task_dir, start_time)
            
            if not output:
                error_result = {
                    'instance_id': instance_id,
                    'patch': '',
                    'error': 'ducc returned empty output',
                    'validation': {'success': False, 'error': 'Empty output'},
                    'task_dir': task_dir,
                }
                # 保存错误信息
                self._save_task_summary(task_dir, error_result, start_time)
                return error_result
            
            # 4. 提取 patch
            # ✨ 优先策略：从ducc生成的fix.patch文件读取（最可靠）
            patch = ""
            fix_patch_file = os.path.join(workspace, 'fix.patch')
            
            if os.path.exists(fix_patch_file):
                try:
                    with open(fix_patch_file, 'r', encoding='utf-8') as f:
                        patch = f.read().strip()
                    if patch and ('diff --git' in patch or '@@' in patch):
                        print(f"✓ 从fix.patch文件读取到patch (长度: {len(patch)} 字符)")
                    else:
                        print(f"⚠️  fix.patch文件存在但内容无效，尝试其他来源")
                        patch = ""
                except Exception as e:
                    print(f"⚠️  读取fix.patch失败: {e}")
            
            # 备用方案1：从输出中提取
            if not patch:
                print(f"  尝试从ducc输出中提取patch...")
                patch = self._extract_patch(output)
            
            # 备用方案2：从debug文件提取（tmux模式）
            if self.use_tmux and (not patch or ('diff --git' not in patch and '@@' not in patch)):
                print(f"  ⚠️  从输出中未提取到有效patch，尝试其他来源...")
                
                debug_file = os.path.join(task_dir, 'ducc_debug.log')
                if os.path.exists(debug_file):
                    try:
                        with open(debug_file, 'r', encoding='utf-8') as f:
                            debug_content = f.read()
                        debug_patch = self._extract_patch(debug_content)
                        if debug_patch and ('diff --git' in debug_patch or '@@' in debug_patch):
                            print(f"  ✓ 从debug文件中成功提取patch (长度: {len(debug_patch)})")
                            patch = debug_patch
                    except Exception as e:
                        print(f"  ✗ 读取debug文件失败: {e}")
                
                # 备用方案3：从workspace中查找其他.diff或.patch文件
                if not patch or ('diff --git' not in patch and '@@' not in patch):
                    print(f"  尝试从workspace查找其他patch文件...")
                    try:
                        import glob
                        diff_files = glob.glob(os.path.join(workspace, '*.diff')) + \
                                    glob.glob(os.path.join(workspace, '*.patch'))
                        # 排除fix.patch（已经检查过了）
                        diff_files = [f for f in diff_files if f != fix_patch_file]
                        if diff_files:
                            # 选择最新的文件
                            latest_diff = max(diff_files, key=os.path.getmtime)
                            with open(latest_diff, 'r', encoding='utf-8') as f:
                                file_patch = f.read()
                            if file_patch and ('diff --git' in file_patch or '@@' in file_patch):
                                print(f"  ✓ 从文件中找到patch: {os.path.basename(latest_diff)} (长度: {len(file_patch)})")
                                patch = file_patch
                    except Exception as e:
                        print(f"  ✗ 查找patch文件失败: {e}")
            
            # 保存提取的patch
            if patch:
                patch_file = os.path.join(task_dir, 'extracted_patch.diff')
                try:
                    with open(patch_file, 'w', encoding='utf-8') as f:
                        f.write(patch)
                    print(f"✓ Patch 已保存: {patch_file}")
                except Exception as e:
                    print(f"⚠️  保存 patch 失败: {e}")
            
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
                
                # 保存验证结果
                validation_file = os.path.join(task_dir, 'validation_result.json')
                try:
                    with open(validation_file, 'w', encoding='utf-8') as f:
                        json.dump(validation_result, f, indent=2)
                    print(f"✓ 验证结果已保存: {validation_file}")
                except Exception as e:
                    print(f"⚠️  保存验证结果失败: {e}")
            
            result = {
                'instance_id': instance_id,
                'patch': patch,
                'duration': duration,
                'validation': validation_result,
                'task_dir': task_dir,
            }
            
            # 保存任务摘要
            self._save_task_summary(task_dir, result, start_time)
            
            return result
        
        finally:
            # 清理临时目录
            if tmpdir_to_cleanup:
                import shutil
                shutil.rmtree(tmpdir_to_cleanup, ignore_errors=True)
    
    def _build_prompt(self, instance: Dict) -> str:
        """构建 prompt (agent 可以自己探索代码,不需要提供文件列表)"""
        # 清理 problem_statement，移除可能的序列化引号
        problem_stmt = instance['problem_statement']
        if isinstance(problem_stmt, str):
            # 移除开头和结尾的引号（如果是被序列化的）
            if problem_stmt.startswith('"') and problem_stmt.endswith('"'):
                problem_stmt = problem_stmt[1:-1]
            # 替换转义的换行符为真实换行符
            problem_stmt = problem_stmt.replace('\\n', '\n')
        
        requirements = f"\n## Requirements\n{instance['requirements']}\n" if instance.get('requirements') else ""
        interface = f"\n## Interface\n{instance['interface']}\n" if instance.get('interface') else ""
        
        return f"""You are a software engineer fixing a bug. The codebase is in the current directory.

## Problem Statement
{problem_stmt}
{requirements}{interface}

## Task
1. Explore the codebase in the current directory to understand the structure
2. Locate the relevant files related to this issue
3. Generate a patch that fixes the issue with minimal, targeted changes
4. **IMPORTANT**: Save the final patch to a file named `fix.patch` in the current directory
5. The patch should be in unified diff format

## Output Format
After you complete the fix, use the Write tool to save the patch to `fix.patch`:

```diff
diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -10,5 +10,5 @@ def func():
-    old_line
+    new_line
```

**CRITICAL**: You MUST write the final patch to the file `fix.patch` in the current directory. This is mandatory."""
    
    def _extract_patch(self, output: str) -> str:
        """从 ducc 输出提取 patch"""
        import re
        
        # 1. 尝试提取 markdown 代码块中的 diff
        if '```diff' in output:
            start = output.find('```diff') + 7
            end = output.find('```', start)
            if end > start:
                return output[start:end].strip()
        
        # 2. 清理 XML 标签 (移除 <think>, <minimax:tool_call> 等)
        # 移除所有 XML 标签
        cleaned = re.sub(r'<[^>]+>', '', output)
        
        # 3. 查找 diff --git 开头的内容
        if 'diff --git' in cleaned:
            # 找到第一个 diff --git 的位置
            diff_start = cleaned.find('diff --git')
            patch_content = cleaned[diff_start:]
            
            # ✨ 增强：智能识别patch结束位置
            # Patch通常在遇到以下内容时结束：
            # - 工具调用的标记（如 "Tool:" 或 "Read(" 等）
            # - 明显的非diff内容（如普通对话）
            # - Shell prompt标记
            
            # 尝试找到patch的结束位置
            end_markers = [
                r'\n\n[^\s\-\+\@].*?:\s',  # 冒号开头的标签（如 "Tool:"）
                r'\nRead\(',  # 工具调用
                r'\nWrite\(',
                r'\nEdit\(',
                r'\n❯\s',  # Shell prompt
                r'\n\$\s',
                r'\n\(dejavu\)',  # Conda环境提示
            ]
            
            end_pos = len(patch_content)
            for marker_pattern in end_markers:
                match = re.search(marker_pattern, patch_content)
                if match:
                    potential_end = match.start()
                    # 确保我们至少提取了一些内容（避免过早截断）
                    if potential_end > 100:  # 至少100字符
                        end_pos = min(end_pos, potential_end)
            
            patch_content = patch_content[:end_pos].strip()
            
            # 额外验证：patch应该包含基本的diff结构
            if '@@' in patch_content or '---' in patch_content:
                return patch_content
            else:
                # 如果没有标准diff结构，返回原内容
                return cleaned[diff_start:].strip()
        
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
            
            # 清理 patch 中的路径前缀问题
            # 如果 workdir 是 /app，patch 中的路径可能是 app/xxx，需要清理
            import re
            if workdir and workdir != '/':
                workdir_basename = os.path.basename(workdir.rstrip('/'))
                # 修复: a/app/file.py -> a/file.py
                patch = re.sub(
                    r'(diff --git a/)' + re.escape(workdir_basename) + r'/',
                    r'\1',
                    patch
                )
                patch = re.sub(
                    r'(--- a/)' + re.escape(workdir_basename) + r'/',
                    r'\1',
                    patch
                )
                patch = re.sub(
                    r'(\+\+\+ b/)' + re.escape(workdir_basename) + r'/',
                    r'\1',
                    patch
                )
                print(f"  ✓ 已清理 patch 路径前缀: {workdir_basename}/")
            
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
    # 使用安全的文件名
    safe_instance_id = instance_id.replace('/', '_').replace('\\', '_').replace(':', '_')
    
    # 官方格式: 单个预测 (用于调试)
    prediction = {
        'instance_id': instance_id,
        'model_patch': result.get('patch', ''),
        'model_name_or_path': 'ducc_standalone',
    }
    with open(os.path.join(predictions_dir, f"{safe_instance_id}.json"), 'w', encoding='utf-8') as f:
        json.dump(prediction, f, indent=2)
    
    # 官方格式: JSONL (用于批量评估)
    with open(os.path.join(output_dir, 'all_preds.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(prediction) + '\n')
    
    # 完整结果 (包含 validation 等额外信息)
    # 注意: 移除 task_dir 字段避免路径过长
    result_copy = result.copy()
    task_dir = result_copy.pop('task_dir', '')
    
    with open(os.path.join(output_dir, f"{safe_instance_id}_full.json"), 'w', encoding='utf-8') as f:
        json.dump(result_copy, f, indent=2)
    
    print(f"✓ 结果已保存到 {output_dir}")
    if task_dir:
        print(f"✓ 任务详情目录: {task_dir}")


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
        description='SWE-bench Pro DUCC 评测 (支持 tmux 实时查看, 自动 conda 环境)',
        epilog="""
说明:
  SWE-bench Pro 包含41个多语言仓库,官方 swebench.harness 不支持
  本脚本使用自己的验证逻辑 (在 Docker 容器内 git apply + 运行测试)
  
  【tmux 模式说明】
  使用 --use-tmux 参数可以在 tmux session 中运行 ducc，方便实时查看执行过程
  tmux 模式会自动激活 conda 环境（默认: dejavu），也可通过 --conda-env 指定
  
推荐工作流程:
  1. 单个任务测试:
     python test_tmux_cc_experience.py --index 0 --no-validate
  
  2. 批量处理（前N个任务）:
     python test_tmux_cc_experience.py --max-tasks 10 --no-validate
  
  3. 指定范围处理（适合分批次运行）:
     # 第一批: 处理 0-50
     python test_tmux_cc_experience.py --start-index 0 --end-index 50 --no-validate
     
     # 第二批: 处理 50-100
     python test_tmux_cc_experience.py --start-index 50 --end-index 100 --no-validate
     
     # 第三批: 处理 100-150
     python test_tmux_cc_experience.py --start-index 100 --end-index 150 --no-validate
  
  4. tmux 模式（可实时查看）:
     # 单个任务
     python test_tmux_cc_experience.py --index 0 --use-tmux --no-validate
     
     # 在另一个终端查看: tmux attach -t swe_bench_<instance_id>
     
     # 指定 conda 环境
     python test_tmux_cc_experience.py --index 0 --use-tmux --conda-env myenv
  
  5. 查看结果:
     cat swe_bench_output_ducc/report.json
     ls -la swe_bench_output_ducc/tasks/<instance_id>/
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--index', type=int, help='任务索引（单个任务）')
    parser.add_argument('--max-tasks', type=int, help='最多处理 N 个任务（从索引0开始）')
    parser.add_argument('--start-index', type=int, help='起始索引（包含，配合 --end-index 使用）')
    parser.add_argument('--end-index', type=int, help='结束索引（不包含，配合 --start-index 使用）')
    parser.add_argument('--no-validate', action='store_true', 
                       help='跳过验证 (默认启用验证)')
    parser.add_argument('--use-tmux', action='store_true',
                       help='使用 tmux 模式运行 ducc (可通过 tmux attach 查看实时执行)')
    parser.add_argument('--conda-env', type=str, default='dejavu',
                       help='tmux 模式下使用的 conda 环境名称 (默认: dejavu)')
    parser.add_argument('--timeout', type=int, default=1800,
                       help='ducc 执行超时时间（秒），默认 1800 (30分钟)')
    parser.add_argument('--output-dir', default='./swe_bench_output_ducc', help='输出目录')
    args = parser.parse_args()
    
    global ENABLE_VALIDATION
    ENABLE_VALIDATION = not args.no_validate
    
    # 设置默认 conda 环境（如果未设置 CONDA_DEFAULT_ENV）
    if args.use_tmux and args.conda_env:
        if not os.environ.get('CONDA_DEFAULT_ENV'):
            os.environ['DEFAULT_CONDA_ENV'] = args.conda_env
            print(f"💡 将使用默认 conda 环境: {args.conda_env}")
    
    # 参数验证
    if args.index is None and not args.max_tasks and not (args.start_index is not None and args.end_index is not None):
        parser.error("必须指定以下之一:\n"
                    "  --index <N>                    (单个任务)\n"
                    "  --max-tasks <N>                (前 N 个任务，从0开始)\n"
                    "  --start-index <N> --end-index <M>  (任务范围 [N, M))")
    
    # 检查参数冲突
    if args.index is not None and (args.max_tasks or args.start_index is not None or args.end_index is not None):
        parser.error("--index 不能与 --max-tasks, --start-index, --end-index 同时使用")
    
    if args.max_tasks and (args.start_index is not None or args.end_index is not None):
        parser.error("--max-tasks 不能与 --start-index, --end-index 同时使用")
    
    if (args.start_index is not None) != (args.end_index is not None):
        parser.error("--start-index 和 --end-index 必须同时指定")
    
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
    print(f"运行模式: {'tmux模式 (可实时查看)' if args.use_tmux else '直接模式'}")
    print(f"验证模式: {'启用' if ENABLE_VALIDATION else '禁用'}")
    if not ENABLE_VALIDATION:
        print("⚠️  跳过验证,只生成 patches")
    if args.use_tmux:
        print("💡 提示: 使用 'tmux attach -t swe_bench_<instance_id>' 查看实时执行")
    print()
    
    evaluator = SimpleDuccEvaluator(use_tmux=args.use_tmux, timeout=args.timeout)
    
    try:
        dataset = evaluator.load_dataset()
        
        # 选择任务
        if args.index is not None:
            # 单个任务
            instances = [dataset[args.index]]
            print(f"\n处理单个任务: 索引 {args.index}")
        elif args.start_index is not None and args.end_index is not None:
            # 范围选择
            start = args.start_index
            end = args.end_index
            
            # 验证范围
            if start < 0:
                parser.error(f"--start-index 必须 >= 0，当前: {start}")
            if end > len(dataset):
                print(f"⚠️  --end-index ({end}) 超过数据集大小 ({len(dataset)})，将调整为 {len(dataset)}")
                end = len(dataset)
            if start >= end:
                parser.error(f"--start-index ({start}) 必须小于 --end-index ({end})")
            
            instances = [dataset[i] for i in range(start, end)]
            print(f"\n处理任务范围: [{start}, {end}) (共 {len(instances)} 个任务)")
            print(f"  起始: {instances[0]['instance_id']}")
            print(f"  结束: {instances[-1]['instance_id']}")
        else:
            # max_tasks: 从 0 开始
            max_tasks = min(args.max_tasks, len(dataset))
            instances = [dataset[i] for i in range(max_tasks)]
            print(f"\n处理前 {max_tasks} 个任务 (索引 0-{max_tasks-1})")
        
        print(f"总共将处理 {len(instances)} 个任务")
        
        # 处理
        results = []
        for idx, instance in enumerate(instances, 1):
            print(f"\n{'='*70}")
            print(f"[{idx}/{len(instances)}] {instance['instance_id']}")
            print(f"{'='*70}")
            
            try:
                result = evaluator.evaluate_single(instance, output_dir=args.output_dir)
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
