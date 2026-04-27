#!/usr/bin/env python3
"""
Standalone script for running ducc commands with tmux integration.

This script allows you to execute ducc commands and monitor their execution 
in real-time through tmux sessions. It supports both interactive and batch modes.

Usage:
    # Interactive mode - creates a tmux session you can attach to
    python test_tmux_cc_experience.py --interactive --prompt "Your task here"
    
    # Batch mode - runs non-interactively
    python test_tmux_cc_experience.py --prompt "Your task here"
    
    # Custom tmux session name
    python test_tmux_cc_experience.py --interactive --tmux-session my_session --prompt "Task"
    
    # Specify working directory
    python test_tmux_cc_experience.py --interactive --cwd /path/to/workspace --prompt "Task"

Features:
    - Interactive mode: View ducc execution in real-time via tmux
    - Auto-confirmation: Automatically handles prompts like "Trust this folder"
    - Session monitoring: Tracks ducc execution status and detects completion
    - Workspace isolation: Creates temporary workspaces for each task
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from typing import Dict, Optional


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_WORKSPACE_ROOT = os.path.expanduser("~/.tmux_cc_experience")
TMUX_SESSION_PREFIX = "ducc_experience"
TMUX_CHECK_INTERVAL = 3  # Check interval in seconds
TMUX_IDLE_THRESHOLD = 5  # Consecutive unchanged checks to consider idle
AUTO_CONFIRM_PATTERNS = {
    "Do you want to proceed": "Enter",
    "Yes, I trust this folder": "Enter",
    "allow all edits during this session": "Down Enter",
    "Press Enter to continue": "Enter",
    "Yes, I accept": "Down Enter",
    "No, exit": "Down Enter",
}


# ============================================================================
# Utility Functions
# ============================================================================

def find_ducc_binary() -> str:
    """Find ducc binary in common locations.
    
    Priority:
        1. DUCC_BIN environment variable
        2. ducc in PATH
        3. ~/.comate/extensions/baidu-cc/dist/agent (typical installation)
        4. /usr/local/bin/ducc
    
    Returns:
        Path to ducc binary
        
    Raises:
        FileNotFoundError: If ducc cannot be found
    """
    # Check environment variable
    if "DUCC_BIN" in os.environ:
        path = os.environ["DUCC_BIN"]
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    
    # Check PATH
    try:
        result = subprocess.run(["which", "ducc"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    
    # Check common installation paths
    common_paths = [
        os.path.expanduser("~/.comate/extensions/baidu-cc/dist/agent"),
        "/usr/local/bin/ducc",
        "/opt/ducc/bin/ducc",
    ]
    
    for path in common_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    
    raise FileNotFoundError(
        "Cannot find ducc binary. Please either:\n"
        "  1. Set DUCC_BIN environment variable\n"
        "  2. Install ducc and add it to your PATH\n"
        "  3. Install baidu-cc extension in ~/.comate/extensions/"
    )


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)


# ============================================================================
# Tmux Functions
# ============================================================================

def tmux_available() -> bool:
    """Check if tmux command is available on the system."""
    try:
        subprocess.run(["tmux", "-V"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def tmux_session_exists(session_name: str) -> bool:
    """Check if a tmux session exists."""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def tmux_create_session(session_name: str, working_dir: str) -> None:
    """Create a new tmux session."""
    try:
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "-c", working_dir],
            check=True,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "tmux is not installed or not found in PATH. "
            "Please install tmux to use interactive mode."
        ) from e


def tmux_kill_session(session_name: str) -> None:
    """Kill a tmux session."""
    subprocess.run(
        ["tmux", "kill-session", "-t", session_name],
        capture_output=True,
    )


def tmux_send_keys(session_name: str, *keys: str) -> None:
    """Send keys to a tmux session."""
    subprocess.run(
        ["tmux", "send-keys", "-t", session_name] + list(keys),
        check=True,
    )


def tmux_capture_pane(session_name: str) -> str:
    """Capture the content of a tmux pane."""
    result = subprocess.run(
        ["tmux", "capture-pane", "-p", "-e", "-S", "-", "-t", session_name],
        capture_output=True,
        text=True,
    )
    return result.stdout


def check_and_auto_confirm(session_name: str, patterns: Dict[str, str]) -> bool:
    """Check for auto-confirm patterns and send keys if matched.
    
    Returns True if a pattern was matched and keys were sent.
    """
    content = tmux_capture_pane(session_name)
    clean_content = strip_ansi(content)
    
    for pattern, keys in patterns.items():
        if pattern in clean_content:
            print(f"[tmux] Detected '{pattern}' -> sending {keys}", file=sys.stderr)
            for key in keys.split():
                tmux_send_keys(session_name, key)
            return True
    return False


def wait_for_ducc_idle(
    session_name: str,
    check_interval: float = TMUX_CHECK_INTERVAL,
    idle_threshold: int = TMUX_IDLE_THRESHOLD,
    auto_confirm: bool = True,
    timeout: float = 600,
) -> str:
    """Wait for ducc to become idle (screen content stops changing).
    
    Args:
        session_name: tmux session name
        check_interval: seconds between checks
        idle_threshold: consecutive unchanged checks to consider idle
        auto_confirm: whether to auto-confirm prompts
        timeout: maximum wait time in seconds
        
    Returns:
        The final screen content
    """
    last_content = ""
    idle_count = 0
    start_time = time.time()
    task_started = False
    command_completed = False
    
    while True:
        if time.time() - start_time > timeout:
            print(f"[tmux] Timeout ({timeout}s), forcing exit", file=sys.stderr)
            break
        
        if not tmux_session_exists(session_name):
            print(f"[tmux] Session '{session_name}' has been closed", file=sys.stderr)
            break
        
        content = tmux_capture_pane(session_name)
        clean_content = strip_ansi(content)
        
        # Auto-confirm if enabled
        if auto_confirm:
            if check_and_auto_confirm(session_name, AUTO_CONFIRM_PATTERNS):
                time.sleep(1)
                idle_count = 0
                last_content = ""
                continue
        
        # Check if ducc has started processing
        if not task_started:
            task_indicators = ['Read(', 'Write(', 'Edit(', '⏺', 'Thinking', 'Reading', 'Writing']
            for indicator in task_indicators:
                if indicator in clean_content:
                    task_started = True
                    print(f"[ducc] Task started (detected: {indicator})", file=sys.stderr)
                    break
        
        # Wait for task to start
        if not task_started:
            print(f"[ducc] Waiting for task to start...", file=sys.stderr)
            last_content = content
            time.sleep(check_interval)
            continue
        
        # Check for completion indicators
        lines = clean_content.strip().split('\n')
        last_lines = '\n'.join(lines[-5:]) if len(lines) >= 5 else clean_content
        
        if not command_completed:
            # Check if ducc is still working
            still_working = any(
                ind in clean_content 
                for ind in ['Proofing', 'Thinking', 'Searching', 'Reading', 'Writing', 'Editing']
            )
            
            if still_working:
                print(f"[ducc] Still working...", file=sys.stderr)
                last_content = content
                time.sleep(check_interval)
                continue
            
            # Check for idle state (❯ prompt)
            ducc_idle = False
            if '❯' in last_lines:
                for line in lines[-3:]:
                    stripped = line.strip()
                    if stripped == '❯' or (stripped.endswith('❯') and len(stripped) < 5):
                        ducc_idle = True
                        break
            
            if ('Done.' in clean_content or ducc_idle or 
                (clean_content.count('%') >= 2 and last_lines.rstrip().endswith('%'))):
                command_completed = True
                print(f"[ducc] Command execution completed", file=sys.stderr)
        
        if command_completed:
            if content == last_content:
                idle_count += 1
                print(f"[tmux] Screen unchanged ({idle_count}/{idle_threshold})", file=sys.stderr)
                if idle_count >= idle_threshold:
                    break
            else:
                idle_count = 0
                last_content = content
        else:
            print(f"[ducc] Waiting for completion...", file=sys.stderr)
            last_content = content
        
        time.sleep(check_interval)
    
    return content if 'content' in dir() else ""


# ============================================================================
# Main Execution Functions
# ============================================================================

def run_ducc_interactive(
    prompt: str,
    ducc_bin: str,
    working_dir: str,
    session_name: str,
    auto_confirm: bool = True,
    model: Optional[str] = None,
    permission_mode: str = "bypassPermissions",
    allowed_tools: str = "Read,Edit,Write",
    effort: str = "low",
) -> None:
    """Run ducc in interactive tmux mode.
    
    Args:
        prompt: Task prompt for ducc
        ducc_bin: Path to ducc binary
        working_dir: Working directory for ducc
        session_name: Tmux session name
        auto_confirm: Auto-confirm prompts
        model: Model name (optional)
        permission_mode: Permission mode
        allowed_tools: Allowed tools
        effort: Effort level
    """
    if not tmux_available():
        raise RuntimeError("tmux is not available. Please install tmux.")
    
    print(f"\n{'='*60}")
    print(f"Running ducc in interactive mode")
    print(f"{'='*60}")
    print(f"Session: {session_name}")
    print(f"Working directory: {working_dir}")
    print(f"Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"Prompt: {prompt}")
    print(f"\nTo watch execution in real-time, run:")
    print(f"  tmux attach -t {session_name}")
    print(f"{'='*60}\n")
    
    # Kill existing session if any
    if tmux_session_exists(session_name):
        print(f"[tmux] Killing existing session '{session_name}'", file=sys.stderr)
        tmux_kill_session(session_name)
    
    # Create new tmux session
    tmux_create_session(session_name, working_dir)
    
    # Build ducc command
    cmd = f'IS_SANDBOX=1 {ducc_bin} --permission-mode {permission_mode} --allowedTools "{allowed_tools}" --effort {effort}'
    
    if model:
        cmd += f' --model "{model}"'
    
    # Start ducc in tmux
    tmux_send_keys(session_name, cmd, "Enter")
    
    # Wait for ducc to start
    print(f"[ducc] Waiting for ducc to start...", file=sys.stderr)
    time.sleep(3)
    
    # Auto-confirm trust folder prompt
    if auto_confirm:
        for _ in range(10):
            if check_and_auto_confirm(session_name, AUTO_CONFIRM_PATTERNS):
                time.sleep(1)
                break
            time.sleep(1)
    
    # Wait for ducc to be ready
    print(f"[ducc] Waiting for ducc to be ready...", file=sys.stderr)
    time.sleep(2)
    
    # Send prompt
    tmux_send_keys(session_name, prompt, "Enter")
    
    # Wait for completion
    print(f"[ducc] Waiting for ducc to process task...", file=sys.stderr)
    wait_for_ducc_idle(session_name, auto_confirm=auto_confirm)
    
    print(f"\n{'='*60}")
    print(f"[ducc] Task completed!")
    print(f"Session '{session_name}' is still active.")
    print(f"Use 'tmux attach -t {session_name}' to view results.")
    print(f"Use 'tmux kill-session -t {session_name}' to close the session.")
    print(f"{'='*60}\n")


def run_ducc_batch(
    prompt: str,
    ducc_bin: str,
    working_dir: str,
    model: Optional[str] = None,
    permission_mode: str = "bypassPermissions",
    allowed_tools: str = "Read,Edit,Write",
    effort: str = "low",
) -> str:
    """Run ducc in batch mode (non-interactive).
    
    Args:
        prompt: Task prompt for ducc
        ducc_bin: Path to ducc binary
        working_dir: Working directory for ducc
        model: Model name (optional)
        permission_mode: Permission mode
        allowed_tools: Allowed tools
        effort: Effort level
        
    Returns:
        ducc output as string
    """
    print(f"\n{'='*60}")
    print(f"Running ducc in batch mode")
    print(f"{'='*60}")
    print(f"Working directory: {working_dir}")
    print(f"Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"Prompt: {prompt}")
    print(f"{'='*60}\n")
    
    # Build command
    cmd = [
        ducc_bin,
        "-p", prompt,
        "--allowedTools", allowed_tools,
        "--permission-mode", permission_mode,
        "--effort", effort,
    ]
    
    if model:
        cmd.extend(["--model", model])
    
    # Execute ducc
    result = subprocess.run(
        cmd,
        cwd=working_dir,
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        print(f"[ducc] Error: ducc failed with code {result.returncode}", file=sys.stderr)
        print(f"[ducc] stderr: {result.stderr}", file=sys.stderr)
        raise RuntimeError(f"ducc execution failed: {result.stderr}")
    
    print(f"\n{'='*60}")
    print(f"[ducc] Task completed!")
    print(f"{'='*60}\n")
    
    return result.stdout


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run ducc commands with tmux integration for real-time monitoring.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode with tmux
  %(prog)s --interactive --prompt "Create a hello world Python script"
  
  # Batch mode (no tmux)
  %(prog)s --prompt "List all Python files"
  
  # Custom session name and working directory
  %(prog)s --interactive --tmux-session my_task --cwd /tmp/workspace --prompt "Task"
  
  # Specify model
  %(prog)s --interactive --model claude-3-5-sonnet-20241022 --prompt "Task"
        """
    )
    
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        required=True,
        help="Task prompt for ducc"
    )
    
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive tmux mode for visual observation"
    )
    
    parser.add_argument(
        "--tmux-session",
        type=str,
        default=None,
        help="Custom tmux session name (default: auto-generated)"
    )
    
    parser.add_argument(
        "--cwd",
        type=str,
        default=None,
        help="Working directory for ducc (default: temporary directory)"
    )
    
    parser.add_argument(
        "--no-auto-confirm",
        action="store_true",
        help="Disable auto-confirm prompts in interactive mode"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (e.g., claude-3-5-sonnet-20241022)"
    )
    
    parser.add_argument(
        "--ducc-bin",
        type=str,
        default=None,
        help="Path to ducc binary (default: auto-detect)"
    )
    
    parser.add_argument(
        "--permission-mode",
        type=str,
        default="bypassPermissions",
        help="Permission mode (default: bypassPermissions)"
    )
    
    parser.add_argument(
        "--allowed-tools",
        type=str,
        default="Read,Edit,Write",
        help="Comma-separated list of allowed tools (default: Read,Edit,Write)"
    )
    
    parser.add_argument(
        "--effort",
        type=str,
        default="low",
        choices=["low", "medium", "high"],
        help="Effort level (default: low)"
    )
    
    args = parser.parse_args()
    
    # Find ducc binary
    try:
        ducc_bin = args.ducc_bin or find_ducc_binary()
        print(f"[Config] Using ducc binary: {ducc_bin}")
    except FileNotFoundError as e:
        print(f"[Error] {e}", file=sys.stderr)
        sys.exit(1)
    
    # Setup working directory
    if args.cwd:
        working_dir = os.path.abspath(args.cwd)
        os.makedirs(working_dir, exist_ok=True)
    else:
        working_dir = tempfile.mkdtemp(prefix="ducc_workspace_")
        print(f"[Config] Using temporary working directory: {working_dir}")
    
    # Run ducc
    try:
        if args.interactive:
            # Generate session name
            session_name = args.tmux_session or f"{TMUX_SESSION_PREFIX}_{int(time.time())}"
            
            run_ducc_interactive(
                prompt=args.prompt,
                ducc_bin=ducc_bin,
                working_dir=working_dir,
                session_name=session_name,
                auto_confirm=not args.no_auto_confirm,
                model=args.model,
                permission_mode=args.permission_mode,
                allowed_tools=args.allowed_tools,
                effort=args.effort,
            )
        else:
            output = run_ducc_batch(
                prompt=args.prompt,
                ducc_bin=ducc_bin,
                working_dir=working_dir,
                model=args.model,
                permission_mode=args.permission_mode,
                allowed_tools=args.allowed_tools,
                effort=args.effort,
            )
            print(output)
    
    except Exception as e:
        print(f"[Error] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
