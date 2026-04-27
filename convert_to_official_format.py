#!/usr/bin/env python3
"""
将我们的 all_preds.jsonl 转换为 SWE-bench Pro 官方格式

用法:
  python convert_to_official_format.py \
    --input swe_bench_output_ducc/all_preds.jsonl \
    --prefix ducc_standalone \
    --output ducc_patches.json
"""

import json
import argparse
from pathlib import Path


def convert_to_official_format(input_file: str, prefix: str, output_file: str):
    """转换格式"""
    
    print(f"读取输入文件: {input_file}")
    
    if not Path(input_file).exists():
        print(f"✗ 文件不存在: {input_file}")
        return
    
    patches = []
    
    # 读取 JSONL 文件
    with open(input_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                
                # 我们的格式 → 官方格式
                patch_entry = {
                    "instance_id": data.get("instance_id"),
                    "patch": data.get("model_patch", ""),
                    "prefix": prefix
                }
                
                patches.append(patch_entry)
                
            except json.JSONDecodeError as e:
                print(f"⚠️  第 {line_num} 行 JSON 解析失败: {e}")
                continue
    
    if not patches:
        print(f"✗ 没有找到任何有效的 patch!")
        print(f"   请检查 {input_file} 是否有内容")
        return
    
    # 写入输出文件
    print(f"\n转换完成:")
    print(f"  输入: {len(patches)} 个 patches")
    print(f"  前缀: {prefix}")
    print(f"  输出: {output_file}")
    
    with open(output_file, 'w') as f:
        json.dump(patches, f, indent=2)
    
    print(f"\n✓ 成功写入: {output_file}")
    
    # 显示示例
    if patches:
        print(f"\n示例 patch (第一个):")
        print(f"  Instance ID: {patches[0]['instance_id']}")
        print(f"  Patch 长度: {len(patches[0]['patch'])} 字符")
        print(f"  Prefix: {patches[0]['prefix']}")


def main():
    parser = argparse.ArgumentParser(
        description='转换为 SWE-bench Pro 官方格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  python convert_to_official_format.py \\
    --input swe_bench_output_ducc/all_preds.jsonl \\
    --prefix ducc_v1 \\
    --output ducc_patches.json
  
  # 使用日期前缀
  python convert_to_official_format.py \\
    --input swe_bench_output_ducc/all_preds.jsonl \\
    --prefix ducc_$(date +%Y%m%d) \\
    --output patches_$(date +%Y%m%d).json
        """
    )
    
    parser.add_argument(
        '--input',
        required=True,
        help='输入文件 (all_preds.jsonl)'
    )
    parser.add_argument(
        '--prefix',
        required=True,
        help='模型/实验前缀 (e.g., ducc_v1, ducc_optimized)'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='输出文件 (patches.json)'
    )
    
    args = parser.parse_args()
    
    convert_to_official_format(args.input, args.prefix, args.output)


if __name__ == '__main__':
    main()
