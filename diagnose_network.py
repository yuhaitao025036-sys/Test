#!/usr/bin/env python3
"""
诊断 HuggingFace 网络连接问题
"""

import sys
import time

def test_webpage_access():
    """测试网页访问"""
    print("测试 1: 网页访问")
    print("-" * 60)
    
    try:
        import requests
        url = "https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro"
        print(f"访问: {url}")
        response = requests.head(url, timeout=10, allow_redirects=True)
        print(f"✓ 网页可访问 (HTTP {response.status_code})")
        return True
    except Exception as e:
        print(f"✗ 网页访问失败: {e}")
        return False

def test_direct_file_access():
    """测试直接文件访问"""
    print("\n测试 2: 直接文件访问")
    print("-" * 60)
    
    try:
        import requests
        url = "https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro/resolve/main/test-00000-of-00001.parquet"
        print(f"访问: {url}")
        response = requests.head(url, timeout=10, allow_redirects=True)
        print(f"✓ 文件可访问 (HTTP {response.status_code})")
        print(f"  Content-Length: {response.headers.get('content-length', 'N/A')} bytes")
        return True
    except Exception as e:
        print(f"✗ 文件访问失败: {e}")
        print(f"  这通常是因为:")
        print(f"  1. HuggingFace CDN 地域限制")
        print(f"  2. 需要特殊请求头（User-Agent, Cookie 等）")
        print(f"  3. 需要登录或认证")
        return False

def test_redirect_chain():
    """测试重定向链"""
    print("\n测试 3: 重定向链追踪")
    print("-" * 60)
    
    try:
        import requests
        url = "https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro/resolve/main/test-00000-of-00001.parquet"
        print(f"追踪: {url}")
        
        # 不跟随重定向，看看是否有重定向
        response = requests.head(url, timeout=10, allow_redirects=False)
        print(f"状态码: {response.status_code}")
        
        if response.status_code in (301, 302, 303, 307, 308):
            print(f"✓ 发现重定向到: {response.headers.get('location', 'N/A')}")
            
            # 跟随重定向
            response = requests.head(url, timeout=10, allow_redirects=True)
            print(f"✓ 最终状态码: {response.status_code}")
            print(f"  最终 URL: {response.url}")
        else:
            print(f"✓ 直接访问成功（无重定向）")
        return True
    except Exception as e:
        print(f"✗ 重定向追踪失败: {e}")
        return False

def test_download_methods():
    """测试各种下载方法"""
    print("\n测试 4: 下载方法测试（仅测试连接，不保存文件）")
    print("-" * 60)
    
    url = "https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro/resolve/main/test-00000-of-00001.parquet"
    
    # 测试 requests
    print("方法 A: requests 库")
    try:
        import requests
        response = requests.get(url, timeout=10, allow_redirects=True, stream=True)
        size = int(response.headers.get('content-length', 0))
        print(f"  ✓ 可下载 (大小: {size / 1024 / 1024:.1f} MB)")
    except Exception as e:
        print(f"  ✗ 失败: {str(e)[:50]}")
    
    # 测试 curl
    print("方法 B: curl 命令")
    try:
        import subprocess
        result = subprocess.run(
            ['curl', '-I', '-L', url],
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            # 查看输出中是否有 Content-Length
            output = result.stdout.decode()
            if 'Content-Length' in output:
                print(f"  ✓ curl 可连接")
            else:
                print(f"  ✓ curl 可连接（但可能需要特殊参数）")
        else:
            print(f"  ✗ curl 失败")
    except Exception as e:
        print(f"  ✗ curl 不可用: {e}")
    
    # 测试 huggingface_hub
    print("方法 C: huggingface_hub 库")
    try:
        from huggingface_hub import hf_hub_url
        hf_url = hf_hub_url("ScaleAI/SWE-bench_Pro", "test-00000-of-00001.parquet", repo_type="dataset")
        print(f"  ✓ huggingface_hub 生成 URL: {hf_url[:60]}...")
    except ImportError:
        print(f"  ✗ huggingface_hub 未安装")
    except Exception as e:
        print(f"  ✗ 失败: {e}")

def test_proxy_settings():
    """测试代理设置"""
    print("\n测试 5: 代理设置")
    print("-" * 60)
    
    import os
    proxies = {
        'HTTP_PROXY': os.environ.get('HTTP_PROXY'),
        'HTTPS_PROXY': os.environ.get('HTTPS_PROXY'),
        'http_proxy': os.environ.get('http_proxy'),
        'https_proxy': os.environ.get('https_proxy'),
    }
    
    active_proxies = {k: v for k, v in proxies.items() if v}
    if active_proxies:
        print("✓ 已配置的代理:")
        for key, val in active_proxies.items():
            print(f"  {key}: {val}")
    else:
        print("✗ 未配置代理")

def main():
    print("="*60)
    print("HuggingFace 网络连接诊断工具")
    print("="*60)
    print()
    
    try:
        test_webpage_access()
        test_direct_file_access()
        test_redirect_chain()
        test_download_methods()
        test_proxy_settings()
    except KeyboardInterrupt:
        print("\n用户中断")
        return 1
    except Exception as e:
        print(f"\n诊断失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print()
    print("="*60)
    print("诊断完成")
    print("="*60)
    print()
    print("📋 建议的下载方式（按优先级）:")
    print("1. 运行: python download_dataset.py")
    print("2. 或运行: bash download_dataset.sh")
    print("3. 或手动访问网页下载")
    print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
