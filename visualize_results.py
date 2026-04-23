#!/usr/bin/env python3
"""
SWE-bench Pro 结果可视化分析工具
生成图表和详细统计报告
"""

import json
import os
from typing import Dict, List
from collections import defaultdict

def load_results(output_dir: str) -> List[Dict]:
    """加载评测结果"""
    summary_file = os.path.join(output_dir, 'all_results.jsonl')
    results = []
    
    if not os.path.exists(summary_file):
        print(f"错误: 未找到结果文件 {summary_file}")
        return results
    
    with open(summary_file, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    results.append(json.loads(line))
                except:
                    continue
    
    return results


def generate_ascii_bar_chart(data: Dict[str, float], title: str, max_width: int = 50):
    """生成ASCII条形图"""
    print(f"\n{title}")
    print("=" * 70)
    
    if not data:
        print("无数据")
        return
    
    max_value = max(data.values()) if data.values() else 1
    
    for label, value in data.items():
        bar_length = int((value / max_value) * max_width) if max_value > 0 else 0
        bar = '█' * bar_length + '░' * (max_width - bar_length)
        print(f"{label:<25} {bar} {value:>6.1f}%")


def analyze_by_category(results: List[Dict]):
    """按分类分析（如果数据集包含分类信息）"""
    # 提取可能的分类维度
    categories = defaultdict(lambda: {'total': 0, 'resolved': 0, 'with_patch': 0})
    
    for r in results:
        # 从 instance_id 提取项目信息（如 django__django-12345）
        instance_id = r.get('instance_id', '')
        project = instance_id.split('__')[0] if '__' in instance_id else 'unknown'
        
        categories[project]['total'] += 1
        if r.get('patch'):
            categories[project]['with_patch'] += 1
        if r.get('validation', {}).get('success'):
            categories[project]['resolved'] += 1
    
    return categories


def generate_comparison_table(results: List[Dict]):
    """生成对比表格"""
    print("\n" + "=" * 70)
    print("详细对比分析")
    print("=" * 70)
    
    # 按项目分组
    projects = defaultdict(lambda: {'total': 0, 'resolved': 0, 'patch': 0})
    
    for r in results:
        instance_id = r.get('instance_id', '')
        project = instance_id.split('__')[0] if '__' in instance_id else 'unknown'
        
        projects[project]['total'] += 1
        if r.get('patch'):
            projects[project]['patch'] += 1
        if r.get('validation', {}).get('success'):
            projects[project]['resolved'] += 1
    
    # 打印表格
    print(f"\n{'项目':<20} {'总数':<8} {'Patch':<10} {'解决':<10} {'解决率':<10}")
    print("-" * 70)
    
    sorted_projects = sorted(projects.items(), key=lambda x: x[1]['total'], reverse=True)
    for project, stats in sorted_projects[:20]:  # 显示前20个
        total = stats['total']
        patch = stats['patch']
        resolved = stats['resolved']
        rate = (resolved / total * 100) if total > 0 else 0
        
        print(f"{project:<20} {total:<8} {patch:<10} {resolved:<10} {rate:<10.1f}%")
    
    if len(sorted_projects) > 20:
        print(f"... (还有 {len(sorted_projects) - 20} 个项目)")


def generate_time_analysis(results: List[Dict]):
    """生成时间分析（如果有时间戳）"""
    # 这里可以添加时间相关的分析
    # 如：每小时处理数量、平均耗时等
    pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description='SWE-bench 结果可视化分析')
    parser.add_argument('--output-dir', default='./swe_bench_output', help='输出目录')
    args = parser.parse_args()
    
    # 加载结果
    results = load_results(args.output_dir)
    
    if not results:
        print("没有找到评测结果")
        return
    
    print("\n" + "="*70)
    print(" " * 20 + "SWE-bench Pro 可视化分析")
    print("="*70)
    
    # 基础统计
    total = len(results)
    with_patch = [r for r in results if r.get('patch')]
    validated = [r for r in results if r.get('validation') is not None]
    resolved = [r for r in validated if r.get('validation', {}).get('success')]
    
    print(f"\n📊 基础统计")
    print(f"  总任务数: {total}")
    print(f"  生成Patch: {len(with_patch)} ({len(with_patch)/total*100:.1f}%)")
    if validated:
        print(f"  验证通过: {len(resolved)} ({len(resolved)/total*100:.1f}%)")
    
    # 1. 成功率分布
    success_data = {
        '已解决': (len(resolved) / total * 100) if total > 0 else 0,
        '生成但失败': ((len(with_patch) - len(resolved)) / total * 100) if total > 0 else 0,
        '未生成Patch': ((total - len(with_patch)) / total * 100) if total > 0 else 0,
    }
    generate_ascii_bar_chart(success_data, "📈 任务完成情况分布")
    
    # 2. 失败原因分析
    failed = [r for r in validated if not r.get('validation', {}).get('success')]
    patch_errors = sum(1 for r in failed if 'Patch apply failed' in r.get('validation', {}).get('error', ''))
    test_failures = sum(1 for r in failed if 'FAILED' in r.get('validation', {}).get('test_output', ''))
    
    if failed:
        failure_data = {
            'Patch应用失败': (patch_errors / len(failed) * 100),
            '测试未通过': (test_failures / len(failed) * 100),
            '其他错误': ((len(failed) - patch_errors - test_failures) / len(failed) * 100),
        }
        generate_ascii_bar_chart(failure_data, "❌ 失败原因分布")
    
    # 3. 代码检索质量
    context_lengths = [r.get('code_context_length', 0) for r in results]
    context_distribution = {
        '无上下文 (0)': sum(1 for l in context_lengths if l == 0) / len(context_lengths) * 100,
        '少量 (<1K)': sum(1 for l in context_lengths if 0 < l < 1000) / len(context_lengths) * 100,
        '中等 (1K-5K)': sum(1 for l in context_lengths if 1000 <= l < 5000) / len(context_lengths) * 100,
        '丰富 (≥5K)': sum(1 for l in context_lengths if l >= 5000) / len(context_lengths) * 100,
    }
    generate_ascii_bar_chart(context_distribution, "📝 代码上下文质量分布")
    
    # 4. 按项目分析
    generate_comparison_table(results)
    
    # 5. 生成排名
    print("\n" + "="*70)
    print("🏆 困难任务 Top 10（未解决但尝试次数多）")
    print("="*70)
    unresolved = [r for r in results if not r.get('validation', {}).get('success')]
    for i, r in enumerate(unresolved[:10], 1):
        instance_id = r.get('instance_id', 'unknown')
        has_patch = '有Patch' if r.get('patch') else '无Patch'
        print(f"  {i:2d}. {instance_id:<45} ({has_patch})")
    
    print("\n" + "="*70)
    print("✅ 成功解决的任务")
    print("="*70)
    for i, r in enumerate(resolved[:10], 1):
        instance_id = r.get('instance_id', 'unknown')
        print(f"  {i:2d}. {instance_id}")
    
    if len(resolved) > 10:
        print(f"  ... (还有 {len(resolved) - 10} 个)")
    
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    main()
