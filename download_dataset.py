#!/usr/bin/env python3
"""
下载 HuggingFace SWE-bench Pro 数据集的辅助脚本
支持多种下载方式和断点续传
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional

def download_with_huggingface_hub():
    """使用 huggingface_hub 库下载（推荐，支持断点续传）"""
    try:
        from huggingface_hub import hf_hub_download
        
        print("✓ 使用 huggingface_hub 库下载...")
        output_dir = Path.home() / "datasets" / "SWE-bench_Pro"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 下载测试集
        print("正在下载 test-00000-of-00001.parquet...")
        filepath = hf_hub_download(
            repo_id="ScaleAI/SWE-bench_Pro",
            filename="test-00000-of-00001.parquet",
            repo_type="dataset",
            cache_dir=str(output_dir),
            resume_download=True,  # 支持断点续传
        )
        print(f"✓ 下载完成: {filepath}")
        return filepath
    except ImportError:
        print("✗ huggingface_hub 未安装，尝试其他方法...")
        return None
    except Exception as e:
        print(f"✗ 下载失败: {e}")
        return None

def download_with_requests():
    """使用 requests 库下载（需要处理重定向）"""
    try:
        import requests
        from requests.adapters import HTTPAdapter
        from requests.packages.urllib3.util.retry import Retry
        
        print("✓ 使用 requests 库下载（处理重定向）...")
        
        url = "https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro/resolve/main/test-00000-of-00001.parquet"
        
        # 创建会话并配置重试策略
        session = requests.Session()
        
        # 配置重试策略（更激进的重试）
        retry_strategy = Retry(
            total=5,  # 总重试次数
            backoff_factor=1,  # 退避因子（1s, 2s, 4s, 8s, 16s）
            status_forcelist=[429, 500, 502, 503, 504],  # 重试这些状态码
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 添加超时和重试
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Encoding': 'gzip, deflate',
        }
        
        output_dir = Path.home() / "datasets" / "SWE-bench_Pro"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "test-00000-of-00001.parquet"
        
        print(f"正在下载: {url}")
        print(f"保存到: {output_file}")
        print("提示: 如果下载很慢或中断，请尝试配置代理或使用 VPN")
        
        response = session.get(
            url,
            headers=headers,
            timeout=(10, 300),  # (连接超时, 读取超时)
            allow_redirects=True,
            stream=True
        )
        response.raise_for_status()
        
        # 获取文件大小
        total_size = int(response.headers.get('content-length', 0))
        
        # 下载并显示进度
        downloaded = 0
        with open(output_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        percent = (downloaded / total_size) * 100
                        print(f"\r进度: {downloaded / 1024 / 1024:.1f}MB / {total_size / 1024 / 1024:.1f}MB ({percent:.1f}%)", end='', flush=True)
        
        print(f"\n✓ 下载完成: {output_file}")
        return str(output_file)
    except ImportError:
        print("✗ requests 未安装，尝试其他方法...")
        return None
    except Exception as e:
        print(f"✗ 下载失败: {e}")
        return None

def download_with_curl():
    """使用 curl 下载（系统命令）"""
    try:
        import subprocess
        
        print("✓ 使用 curl 下载...")
        
        url = "https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro/resolve/main/test-00000-of-00001.parquet"
        
        output_dir = Path.home() / "datasets" / "SWE-bench_Pro"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "test-00000-of-00001.parquet"
        
        # curl 命令：支持断点续传、重试、更长的超时
        cmd = [
            'curl',
            '-L',  # 跟随重定向
            '-C', '-',  # 断点续传
            '--retry', '5',  # 重试 5 次
            '--retry-delay', '2',  # 重试间隔 2 秒
            '--max-time', '600',  # 单个请求最多 10 分钟
            '--connect-timeout', '10',  # 连接超时 10 秒
            '--speed-limit', '1024',  # 最低速度 1KB/s
            '--speed-time', '30',  # 30 秒内达到最低速度
            '-o', str(output_file),
            url
        ]
        
        print(f"正在下载: {url}")
        print(f"保存到: {output_file}")
        print("提示: curl 会自动重试，如果连接不稳定请耐心等待...")
        
        result = subprocess.run(cmd, check=False)
        
        if output_file.exists() and output_file.stat().st_size > 0:
            size_mb = output_file.stat().st_size / 1024 / 1024
            print(f"✓ 下载完成: {output_file} ({size_mb:.1f} MB)")
            return str(output_file)
        else:
            print("✗ 下载失败，文件为空或不存在")
            return None
    except Exception as e:
        print(f"✗ curl 下载失败: {e}")
        return None

def download_low_bandwidth():
    """超低速下载模式 - 针对不稳定网络"""
    try:
        import socket
        import time as time_module
        
        print("✓ 使用超低速下载模式（针对不稳定网络）...")
        
        url = "https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro/resolve/main/test-00000-of-00001.parquet"
        
        output_dir = Path.home() / "datasets" / "SWE-bench_Pro"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "test-00000-of-00001.parquet"
        
        # 检查是否已部分下载
        resume_header = {}
        if output_file.exists():
            resume_size = output_file.stat().st_size
            if resume_size > 0:
                resume_header = {'Range': f'bytes={resume_size}-'}
                print(f"检测到已下载 {resume_size / 1024 / 1024:.1f} MB，继续下载...")
        
        import requests
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            **resume_header
        }
        
        print(f"正在下载: {url}")
        print(f"保存到: {output_file}")
        print("模式: 超低速下载（每 2 秒一个小数据块，网络不稳定时可用）")
        
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=(5, 30),  # 短超时，快速失败
                allow_redirects=True,
                stream=True,
                verify=True
            )
            response.raise_for_status()
        except Exception as e:
            print(f"连接失败，尝试禁用 SSL 验证...")
            response = requests.get(
                url,
                headers=headers,
                timeout=(5, 30),
                allow_redirects=True,
                stream=True,
                verify=False  # 禁用 SSL 验证（不安全，仅作为最后手段）
            )
            response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        # 超小块下载（每次 1KB），降低连接中断风险
        with open(output_file, 'ab') as f:  # 追加模式支持断点续传
            for chunk in response.iter_content(chunk_size=1024):  # 1KB
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        percent = (downloaded / total_size) * 100
                        speed_kb = len(chunk) / 1024
                        print(f"\r进度: {downloaded / 1024 / 1024:.1f}MB / {total_size / 1024 / 1024:.1f}MB ({percent:.1f}%) 速度: {speed_kb:.1f}KB/s", end='', flush=True)
                    # 每块数据后等待 2 秒，给网络恢复时间
                    time_module.sleep(2)
        
        print(f"\n✓ 下载完成: {output_file}")
        return str(output_file)
    except Exception as e:
        print(f"✗ 超低速下载失败: {e}")
        return None

def main():
    print("="*70)
    print("HuggingFace SWE-bench Pro 数据集下载工具")
    print("="*70)
    print()
    
    # 尝试多种下载方式
    methods = [
        ("huggingface_hub 库", download_with_huggingface_hub),
        ("requests 库（带重试）", download_with_requests),
        ("curl 命令（带重试）", download_with_curl),
        ("超低速下载模式（不稳定网络）", download_low_bandwidth),
    ]
    
    for method_name, method_func in methods:
        print(f"\n尝试方式: {method_name}")
        print("-" * 70)
        
        result = method_func()
        if result:
            print()
            print("="*70)
            print("✓ 下载成功！")
            print("="*70)
            print()
            print("下一步：使用离线数据集运行评测")
            print(f"  LOCAL_DATASET_PATH={result} python test_llm_api.py --index 0 --no-validate")
            print()
            return 0
        print()
    
    print("="*70)
    print("✗ 所有下载方式都失败了")
    print("="*70)
    print()
    print("🔧 故障排查步骤:")
    print("  1. 检查网络连接是否正常")
    print("  2. 配置代理（如需要）:")
    print("     export HTTP_PROXY=http://proxy:8080")
    print("     export HTTPS_PROXY=http://proxy:8080")
    print("     python download_dataset.py")
    print()
    print("  3. 尝试禁用 DNS 缓存:")
    print("     sudo dscacheutil -flushcache")
    print()
    print("  4. 尝试更换 DNS:")
    print("     # macOS: 系统偏好设置 → 网络 → Wi-Fi → 高级 → DNS")
    print("     # 或尝试 8.8.8.8, 1.1.1.1")
    print()
    print("📋 手动下载方案:")
    print("  1. 访问 https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro")
    print("  2. 点击 'Files' 标签")
    print("  3. 找到 'test-00000-of-00001.parquet' 文件")
    print("  4. 右键 → 在浏览器中下载（或用下载工具）")
    print("  5. 下载后保存到 ~/datasets/SWE-bench_Pro/")
    print()
    print("💡 其他选项:")
    print("  - 使用 VPN 可能改善连接")
    print("  - 在网络较好的机器上下载后转移")
    print("  - 等待网络恢复后重试")
    print()
    return 1

if __name__ == "__main__":
    sys.exit(main())
