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
from supernova.core.command_executor import CommandExecutor

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
        # Validate arguments
        validation = self.validate_args(args)
        if not validation["valid"]:
            return self._create_standard_response(
                success=False,
                error=validation.get("error", "Missing required arguments")
            )
            
        # Get the command from args
        command = args.get("command", "")
        explanation = args.get("explanation", "")
        args_working_dir = args.get("working_dir", "")
        timeout = args.get("timeout", 30)
        
        try:
            timeout = int(timeout)
        except (ValueError, TypeError):
            timeout = 30
            
        # If working_dir is provided as a function parameter, it takes precedence
        effective_working_dir = working_dir if working_dir is not None else args_working_dir
            
        # Check if the command is potentially dangerous
        if self._is_potentially_dangerous(command):
            return self._create_standard_response(
                success=False,
                error="This command contains potentially dangerous operations and has been blocked for security reasons.",
                command=command
            )
        
        # Use the CommandExecutor to execute the command
        result = CommandExecutor.execute_command(
            command=command,
            working_dir=effective_working_dir,
            explanation=explanation,
            timeout=timeout,
            require_confirmation=False,  # No confirmation needed in tool context
            show_output=True
        )
        
        return result
        
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
        # Just call the synchronous version for now
        return self.execute(args, context, working_dir)
    
    def _is_potentially_dangerous(self, command: str) -> bool:
        """Check if a command contains potentially dangerous operations."""
        return CommandExecutor.is_potentially_dangerous(command)

    # Helper methods for compatibility with old code
    def get_name(self) -> str:
        """Legacy method to get the tool name."""
        return self.name
    
    def get_description(self) -> str:
        """Legacy method to get the tool description."""
        return self.description 