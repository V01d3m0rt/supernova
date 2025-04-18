"""
SuperNova - AI-powered development assistant within the terminal.

Tool to execute terminal commands.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from functools import partial

from rich.console import Console
from rich.panel import Panel

from supernova.core.tool_base import SupernovaTool

console = Console()

class TerminalCommandTool(SupernovaTool):
    """Tool for executing terminal commands."""
    
    description = "Execute a terminal command in the current working directory."
    
    def __init__(self):
        """Initialize the terminal command tool."""
        super().__init__(
            name="terminal_command",
            description="Execute a terminal command and get its output",
            required_args={
                "command": "The terminal command to execute"
            },
            optional_args={
                "working_dir": "Directory to execute the command in",
                "explanation": "Explanation of what this command does",
                "timeout": "Timeout in seconds for the command"
            }
        )
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the schema for this tool.
        
        Returns:
            Tool schema dictionary
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The terminal command to execute"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Directory to execute the command in"
                    },
                    "explanation": {
                        "type": "string",
                        "description": "Explanation of what this command does"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds for the command"
                    }
                },
                "required": ["command"]
            }
        }
    
    def get_arguments_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for the tool's arguments."""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute"
                },
                "explanation": {
                    "type": "string",
                    "description": "Explanation of what this command does"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Directory to run the command in"
                }
            },
            "required": ["command"]
        }
    
    def get_usage_examples(self) -> List[Dict[str, Any]]:
        """Get examples of how to use the tool."""
        return [
            {
                "description": "List files in the current directory",
                "arguments": {
                    "command": "ls -la"
                }
            },
            {
                "description": "Check git status",
                "arguments": {
                    "command": "git status"
                }
            }
        ]
    
    def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None, working_dir: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Execute the terminal command.
        
        Args:
            args: Dictionary with command arguments
            context: Optional execution context
            working_dir: Optional working directory
            
        Returns:
            Dictionary with execution results
        """
        if not isinstance(args, dict):
            return {
                "success": False, 
                "error": "Arguments must be a dictionary"
            }
            
        # Get the command from args
        command = args.get("command", "")
        explanation = args.get("explanation", "")
        args_working_dir = args.get("working_dir", "")
        
        # If working_dir is provided as a function parameter, it takes precedence
        effective_working_dir = working_dir if working_dir is not None else args_working_dir
            
        return self.execute_command(command, explanation, effective_working_dir)
        
    def execute_command(self, command: str, explanation: str = None, working_dir: Union[str, Path] = None) -> Dict[str, Any]:
        """
        Execute a terminal command and return the result.
        
        Args:
            command: The command to execute
            explanation: Optional explanation of what this command does
            working_dir: Optional directory to run the command in (str or Path)
            
        Returns:
            Dictionary with command execution results
        """
        if not command:
            return {
                "success": False,
                "error": "No command provided"
            }
        
        # Determine working directory - handle both string and Path objects
        if working_dir:
            # Convert to Path if it's a string
            if isinstance(working_dir, str):
                cwd = Path(working_dir)
            else:
                cwd = working_dir
            
            # Convert to string for subprocess
            cwd = str(cwd)
        else:
            cwd = os.getcwd()
        
        # Show execution information
        if explanation:
            console.print(Panel(f"[cyan]{explanation}[/cyan]\n\n[bold]Command:[/bold] {command}", title="Running Command"))
        else:
            console.print(Panel(f"[bold]Command:[/bold] {command}", title="Running Command"))
        
        console.print(f"Working directory: {cwd}")
        
        try:
            # Execute command
            process = subprocess.Popen(
                command,
                cwd=cwd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Get output with timeout
            stdout, stderr = process.communicate(timeout=30)
            returncode = process.returncode
            
            if returncode == 0:
                console.print("[green]Command completed successfully[/green]")
                if stdout:
                    console.print(Panel(stdout, title="Output"))
                return {
                    "success": True,
                    "stdout": stdout,
                    "stderr": stderr,
                    "code": returncode
                }
            else:
                console.print(f"[red]Command failed with exit code {returncode}[/red]")
                if stderr:
                    console.print(Panel(stderr, title="Error"))
                if stdout:
                    console.print(Panel(stdout, title="Output"))
                return {
                    "success": False,
                    "error": f"Command failed with exit code {returncode}",
                    "stdout": stdout,
                    "stderr": stderr,
                    "code": returncode
                }
        except subprocess.TimeoutExpired:
            console.print("[red]Command execution timed out[/red]")
            process.kill()
            return {
                "success": False,
                "error": "Command execution timed out"
            }
        except Exception as e:
            console.print(f"[red]Error executing command: {str(e)}[/red]")
            return {
                "success": False,
                "error": f"Error executing command: {str(e)}"
            }
    
    async def execute_async(self, args: Dict[str, Any], context: Dict[str, Any] = None, working_dir: Union[str, Path] = None) -> Dict[str, Any]:
        """
        Execute the terminal command asynchronously.
        
        Args:
            args: Arguments for the command
            context: Additional context
            working_dir: Working directory to run the command in
            
        Returns:
            Command results
        """
        # Extract command from args
        if not isinstance(args, dict):
            return {
                "success": False,
                "error": "Arguments must be a dictionary"
            }
        
        command = args.get("command", "")
        explanation = args.get("explanation", "")
        
        # If working_dir is provided in function args, it takes precedence over the one in args
        # This is important as it comes from the session context
        args_working_dir = args.get("working_dir")
        effective_working_dir = working_dir if working_dir is not None else args_working_dir
        
        console.print(f"[dim]Async executing with working directory: {effective_working_dir}[/dim]")
        
        # Run the terminal command
        return self.execute_command(
            command=command,
            explanation=explanation,
            working_dir=effective_working_dir
        )
    
    def _is_potentially_dangerous(self, command: str) -> bool:
        """Check if a command contains potentially dangerous operations."""
        # List of potentially dangerous command patterns
        dangerous_patterns = [
            r"rm\s+-rf\s+/",
            r"rm\s+-rf\s+~",
            r"rm\s+-rf\s+\*",
            r":(){ :\|:& };:",
            r"dd\s+.*\s+of=/dev/",
            r">\s+/dev/",
            r">\s+/proc/",
            r">\s+/sys/",
            r"shutdown",
            r"mkfs",
            r"reboot",
            r"halt",
            r"poweroff"
        ]
        
        # Check if command matches any dangerous pattern
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        
        return False

    # Helper methods for compatibility with old code
    def get_name(self) -> str:
        """Legacy method to get the tool name."""
        return self.name
    
    def get_description(self) -> str:
        """Legacy method to get the tool description."""
        return self.description 