"""
SuperNova - AI-powered development assistant within the terminal.

Unified command execution utility for running terminal commands.
"""

import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()


class CommandExecutor:
    """
    A utility class that provides a unified interface for command execution,
    to be used by both command_runner.py and TerminalCommandTool.
    
    This class handles:
    - Command validation and sanitization
    - Working directory management
    - Command execution with or without shell
    - Timeout handling
    - Output capturing and formatting
    - Error handling
    """
    
    @staticmethod
    def detect_shell_features(command: str) -> bool:
        """
        Detect if a command uses shell-specific features.
        
        Args:
            command: Command to check
            
        Returns:
            True if the command uses shell features, False otherwise
        """
        shell_features = ['|', '>', '<', '&&', '||', ';', '*', '?', '~', '$']
        return any(char in command for char in shell_features)
    
    @staticmethod
    def is_potentially_dangerous(command: str) -> bool:
        """
        Check if a command contains potentially dangerous operations.
        
        Args:
            command: Command to check
            
        Returns:
            True if the command is potentially dangerous, False otherwise
        """
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
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        
        return False
    
    @staticmethod
    def resolve_working_dir(working_dir: Optional[Union[str, Path]] = None) -> str:
        """
        Resolve the working directory to use for command execution.
        
        Args:
            working_dir: Working directory (string or Path) or None for current directory
            
        Returns:
            Resolved working directory as a string
        """
        if working_dir is None:
            try:
                return os.getcwd()
            except (FileNotFoundError, OSError):
                # Fallback to home directory if current directory is not accessible
                return str(Path.home())
        
        # Convert Path to string if needed
        if isinstance(working_dir, Path):
            return str(working_dir)
        
        return working_dir
    
    @classmethod
    def execute_command(
        cls,
        command: str,
        working_dir: Optional[Union[str, Path]] = None,
        explanation: Optional[str] = None,
        timeout: int = 30,
        require_confirmation: bool = False,
        env: Optional[Dict[str, str]] = None,
        show_output: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a command and return a standardized result.
        
        Args:
            command: Command to execute
            working_dir: Working directory for command execution
            explanation: Optional explanation of what the command does
            timeout: Command timeout in seconds
            require_confirmation: Whether to require user confirmation
            env: Additional environment variables
            show_output: Whether to display output in the console
            
        Returns:
            Dictionary with standardized execution results including:
                - success: Whether the command completed successfully (exit code 0)
                - stdout: Standard output from the command
                - stderr: Standard error from the command
                - return_code: Command exit code
                - execution_time: Time taken to execute in seconds
                - error: Error message if an error occurred
        """
        if not command:
            return {
                "success": False,
                "error": "No command provided",
                "return_code": -1,
                "stdout": "",
                "stderr": "",
                "execution_time": 0
            }
        
        # Resolve working directory
        cwd = cls.resolve_working_dir(working_dir)
        
        # Show execution information
        if show_output:
            if explanation:
                console.print(Panel(f"[cyan]{explanation}[/cyan]\n\n[bold]Command:[/bold] {command}", title="Running Command"))
            else:
                console.print(Panel(f"[bold]Command:[/bold] {command}", title="Running Command"))
            console.print(f"Working directory: {cwd}")
        
        # Get confirmation if required
        if require_confirmation:
            if not Confirm.ask("[yellow]Execute this command?[/yellow]"):
                return {
                    "success": False,
                    "error": "Command execution cancelled by user",
                    "return_code": -1,
                    "stdout": "",
                    "stderr": "",
                    "execution_time": 0
                }
        
        # Prepare environment
        cmd_env = os.environ.copy()
        if env:
            cmd_env.update(env)
        
        # Track execution time
        start_time = time.time()
        
        try:
            # Check if command uses shell features
            has_shell_features = cls.detect_shell_features(command)
            
            if has_shell_features:
                if show_output:
                    console.print("[yellow]Warning: Using shell for complex command.[/yellow]")
                
                # Execute with shell=True for complex commands
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    env=cmd_env,
                    timeout=timeout,
                    capture_output=True,
                    text=True
                )
            else:
                try:
                    # Split command for simple commands
                    command_args = shlex.split(command)
                    
                    # Execute without shell
                    result = subprocess.run(
                        command_args,
                        shell=False,
                        cwd=cwd,
                        env=cmd_env,
                        timeout=timeout,
                        capture_output=True,
                        text=True
                    )
                except ValueError as e:
                    if show_output:
                        console.print(f"[yellow]Warning: Error parsing command ({str(e)}). Falling back to shell execution.[/yellow]")
                    
                    # Fall back to shell=True if parsing fails
                    result = subprocess.run(
                        command,
                        shell=True,
                        cwd=cwd,
                        env=cmd_env,
                        timeout=timeout,
                        capture_output=True,
                        text=True
                    )
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Extract output
            stdout = result.stdout
            stderr = result.stderr
            return_code = result.returncode
            success = return_code == 0
            
            # Display results if requested
            if show_output:
                console.print(f"[blue]Execution time:[/blue] {execution_time:.2f} seconds")
                console.print(f"[blue]Return code:[/blue] {return_code}")
                
                if stdout:
                    console.print(Panel(stdout, title="Output"))
                
                if stderr:
                    console.print(Panel(stderr, title="Error"))
                
                if success:
                    console.print("[green]Command completed successfully[/green]")
                else:
                    console.print(f"[red]Command failed with exit code {return_code}[/red]")
            
            # Create standardized result
            result_dict = {
                "success": success,
                "stdout": stdout,
                "stderr": stderr,
                "return_code": return_code,
                "execution_time": execution_time
            }
            
            # Add error message for failed commands
            if not success:
                result_dict["error"] = f"Command failed with exit code {return_code}"
            
            return result_dict
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            
            if show_output:
                console.print(f"[red]Command execution timed out after {timeout} seconds[/red]")
            
            return {
                "success": False,
                "error": f"Command execution timed out after {timeout} seconds",
                "return_code": 124,  # Standard timeout exit code
                "stdout": "",
                "stderr": "",
                "execution_time": execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            if show_output:
                console.print(f"[red]Error executing command: {str(e)}[/red]")
            
            return {
                "success": False,
                "error": f"Error executing command: {str(e)}",
                "return_code": 1,
                "stdout": "",
                "stderr": str(e),
                "execution_time": execution_time
            } 