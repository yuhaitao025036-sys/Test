#!/usr/bin/env python3
"""
Quick test examples for test_tmux_cc.py

Run these to verify the script works correctly.
"""

import os
import subprocess
import sys
import tempfile


def run_example(name, cmd):
    """Run an example command."""
    print(f"\n{'='*60}")
    print(f"Example: {name}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    script_path = os.path.join(os.path.dirname(__file__), "test_tmux_cc.py")
    
    if not os.path.exists(script_path):
        print(f"Error: {script_path} not found!")
        sys.exit(1)
    
    print("Tmux CC Experience - Quick Test Examples")
    print("=" * 60)
    
    # Example 1: Simple batch mode (no tmux)
    print("\n1. Testing batch mode (no tmux)...")
    print("   This will run ducc without tmux and print the output.")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a simple test file
        test_file = os.path.join(tmpdir, "test.txt")
        with open(test_file, "w") as f:
            f.write("Hello World")
        
        cmd = [
            "python3", script_path,
            "--prompt", "Read the test.txt file and tell me its content",
            "--cwd", tmpdir,
        ]
        
        run_example("Batch Mode - Simple Read", cmd)
    
    # Example 2: Interactive mode (with tmux)
    print("\n2. Testing interactive mode (with tmux)...")
    print("   This will create a tmux session. You can attach to it to watch.")
    print("   Press Ctrl+C to skip this test if you don't want to use tmux.")
    
    try:
        response = input("\n   Run interactive test? (y/N): ")
        if response.lower() == 'y':
            with tempfile.TemporaryDirectory() as tmpdir:
                session_name = f"test_ducc_{os.getpid()}"
                
                cmd = [
                    "python3", script_path,
                    "--interactive",
                    "--tmux-session", session_name,
                    "--prompt", "Create a hello.py file that prints 'Hello, World!'",
                    "--cwd", tmpdir,
                ]
                
                success = run_example("Interactive Mode - Simple Write", cmd)
                
                if success:
                    print(f"\n{'='*60}")
                    print(f"Session '{session_name}' is still active.")
                    print(f"To view the session:")
                    print(f"  tmux attach -t {session_name}")
                    print(f"\nTo check if hello.py was created:")
                    print(f"  ls {tmpdir}")
                    print(f"\nTo kill the session:")
                    print(f"  tmux kill-session -t {session_name}")
                    print(f"{'='*60}")
        else:
            print("   Skipped interactive test.")
    except KeyboardInterrupt:
        print("\n   Skipped interactive test.")
    
    print("\n" + "="*60)
    print("Test examples completed!")
    print("="*60)
    print("\nFor more usage examples, see TMUX_CC_USAGE.md")


if __name__ == "__main__":
    main()
