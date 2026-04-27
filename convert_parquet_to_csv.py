#!/usr/bin/env python3
"""
将 SWE-bench Pro 的 Parquet 文件转换为 CSV

官方 swe_bench_pro_eval.py 使用 pd.read_csv(),
但数据集是 Parquet 格式,所以需要转换。

用法:
  python convert_parquet_to_csv.py
"""

import pandas as pd
import sys
import os

def convert_parquet_to_csv():
    parquet_file = '/ssd1/Dejavu/datasets/SWE-bench_Pro/test-00000-of-00001.parquet'
    csv_file = 'swe_bench_pro_test.csv'
    
    print(f"读取 Parquet 文件: {parquet_file}")
    
    if not os.path.exists(parquet_file):
        print(f"✗ 文件不存在: {parquet_file}")
        sys.exit(1)
    
    # 读取 Parquet
    df = pd.read_parquet(parquet_file)
    
    print(f"✓ 读取成功: {len(df)} 行, {len(df.columns)} 列")
    print(f"\n列名:")
    for col in df.columns:
        print(f"  - {col}")
    
    # 保存为 CSV
    print(f"\n保存为 CSV: {csv_file}")
    df.to_csv(csv_file, index=False)
    
    # 验证
    file_size = os.path.getsize(csv_file) / 1024 / 1024
    print(f"✓ 转换完成!")
    print(f"  文件大小: {file_size:.2f} MB")
    print(f"  输出文件: {os.path.abspath(csv_file)}")
    
    # 显示示例
    print(f"\n前 3 行预览:")
    print(df.head(3)[['instance_id', 'repo', 'repo_language']].to_string())

if __name__ == '__main__':
    convert_parquet_to_csv()
