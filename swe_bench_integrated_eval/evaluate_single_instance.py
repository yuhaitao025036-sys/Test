#!/usr/bin/env python3
"""
单实例实时评估脚本

功能:
1. 接收单个 instance_id 的 prediction 文件
2. 转换为 patch 格式
3. 立即调用评估逻辑（复用 swe_bench_pro_eval.py 核心函数）
4. 返回评估结果

用法:
  python evaluate_single_instance.py \
    --instance-id "instance_xxx" \
    --prediction-file "./output/predictions/instance_xxx.json" \
    --dataset-path "/ssd1/Dejavu/datasets/SWE-bench_Pro/test-python.parquet" \
    --scripts-dir "./SWE-bench_Pro-os/run_scripts" \
    --output-dir "./output/eval_results" \
    --dockerhub-username jefzda \
    --use-local-docker
"""

import argparse
import json
import os
import sys
from pathlib import Path
import pandas as pd

# 添加 SWE-bench_Pro-os 目录到 sys.path
script_dir = Path(__file__).parent
swe_bench_dir = script_dir / "SWE-bench_Pro-os"
sys.path.insert(0, str(swe_bench_dir))

from swe_bench_pro_eval import eval_with_docker, eval_with_modal


def load_dataset_as_dataframe(dataset_path):
    """从 parquet 文件加载数据集并转换为 DataFrame"""
    if dataset_path.endswith('.parquet'):
        # 使用 pandas 直接读取 parquet
        df = pd.read_parquet(dataset_path)
        print(f"✓ 数据集加载完成: {len(df)} 个任务")
        return df
    elif dataset_path.endswith('.csv'):
        # 兼容 CSV 格式
        df = pd.read_csv(dataset_path)
        print(f"✓ 数据集加载完成 (CSV): {len(df)} 个任务")
        return df
    else:
        raise ValueError(f"Unsupported dataset format: {dataset_path}")


def ensure_dataset_columns(df):
    """确保数据集包含评估所需的列"""
    required_columns = ['instance_id', 'fail_to_pass', 'pass_to_pass']
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")
    return df


def load_prediction(prediction_file):
    """加载单个 prediction 文件"""
    if not os.path.exists(prediction_file):
        raise FileNotFoundError(f"Prediction file not found: {prediction_file}")
    
    with open(prediction_file, 'r') as f:
        prediction = json.load(f)
    
    return prediction


def convert_prediction_to_patch(prediction):
    """将 prediction 转换为 patch 格式"""
    # 从 prediction 中提取 patch
    # 根据 test_tmux_cc_experience.py 的输出格式，model_patch 字段存储了 patch
    patch = prediction.get("model_patch", "")
    instance_id = prediction.get("instance_id", "")
    
    if not patch:
        print(f"Warning: No patch found in prediction for {instance_id}")
        return ""
    
    return patch


def save_result_to_task_dir(result, task_dir):
    """保存评估结果到任务目录的 evaluation 子文件夹"""
    if not task_dir:
        return
    
    import shutil
    
    # 创建评估子目录
    eval_subdir = os.path.join(task_dir, "evaluation")
    os.makedirs(eval_subdir, exist_ok=True)
    
    # 保存评估结果
    eval_result_file = os.path.join(eval_subdir, "result.json")
    with open(eval_result_file, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"  ✓ Saved: evaluation/result.json")


