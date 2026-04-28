#!/usr/bin/env python3
"""
SWE-bench 评估失败分析工具

帮助快速定位和分类评估任务失败的原因
"""

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
import argparse


class FailureAnalyzer:
    """评估失败分析器"""
    
    def __init__(self, log_file, preds_file, output_dir=None):
        self.log_file = log_file
        self.preds_file = preds_file
        self.output_dir = output_dir
        
        # 失败分类
        self.failure_categories = {
            'disk_space': [],      # 磁盘空间不足
            'timeout': [],          # 超时
            'patch_failed': [],     # Patch 应用失败
            'no_patch': [],         # 没有生成 patch
            'container_error': [],  # 容器错误
            'other': []             # 其他错误
        }
        
        # 项目统计
        self.project_stats = defaultdict(lambda: {
            'total': 0,
            'success': 0,
            'failed': 0,
            'failures': []
        })
    
    def load_log_tasks(self):
        """从日志文件加载任务列表"""
        tasks = []
        with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if line.startswith('[') and '/100]' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        task_id = parts[1]
                        index = parts[0].strip('[]').split('/')[0]
                        tasks.append({
                            'index': int(index),
                            'task_id': task_id
                        })
        return tasks
    
    def load_successful_tasks(self):
        """从结果文件加载成功的任务"""
        successful = set()
        if not os.path.exists(self.preds_file):
            print(f"⚠️  结果文件不存在: {self.preds_file}")
            return successful
        
        with open(self.preds_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    successful.add(data['instance_id'])
        return successful
    
    def analyze_failure_reason(self, task_id, log_content):
        """分析单个任务的失败原因"""
        # 查找该任务的日志
        task_log = self.extract_task_log(task_id, log_content)
        
        if 'No space left on device' in task_log:
            return 'disk_space', '磁盘空间不足'
        elif 'timeout' in task_log.lower() or 'timed out' in task_log.lower():
            return 'timeout', '执行超时'
        elif 'patch failed' in task_log.lower() or 'corrupt patch' in task_log:
            return 'patch_failed', 'Patch 应用失败'
        elif '✓ Patch 已保存' not in task_log:
            return 'no_patch', '未生成有效 Patch'
        elif 'container' in task_log.lower() and 'error' in task_log.lower():
            return 'container_error', '容器错误'
        else:
            return 'other', '其他错误'
    
    def extract_task_log(self, task_id, log_content):
        """提取单个任务的日志内容"""
        lines = log_content.split('\n')
        task_lines = []
        in_task = False
        
        for line in lines:
            if task_id in line and '处理任务:' in line:
                in_task = True
            elif in_task:
                task_lines.append(line)
                if '处理完成:' in line or line.startswith('[') and '/100]' in line:
                    break
        
        return '\n'.join(task_lines)
    
    def get_project_name(self, task_id):
        """从任务ID提取项目名称"""
        # instance_gravitational__teleport-xxxxx -> gravitational/teleport
        parts = task_id.replace('instance_', '').split('-')[0]
        return parts.replace('__', '/')
    
    def analyze(self):
        """执行完整分析"""
        print("=" * 80)
        print("🔍 SWE-bench 评估失败分析")
        print("=" * 80)
        print()
        
        # 1. 加载数据
        print("[1/4] 加载数据...")
        log_tasks = self.load_log_tasks()
        successful_tasks = self.load_successful_tasks()
        
        print(f"  ✓ 日志中的任务数: {len(log_tasks)}")
        print(f"  ✓ 成功的任务数: {len(successful_tasks)}")
        print(f"  ✓ 失败的任务数: {len(log_tasks) - len(successful_tasks)}")
        print()
        
        # 2. 读取完整日志
        print("[2/4] 分析失败原因...")
        with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
            log_content = f.read()
        
        failed_tasks = []
        for task in log_tasks:
            task_id = task['task_id']
            project = self.get_project_name(task_id)
            
            # 更新项目统计
            self.project_stats[project]['total'] += 1
            
            if task_id not in successful_tasks:
                # 失败任务
                category, reason = self.analyze_failure_reason(task_id, log_content)
                self.failure_categories[category].append({
                    'index': task['index'],
                    'task_id': task_id,
                    'project': project,
                    'reason': reason
                })
                failed_tasks.append(task)
                self.project_stats[project]['failed'] += 1
                self.project_stats[project]['failures'].append(reason)
            else:
                # 成功任务
                self.project_stats[project]['success'] += 1
        
        print(f"  ✓ 分析完成: {len(failed_tasks)} 个失败任务")
        print()
        
        # 3. 生成报告
        print("[3/4] 生成分析报告...")
        self.print_summary()
        self.print_failure_details()
        self.print_project_analysis()
        
        # 4. 保存报告
        if self.output_dir:
            print(f"\n[4/4] 保存报告到: {self.output_dir}")
            self.save_reports()
        else:
            print("\n[4/4] 跳过保存（未指定输出目录）")
    
    def print_summary(self):
        """打印总体摘要"""
        print("=" * 80)
        print("📊 失败原因分类统计")
        print("=" * 80)
        
        total_failures = sum(len(tasks) for tasks in self.failure_categories.values())
        
        for category, tasks in sorted(self.failure_categories.items(), 
                                     key=lambda x: len(x[1]), reverse=True):
            if tasks:
                count = len(tasks)
                percentage = (count / total_failures * 100) if total_failures > 0 else 0
                emoji = self.get_category_emoji(category)
                print(f"{emoji} {self.get_category_name(category):20s}: {count:3d} ({percentage:5.1f}%)")
        
        print()
    
    def print_failure_details(self):
        """打印失败详情"""
        print("=" * 80)
        print("📋 失败任务详细列表")
        print("=" * 80)
        print()
        
        for category, tasks in self.failure_categories.items():
            if not tasks:
                continue
            
            print(f"\n{self.get_category_emoji(category)} {self.get_category_name(category)} ({len(tasks)}个)")
            print("-" * 80)
            
            for task in sorted(tasks, key=lambda x: x['index']):
                print(f"  [{task['index']:3d}] {task['project']:30s} | {task['task_id'][:60]}")
            
            if len(tasks) > 10:
                print(f"  ... (共 {len(tasks)} 个任务)")
        
        print()
    
    def print_project_analysis(self):
        """打印项目维度分析"""
        print("=" * 80)
        print("🏗️  项目维度分析")
        print("=" * 80)
        print()
        
        print(f"{'项目':<35s} | {'总数':>5s} | {'成功':>5s} | {'失败':>5s} | {'成功率':>8s}")
        print("-" * 80)
        
        for project, stats in sorted(self.project_stats.items(), 
                                     key=lambda x: x[1]['failed'], reverse=True):
            if stats['total'] == 0:
                continue
            
            success_rate = (stats['success'] / stats['total'] * 100)
            
            # 根据成功率选择 emoji
            if success_rate >= 90:
                emoji = "✅"
            elif success_rate >= 70:
                emoji = "⚠️ "
            else:
                emoji = "❌"
            
            print(f"{emoji} {project:<32s} | {stats['total']:5d} | {stats['success']:5d} | "
                  f"{stats['failed']:5d} | {success_rate:7.1f}%")
        
        print()
        
        # 打印最常见的失败原因
        print("🔥 高失败率项目的主要失败原因:")
        print("-" * 80)
        
        for project, stats in sorted(self.project_stats.items(), 
                                     key=lambda x: x[1]['failed'], reverse=True)[:10]:
            if stats['failed'] == 0:
                continue
            
            failure_reasons = Counter(stats['failures'])
            top_reason = failure_reasons.most_common(1)[0] if failure_reasons else ('未知', 0)
            print(f"  {project:<35s}: {top_reason[0]} ({top_reason[1]}次)")
        
        print()
    
    def save_reports(self):
        """保存分析报告"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 保存 JSON 格式的详细报告
        report = {
            'summary': {
                'total_tasks': sum(s['total'] for s in self.project_stats.values()),
                'successful_tasks': sum(s['success'] for s in self.project_stats.values()),
                'failed_tasks': sum(s['failed'] for s in self.project_stats.values()),
            },
            'failure_categories': {
                cat: [{'index': t['index'], 'project': t['project'], 
                      'task_id': t['task_id'], 'reason': t['reason']} 
                     for t in tasks]
                for cat, tasks in self.failure_categories.items()
            },
            'project_stats': {
                project: {
                    'total': stats['total'],
                    'success': stats['success'],
                    'failed': stats['failed'],
                    'success_rate': round(stats['success'] / stats['total'] * 100, 2) 
                                   if stats['total'] > 0 else 0,
                    'failure_reasons': dict(Counter(stats['failures']))
                }
                for project, stats in self.project_stats.items()
            }
        }
        
        report_file = os.path.join(self.output_dir, 'failure_analysis.json')
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ JSON 报告: {report_file}")
        
        # 保存需要重跑的任务列表
        failed_indices = []
        for tasks in self.failure_categories.values():
            failed_indices.extend([t['index'] for t in tasks])
        
        rerun_file = os.path.join(self.output_dir, 'failed_task_indices.txt')
        with open(rerun_file, 'w') as f:
            f.write(','.join(map(str, sorted(failed_indices))))
        
        print(f"  ✓ 失败任务索引: {rerun_file}")
        print(f"    重跑命令: python test_tmux_cc_experience.py --indices {','.join(map(str, sorted(failed_indices)[:10]))}...")
    
    @staticmethod
    def get_category_emoji(category):
        """获取分类的 emoji"""
        emojis = {
            'disk_space': '💾',
            'timeout': '⏱️ ',
            'patch_failed': '🔧',
            'no_patch': '📝',
            'container_error': '🐳',
            'other': '❓'
        }
        return emojis.get(category, '❓')
    
    @staticmethod
    def get_category_name(category):
        """获取分类的中文名称"""
        names = {
            'disk_space': '磁盘空间不足',
            'timeout': '执行超时',
            'patch_failed': 'Patch 应用失败',
            'no_patch': '未生成 Patch',
            'container_error': '容器错误',
            'other': '其他错误'
        }
        return names.get(category, '未知错误')


def main():
    parser = argparse.ArgumentParser(description='SWE-bench 评估失败分析工具')
    parser.add_argument('--log', default='./batch_0_50.log', 
                       help='日志文件路径')
    parser.add_argument('--preds', default='./all_preds.jsonl',
                       help='预测结果文件路径')
    parser.add_argument('--output', default='./failure_analysis',
                       help='输出目录（保存报告）')
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.log):
        print(f"❌ 日志文件不存在: {args.log}")
        sys.exit(1)
    
    # 执行分析
    analyzer = FailureAnalyzer(args.log, args.preds, args.output)
    analyzer.analyze()
    
    print()
    print("=" * 80)
    print("✅ 分析完成！")
    print("=" * 80)


if __name__ == '__main__':
    main()
