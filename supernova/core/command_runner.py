"""
SuperNova - AI-powered development assistant within the terminal.

Secure command runner for executing terminal commands.
"""

import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

from rich.console import Console

from supernova.core.command_executor import CommandExecutor

console = Console()


def run_command(
    command: str,
    cwd: Optional[Union[str, Path]] = None,
    timeout: Optional[int] = None,
    require_confirmation: bool = True,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Run a shell command securely with user confirmation.
    
    Args:
        command: The command to execute
        cwd: Working directory for the command (default: current directory)
        timeout: Maximum execution time in seconds (default: 30)
        require_confirmation: Whether to require user confirmation (default: True)
        env: Additional environment variables
        
    Returns:
        Dictionary with standardized execution results
    """
    # Use the unified CommandExecutor
    return CommandExecutor.execute_command(
        command=command,
        working_dir=cwd,
        timeout=timeout or 30,
        require_confirmation=require_confirmation,
        env=env,
        show_output=True
    )


def sanitize_command(command: str) -> str:
    """
    Basic command sanitization.
    
    Args:
        command: The command to sanitize
        
    Returns:
        Sanitized command
    """
    # This is a very basic sanitization - in a real application,
    # you'd want more comprehensive security checks
    
    # Remove dangerous shell operators
    dangerous_operators = [
        "&&", "||", ";", "|", ">", "<", "$(", "`", "$(",
    ]
    
    sanitized = command
    for op in dangerous_operators:
        sanitized = sanitized.replace(op, "")
    
    return sanitized


def extract_commands_from_text(text: str) -> List[str]:
    """
    Extract shell commands from the text.
    
    This method is deprecated as we now use LiteLLM's tool calling for command handling.
    It's kept for backward compatibility but returns an empty list.
    
    Args:
        text: Text to extract commands from
        
    Returns:
        Empty list (previously returned list of commands)
    """
    # We're now using LiteLLM's tool calling for command handling
    # This function is deprecated and kept for backward compatibility
    return [] 