def evaluate_single(
    instance_id,
    prediction_file,
    dataset_path,
    scripts_dir,
    dockerhub_username,
    use_local_docker=True,
    output_dir="./eval_results",
    docker_platform=None,
    prefix="eval",
    task_dir=None  # 新增：任务目录，用于保存详细的评估日志
):
    """评估单个 instance"""
    
    print(f"========================================")
    print(f"Evaluating: {instance_id}")
    print(f"========================================")
    
    # 1. 加载 prediction
    print(f"[1/5] Loading prediction from {prediction_file}")
    try:
        prediction = load_prediction(prediction_file)
    except Exception as e:
        error_result = {
            "instance_id": instance_id,
            "error": f"Failed to load prediction: {str(e)}",
            "error_stage": "load_prediction",
            "resolved": False,
            "fail_to_pass_passed": False,
            "fail_to_pass_success_count": 0,
            "fail_to_pass_failed_count": 0,
            "fail_to_pass_total_count": 0,
            "fail_to_pass_success_rate": 0.0,
            "fail_to_pass_failed_rate": 0.0,
            "pass_to_pass_passed": False,
            "pass_to_pass_success_count": 0,
            "pass_to_pass_failed_count": 0,
            "pass_to_pass_total_count": 0,
            "pass_to_pass_success_rate": 0.0,
            "pass_to_pass_failed_rate": 0.0,
            "overall": False,
            "total_tests_run": 0,
            "total_tests_passed": 0,
            "total_tests_failed": 0,
            "overall_test_pass_rate": 0.0
        }
        print(f"Error loading prediction: {e}")
        save_result_to_task_dir(error_result, task_dir)
        return error_result
    
    # 2. 转换为 patch
    print(f"[2/5] Converting prediction to patch format")
    patch = convert_prediction_to_patch(prediction)
    if not patch or not patch.strip():
        error_result = {
            "instance_id": instance_id,
            "error": "Empty patch - model did not generate a valid patch",
            "error_stage": "convert_patch",
            "resolved": False,
            "fail_to_pass_passed": False,
            "fail_to_pass_success_count": 0,
            "fail_to_pass_failed_count": 0,
            "fail_to_pass_total_count": 0,
            "fail_to_pass_success_rate": 0.0,
            "fail_to_pass_failed_rate": 0.0,
            "pass_to_pass_passed": False,
            "pass_to_pass_success_count": 0,
            "pass_to_pass_failed_count": 0,
            "pass_to_pass_total_count": 0,
            "pass_to_pass_success_rate": 0.0,
            "pass_to_pass_failed_rate": 0.0,
            "overall": False,
            "total_tests_run": 0,
            "total_tests_passed": 0,
            "total_tests_failed": 0,
            "overall_test_pass_rate": 0.0
        }
        print(f"Error: Empty patch for {instance_id}")
        save_result_to_task_dir(error_result, task_dir)
        return error_result
    
    # 3. 从数据集文件加载 instance 配置
    print(f"[3/5] Loading test configuration from {dataset_path}")
    try:
        # 直接从 parquet/csv 读取，确保数据一致性
        dataset_df = load_dataset_as_dataframe(dataset_path)
        dataset_df = ensure_dataset_columns(dataset_df)
        
        # 先根据 instance_id 筛选
        matching_rows = dataset_df[dataset_df["instance_id"] == instance_id]
        
        if len(matching_rows) == 0:
            error_result = {
                "instance_id": instance_id,
                "error": f"Instance {instance_id} not found in dataset",
                "error_stage": "load_dataset",
                "resolved": False,
                "fail_to_pass_passed": False,
                "fail_to_pass_success_count": 0,
                "fail_to_pass_failed_count": 0,
                "fail_to_pass_total_count": 0,
                "fail_to_pass_success_rate": 0.0,
                "fail_to_pass_failed_rate": 0.0,
                "pass_to_pass_passed": False,
                "pass_to_pass_success_count": 0,
                "pass_to_pass_failed_count": 0,
                "pass_to_pass_total_count": 0,
                "pass_to_pass_success_rate": 0.0,
                "pass_to_pass_failed_rate": 0.0,
                "overall": False,
                "total_tests_run": 0,
                "total_tests_passed": 0,
                "total_tests_failed": 0,
                "overall_test_pass_rate": 0.0
            }
            print(f"Error: Instance {instance_id} not found in dataset")
            save_result_to_task_dir(error_result, task_dir)
            return error_result
        
        # 获取第一行作为 Series，并转换为字典（保留 instance_id）
        raw_sample = matching_rows.iloc[0].to_dict()
        
    except Exception as e:
        error_result = {
            "instance_id": instance_id,
            "error": f"Failed to load dataset: {str(e)}",
            "error_stage": "load_dataset",
            "resolved": False,
            "fail_to_pass_passed": False,
            "fail_to_pass_success_count": 0,
            "fail_to_pass_failed_count": 0,
            "fail_to_pass_total_count": 0,
            "fail_to_pass_success_rate": 0.0,
            "fail_to_pass_failed_rate": 0.0,
            "pass_to_pass_passed": False,
            "pass_to_pass_success_count": 0,
            "pass_to_pass_failed_count": 0,
            "pass_to_pass_total_count": 0,
            "pass_to_pass_success_rate": 0.0,
            "pass_to_pass_failed_rate": 0.0,
            "overall": False,
            "total_tests_run": 0,
            "total_tests_passed": 0,
            "total_tests_failed": 0,
            "overall_test_pass_rate": 0.0
        }
        print(f"Error loading dataset: {e}")
        import traceback
        traceback.print_exc()
        save_result_to_task_dir(error_result, task_dir)
        return error_result
    
    # 4. 执行 Docker 评估
    print(f"[4/5] Running Docker evaluation")
    eval_fn = eval_with_docker if use_local_docker else eval_with_modal
    
    # 保存当前工作目录
    original_cwd = os.getcwd()

    # 在 chdir 之前将相对路径转为绝对路径
    abs_output_dir = os.path.abspath(output_dir)
    abs_scripts_dir = os.path.abspath(scripts_dir)

    try:
        # 切换到 SWE-bench_Pro-os 目录（因为 eval_with_docker 依赖相对路径）
        swe_bench_dir = os.path.join(os.path.dirname(__file__), "SWE-bench_Pro-os")
        os.chdir(swe_bench_dir)

        output = eval_fn(
            patch=patch,
            sample=raw_sample,
            output_dir=abs_output_dir,
            dockerhub_username=dockerhub_username,
            scripts_dir=abs_scripts_dir,
            prefix=prefix,
            redo=False,
            block_network=False,
            docker_platform=docker_platform,
            ground_truth_patch=""
        )
        
    finally:
        # 恢复原工作目录
        os.chdir(original_cwd)
    
    try:
        if output is None:
            error_result = {
                "instance_id": instance_id,
                "error": "Docker evaluation returned None - check Docker logs for details",
                "error_stage": "docker_evaluation",
                "resolved": False,
                "fail_to_pass_passed": False,
                "fail_to_pass_success_count": 0,
                "fail_to_pass_failed_count": 0,
                "fail_to_pass_total_count": 0,
                "fail_to_pass_success_rate": 0.0,
                "fail_to_pass_failed_rate": 0.0,
                "pass_to_pass_passed": False,
                "pass_to_pass_success_count": 0,
                "pass_to_pass_failed_count": 0,
                "pass_to_pass_total_count": 0,
                "pass_to_pass_success_rate": 0.0,
                "pass_to_pass_failed_rate": 0.0,
                "overall": False,
                "total_tests_run": 0,
                "total_tests_passed": 0,
                "total_tests_failed": 0,
                "overall_test_pass_rate": 0.0
            }
            print(f"Error: Evaluation returned None for {instance_id}")
            save_result_to_task_dir(error_result, task_dir)
            return error_result
    except Exception as e:
        error_result = {
            "instance_id": instance_id,
            "error": f"Docker evaluation exception: {str(e)}",
            "error_stage": "docker_evaluation",
            "resolved": False,
            "fail_to_pass_passed": False,
            "fail_to_pass_success_count": 0,
            "fail_to_pass_failed_count": 0,
            "fail_to_pass_total_count": 0,
            "fail_to_pass_success_rate": 0.0,
            "fail_to_pass_failed_rate": 0.0,
            "pass_to_pass_passed": False,
            "pass_to_pass_success_count": 0,
            "pass_to_pass_failed_count": 0,
            "pass_to_pass_total_count": 0,
            "pass_to_pass_success_rate": 0.0,
            "pass_to_pass_failed_rate": 0.0,
            "overall": False,
            "total_tests_run": 0,
            "total_tests_passed": 0,
            "total_tests_failed": 0,
            "overall_test_pass_rate": 0.0
        }
        print(f"Error during evaluation: {e}")
        import traceback
        traceback.print_exc()
        save_result_to_task_dir(error_result, task_dir)
        return error_result
    
    # 5. 解析测试结果
    print(f"[5/5] Parsing test results")
    try:
        passed_tests = {x["name"] for x in output["tests"] if x["status"] == "PASSED"}
        failed_tests = {x["name"] for x in output["tests"] if x["status"] == "FAILED"}
        all_tests = {x["name"] for x in output["tests"]}
        
        f2p = set(eval(raw_sample["fail_to_pass"]))
        p2p = set(eval(raw_sample["pass_to_pass"]))
        
        # 计算详细的成功率
        f2p_success = len(f2p & passed_tests)
        f2p_total = len(f2p)
        f2p_failed = len(f2p & failed_tests)
        f2p_rate = f2p_success / f2p_total if f2p_total > 0 else 0.0
        f2p_passed = f2p <= passed_tests
        
        p2p_success = len(p2p & passed_tests)
        p2p_total = len(p2p)
        p2p_failed = len(p2p & failed_tests)
        p2p_rate = p2p_success / p2p_total if p2p_total > 0 else 0.0
        p2p_passed = p2p <= passed_tests
        
        overall_passed = f2p_passed and p2p_passed
        
        result = {
            "instance_id": instance_id,
            "resolved": overall_passed,
            
            # Fail-to-Pass 详细信息
            "fail_to_pass_passed": f2p_passed,
            "fail_to_pass_success_count": f2p_success,
            "fail_to_pass_failed_count": f2p_failed,
            "fail_to_pass_total_count": f2p_total,
            "fail_to_pass_success_rate": round(f2p_rate, 4),
            "fail_to_pass_failed_rate": round(f2p_failed / f2p_total if f2p_total > 0 else 0.0, 4),
            
            # Pass-to-Pass 详细信息
            "pass_to_pass_passed": p2p_passed,
            "pass_to_pass_success_count": p2p_success,
            "pass_to_pass_failed_count": p2p_failed,
            "pass_to_pass_total_count": p2p_total,
            "pass_to_pass_success_rate": round(p2p_rate, 4),
            "pass_to_pass_failed_rate": round(p2p_failed / p2p_total if p2p_total > 0 else 0.0, 4),
            
            # 总体信息
            "overall": overall_passed,
            "total_tests_run": len(all_tests),
            "total_tests_passed": len(passed_tests),
            "total_tests_failed": len(failed_tests),
            "overall_test_pass_rate": round(len(passed_tests) / len(all_tests) if len(all_tests) > 0 else 0.0, 4)
        }
        
        print(f"")
        print(f"Results:")
        print(f"  Fail-to-Pass: {f2p_success}/{f2p_total} passed, {f2p_failed} failed = {f2p_rate:.2%} {'✓' if f2p_passed else '✗'}")
        print(f"  Pass-to-Pass: {p2p_success}/{p2p_total} passed, {p2p_failed} failed = {p2p_rate:.2%} {'✓' if p2p_passed else '✗'}")
        print(f"  Total Tests: {len(passed_tests)}/{len(all_tests)} passed ({len(passed_tests) / len(all_tests) * 100 if len(all_tests) > 0 else 0:.1f}%)")
        print(f"  Overall: {'✓ RESOLVED' if overall_passed else '✗ FAILED'}")
        print(f"")
        
        # 6. 复制评估日志到任务目录（如果指定了 task_dir）
        if task_dir:
            print(f"[6/6] Copying evaluation logs to task directory")
            import shutil

            # 创建评估子目录
            eval_subdir = os.path.join(task_dir, "evaluation")
            os.makedirs(eval_subdir, exist_ok=True)

            # 评估日志的源目录（swe_bench_pro_eval.py 会在 output_dir/instance_id/ 下生成日志）
            eval_logs_src = os.path.join(output_dir, instance_id)

            if os.path.exists(eval_logs_src):
                # 复制所有评估产物文件（去掉 prefix，简化命名）
                files_to_copy = [
                    (f"{prefix}_stdout.log", "stdout.log"),
                    (f"{prefix}_stderr.log", "stderr.log"),
                    (f"{prefix}_git_apply.log", "git_apply.log"),
                    (f"{prefix}_patch_failed.diff", "patch_failed.diff"),
                    (f"{prefix}_output.json", "output.json"),
                    (f"{prefix}_entryscript.sh", "entryscript.sh"),
                    (f"{prefix}_patch.diff", "applied_patch.diff"),
                    (f"{prefix}_ground_truth_patch.diff", "ground_truth_patch.diff"),
                ]

                for src_filename, dest_filename in files_to_copy:
                    src_file = os.path.join(eval_logs_src, src_filename)
                    if os.path.exists(src_file):
                        dest_file = os.path.join(eval_subdir, dest_filename)
                        try:
                            shutil.copy2(src_file, dest_file)
                            print(f"  ✓ Copied: evaluation/{dest_filename}")
                        except Exception as copy_err:
                            print(f"  ⚠️  Failed to copy {src_filename}: {copy_err}")

                # 复制 workspace 目录中可能有的其他有用文件
                workspace_src = os.path.join(eval_logs_src, "workspace")
                if os.path.isdir(workspace_src):
                    workspace_files = ["stdout.log", "stderr.log", "output.json", "git_apply.log", "patch_failed.diff"]
                    for wf in workspace_files:
                        ws_file = os.path.join(workspace_src, wf)
                        dest_file = os.path.join(eval_subdir, dest_filename)
                        # 只复制目标目录中尚未存在的文件（避免覆盖已有的带 prefix 的版本）
                        if os.path.exists(ws_file) and not os.path.exists(os.path.join(eval_subdir, wf)):
                            try:
                                shutil.copy2(ws_file, os.path.join(eval_subdir, wf))
                            except Exception:
                                pass

            # 保存评估结果（使用统一函数）
            save_result_to_task_dir(result, task_dir)
        
        return result
        
    except Exception as e:
        print(f"Error parsing test results: {e}")
        import traceback
        traceback.print_exc()
        
        error_result = {
            "instance_id": instance_id,
            "error": f"Failed to parse test results: {str(e)}",
            "error_stage": "parse_results",
            "resolved": False,
            "fail_to_pass_passed": False,
            "fail_to_pass_success_count": 0,
            "fail_to_pass_failed_count": 0,
            "fail_to_pass_total_count": 0,
            "fail_to_pass_success_rate": 0.0,
            "fail_to_pass_failed_rate": 0.0,
            "pass_to_pass_passed": False,
            "pass_to_pass_success_count": 0,
            "pass_to_pass_failed_count": 0,
            "pass_to_pass_total_count": 0,
            "pass_to_pass_success_rate": 0.0,
            "pass_to_pass_failed_rate": 0.0,
            "overall": False,
            "total_tests_run": 0,
            "total_tests_passed": 0,
            "total_tests_failed": 0,
            "overall_test_pass_rate": 0.0
        }
        save_result_to_task_dir(error_result, task_dir)
        return error_result


