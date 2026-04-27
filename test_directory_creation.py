#!/usr/bin/env python3
"""
快速测试脚本 - 验证任务目录结构创建
不需要实际运行 ducc，只检查目录创建逻辑
"""

import os
import json

def test_directory_creation():
    """测试任务目录创建"""
    
    # 模拟一个 instance
    test_instance = {
        'instance_id': 'test__test-12345',
        'repo': 'test/test',
        'repo_language': 'Python',
        'problem_statement': 'This is a test problem',
        'requirements': 'pytest',
        'interface': 'test interface',
        'dockerhub_tag': 'test:latest',
        'base_commit': 'abc123',
        'hints': 'test hints',
        'created_at': '2026-04-27',
    }
    
    # 输出目录
    output_dir = './test_output'
    
    # 创建任务目录（与脚本中相同的逻辑）
    instance_id = test_instance['instance_id']
    safe_instance_id = instance_id.replace('/', '_').replace('\\', '_').replace(':', '_')
    task_dir = os.path.join(output_dir, 'tasks', safe_instance_id)
    
    print(f"创建目录: {task_dir}")
    os.makedirs(task_dir, exist_ok=True)
    
    # 保存数据集信息
    dataset_info_file = os.path.join(task_dir, 'dataset_info.json')
    with open(dataset_info_file, 'w', encoding='utf-8') as f:
        dataset_info = {
            'instance_id': instance_id,
            'repo': test_instance.get('repo', ''),
            'repo_language': test_instance.get('repo_language', ''),
            'problem_statement': test_instance.get('problem_statement', ''),
            'requirements': test_instance.get('requirements', ''),
            'interface': test_instance.get('interface', ''),
            'dockerhub_tag': test_instance.get('dockerhub_tag', ''),
            'base_commit': test_instance.get('base_commit', ''),
            'hints': test_instance.get('hints', ''),
            'created_at': test_instance.get('created_at', ''),
        }
        json.dump(dataset_info, f, indent=2, ensure_ascii=False)
    
    # 创建其他测试文件
    files_to_create = [
        ('prompt.txt', 'This is a test prompt'),
        ('ducc_execution.log', 'Test execution log'),
        ('ducc_raw_output.txt', 'Test raw output'),
        ('extracted_patch.diff', 'Test patch'),
        ('task_summary.json', json.dumps({'test': 'summary'}, indent=2)),
        ('README.txt', 'Test README'),
    ]
    
    for filename, content in files_to_create:
        filepath = os.path.join(task_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ 创建文件: {filename}")
    
    # 验证目录结构
    print(f"\n目录结构:")
    print(f"{output_dir}/")
    print(f"└── tasks/")
    print(f"    └── {safe_instance_id}/")
    
    for filename, _ in files_to_create:
        print(f"        ├── {filename}")
    print(f"        └── dataset_info.json")
    
    print(f"\n✓ 测试完成！")
    print(f"\n查看创建的文件:")
    print(f"  ls -la {task_dir}")
    print(f"\n清理测试文件:")
    print(f"  rm -rf {output_dir}")

if __name__ == '__main__':
    test_directory_creation()
