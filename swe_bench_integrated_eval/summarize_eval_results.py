#!/usr/bin/env python3
"""
评估结果汇总脚本

功能:
- 扫描 eval_results/ 目录
- 汇总所有 instance 的评估结果
- 生成最终统计报告

用法:
  python summarize_eval_results.py \
    --eval-results-dir "./output/eval_results" \
    --output-file "./output/eval_summary.json"
"""

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List


def load_eval_results(eval_results_dir: str) -> Dict:
    """扫描目录并加载所有评估结果"""
    
    results_dir = Path(eval_results_dir)
    
    if not results_dir.exists():
        print(f"Error: Directory not found: {eval_results_dir}")
        return {}
    
    # 查找所有 *_eval.json 文件
    eval_files = list(results_dir.glob("*_eval.json"))
    
    if not eval_files:
        print(f"Warning: No evaluation result files found in {eval_results_dir}")
        return {}
    
    print(f"Found {len(eval_files)} evaluation result files")
    print("")
    
    all_results = {}
    
    for eval_file in sorted(eval_files):
        try:
            with open(eval_file, 'r') as f:
                result = json.load(f)
                instance_id = result.get("instance_id")
                
                if instance_id:
                    all_results[instance_id] = result
                else:
                    print(f"Warning: No instance_id in {eval_file.name}")
        except Exception as e:
            print(f"Error loading {eval_file.name}: {e}")
    
    return all_results


def calculate_statistics(results: Dict) -> Dict:
    """计算汇总统计"""
    
    if not results:
        return {
            "total": 0,
            "resolved": 0,
            "failed": 0,
            "accuracy": 0.0,
            "fail_to_pass_accuracy": 0.0,
            "pass_to_pass_accuracy": 0.0
        }
    
    total = len(results)
    resolved = sum(1 for r in results.values() if r.get("resolved", False) or r.get("overall", False))
    failed = total - resolved
    
    # 计算各类准确率
    f2p_passed_count = sum(1 for r in results.values() if r.get("fail_to_pass_passed", False))
    p2p_passed_count = sum(1 for r in results.values() if r.get("pass_to_pass_passed", False))
    
    accuracy = resolved / total if total > 0 else 0.0
    f2p_accuracy = f2p_passed_count / total if total > 0 else 0.0
    p2p_accuracy = p2p_passed_count / total if total > 0 else 0.0
    
    # 计算平均成功率
    all_f2p_rates = [r.get("fail_to_pass_rate", 0.0) for r in results.values() if "fail_to_pass_rate" in r]
    all_p2p_rates = [r.get("pass_to_pass_rate", 0.0) for r in results.values() if "pass_to_pass_rate" in r]
    
    avg_f2p_rate = sum(all_f2p_rates) / len(all_f2p_rates) if all_f2p_rates else 0.0
    avg_p2p_rate = sum(all_p2p_rates) / len(all_p2p_rates) if all_p2p_rates else 0.0
    
    # 计算总的成功/总数（跨所有实例）
    total_f2p_success = sum(r.get("fail_to_pass_success_count", 0) for r in results.values())
    total_f2p_count = sum(r.get("fail_to_pass_total_count", 0) for r in results.values())
    total_p2p_success = sum(r.get("pass_to_pass_success_count", 0) for r in results.values())
    total_p2p_count = sum(r.get("pass_to_pass_total_count", 0) for r in results.values())
    
    overall_f2p_rate = total_f2p_success / total_f2p_count if total_f2p_count > 0 else 0.0
    overall_p2p_rate = total_p2p_success / total_p2p_count if total_p2p_count > 0 else 0.0
    
    # 获取失败的实例列表
    failed_instances = [
        instance_id for instance_id, r in results.items()
        if not r.get("resolved", False) and not r.get("overall", False)
    ]
    
    # 获取有错误的实例列表
    error_instances = [
        {"instance_id": instance_id, "error": r.get("error", "Unknown error")}
        for instance_id, r in results.items()
        if "error" in r
    ]
    
    statistics = {
        "total": total,
        "resolved": resolved,
        "failed": failed,
        "accuracy": round(accuracy, 4),
        "fail_to_pass_accuracy": round(f2p_accuracy, 4),
        "pass_to_pass_accuracy": round(p2p_accuracy, 4),
        "avg_fail_to_pass_rate": round(avg_f2p_rate, 4),
        "avg_pass_to_pass_rate": round(avg_p2p_rate, 4),
        "overall_fail_to_pass_rate": round(overall_f2p_rate, 4),
        "overall_pass_to_pass_rate": round(overall_p2p_rate, 4),
        "total_fail_to_pass_tests": {
            "passed": total_f2p_success,
            "total": total_f2p_count,
            "rate": round(overall_f2p_rate, 4)
        },
        "total_pass_to_pass_tests": {
            "passed": total_p2p_success,
            "total": total_p2p_count,
            "rate": round(overall_p2p_rate, 4)
        },
        "failed_instances": failed_instances,
        "error_instances": error_instances
    }
    
    return statistics


