#!/usr/bin/env python3
"""
Test script to verify the tool call working directory fix.
"""

import os
import json
from pathlib import Path

from supernova.core.tool_manager import ToolManager
from supernova.tools.terminal_command_tool import TerminalCommandTool

def test_working_dir_handling():
    """Test working directory handling in tool execution."""
    # Create a test directory
    test_dir = Path("./test_dir")
    test_dir.mkdir(exist_ok=True)
    
    # Create a manager and register the terminal command tool
    manager = ToolManager()
    terminal_tool = TerminalCommandTool()
    manager.register_tool(terminal_tool)
    
    # Set up session state
    session_state = {
        "cwd": str(test_dir),
        "initial_directory": str(Path.cwd()),
        "executed_commands": [],
        "used_tools": []
    }
    
    # Different ways to specify working directory
    test_cases = [
        {
            "name": "String path relative",
            "working_dir": "test_dir",
            "command": "pwd"
        },
        {
            "name": "String path absolute",
            "working_dir": str(test_dir.resolve()),
            "command": "pwd"
        },
        {
            "name": "Path object relative",
            "working_dir": test_dir,
            "command": "pwd"
        },
        {
            "name": "Path object absolute",
            "working_dir": test_dir.resolve(),
            "command": "pwd"
        },
        {
            "name": "None (should use current directory)",
            "working_dir": None,
            "command": "pwd"
        }
    ]
    
    print("\n=== Testing Working Directory Handling ===\n")
    for case in test_cases:
        print(f"\n--- Test Case: {case['name']} ---")
        print(f"Working directory: {case['working_dir']}")
        
        # Execute the tool
        result = manager.execute_tool(
            "terminal_command",
            {"command": case["command"]},
            session_state=session_state,
            working_dir=case["working_dir"]
        )
        
        print(f"Result: {json.dumps(result, indent=2)}")
        
        # Verify the result matches the expected path
        if result.get("success"):
            stdout = result.get("stdout", "").strip()
            expected_path = str(test_dir.resolve()) if case["working_dir"] is not None else str(Path.cwd())
            if stdout == expected_path:
                print(f"✅ SUCCESS: Path matches expected {expected_path}")
            else:
                print(f"❌ FAILURE: Path {stdout} doesn't match expected {expected_path}")
        else:
            print(f"❌ FAILURE: Command failed: {result.get('error')}")
    
    print("\n=== Tests completed ===")

if __name__ == "__main__":
    test_working_dir_handling() 