def main():
    parser = argparse.ArgumentParser(description="Evaluate a single SWE-bench Pro instance")
    parser.add_argument("--instance-id", required=True, help="Instance ID to evaluate")
    parser.add_argument("--prediction-file", required=True, help="Path to prediction JSON file")
    parser.add_argument("--dataset-path", required=True, 
                        help="Path to dataset file (parquet or CSV)")
    parser.add_argument("--scripts-dir", required=True, help="Directory containing run scripts")
    parser.add_argument("--output-dir", required=True, help="Directory to store evaluation outputs")
    parser.add_argument("--dockerhub-username", required=True, help="Docker Hub username")
    parser.add_argument("--use-local-docker", action="store_true", help="Use local Docker instead of Modal")
    parser.add_argument("--docker-platform", default=None, help="Docker platform (e.g., linux/amd64)")
    parser.add_argument("--prefix", default="eval", help="Prefix for output files")
    parser.add_argument("--task-dir", default=None, help="Task directory to copy evaluation logs to")
    
    args = parser.parse_args()
    
    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 执行评估
    result = evaluate_single(
        instance_id=args.instance_id,
        prediction_file=args.prediction_file,
        dataset_path=args.dataset_path,
        scripts_dir=args.scripts_dir,
        dockerhub_username=args.dockerhub_username,
        use_local_docker=args.use_local_docker,
        output_dir=args.output_dir,
        docker_platform=args.docker_platform,
        prefix=args.prefix,
        task_dir=args.task_dir
    )
    
    if result is None:
        print(f"Evaluation failed for {args.instance_id}")
        sys.exit(1)
    
    # 保存结果到 JSON 文件
    eval_result_file = os.path.join(args.output_dir, f"{args.instance_id}_eval.json")
    with open(eval_result_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Evaluation result saved to: {eval_result_file}")
    
    # 退出码: 0 = resolved, 1 = failed
    sys.exit(0 if result.get("resolved", False) else 1)


if __name__ == "__main__":
    main()