def print_summary(statistics: Dict):
    """打印汇总信息"""
    
    print("=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total Instances: {statistics['total']}")
    print(f"Resolved: {statistics['resolved']}")
    print(f"Failed: {statistics['failed']}")
    print(f"Overall Accuracy: {statistics['accuracy']:.2%}")
    print("")
    
    print("-" * 60)
    print("FAIL-TO-PASS METRICS")
    print("-" * 60)
    print(f"Instances with all F2P passed: {statistics['total'] * statistics['fail_to_pass_accuracy']:.0f}/{statistics['total']} ({statistics['fail_to_pass_accuracy']:.2%})")
    print(f"Overall F2P test pass rate: {statistics['total_fail_to_pass_tests']['passed']}/{statistics['total_fail_to_pass_tests']['total']} ({statistics['overall_fail_to_pass_rate']:.2%})")
    print(f"Average per-instance F2P rate: {statistics['avg_fail_to_pass_rate']:.2%}")
    print("")
    
    print("-" * 60)
    print("PASS-TO-PASS METRICS")
    print("-" * 60)
    print(f"Instances with all P2P passed: {statistics['total'] * statistics['pass_to_pass_accuracy']:.0f}/{statistics['total']} ({statistics['pass_to_pass_accuracy']:.2%})")
    print(f"Overall P2P test pass rate: {statistics['total_pass_to_pass_tests']['passed']}/{statistics['total_pass_to_pass_tests']['total']} ({statistics['overall_pass_to_pass_rate']:.2%})")
    print(f"Average per-instance P2P rate: {statistics['avg_pass_to_pass_rate']:.2%}")
    print("")
    
    if statistics['error_instances']:
        print("-" * 60)
        print(f"ERRORS ({len(statistics['error_instances'])} instances)")
        print("-" * 60)
        for err in statistics['error_instances'][:10]:
            print(f"  {err['instance_id']}: {err['error']}")
        if len(statistics['error_instances']) > 10:
            print(f"  ... and {len(statistics['error_instances']) - 10} more")
        print("")
    
    if statistics['failed_instances']:
        print("-" * 60)
        print(f"FAILED INSTANCES ({len(statistics['failed_instances'])} total)")
        print("-" * 60)
        for instance_id in statistics['failed_instances'][:20]:
            print(f"  {instance_id}")
        if len(statistics['failed_instances']) > 20:
            print(f"  ... and {len(statistics['failed_instances']) - 20} more")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Summarize SWE-bench Pro evaluation results")
    parser.add_argument("--eval-results-dir", required=True, help="Directory containing *_eval.json files")
    parser.add_argument("--output-file", help="Output JSON file for summary (optional)")
    parser.add_argument("--detailed-output", help="Output JSON file with all detailed results (optional)")
    
    args = parser.parse_args()
    
    # 加载所有评估结果
    print(f"Loading evaluation results from: {args.eval_results_dir}")
    print("")
    
    results = load_eval_results(args.eval_results_dir)
    
    if not results:
        print("No results to summarize")
        return
    
    # 计算统计
    statistics = calculate_statistics(results)
    
    # 打印摘要
    print_summary(statistics)
    
    # 保存统计摘要
    if args.output_file:
        with open(args.output_file, 'w') as f:
            json.dump(statistics, f, indent=2)
        print(f"\nSummary saved to: {args.output_file}")
    
    # 保存详细结果
    if args.detailed_output:
        detailed = {
            "statistics": statistics,
            "detailed_results": results
        }
        with open(args.detailed_output, 'w') as f:
            json.dump(detailed, f, indent=2)
        print(f"Detailed results saved to: {args.detailed_output}")


if __name__ == "__main__":
    main()
