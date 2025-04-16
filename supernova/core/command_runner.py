"""
SuperNova - AI-powered development assistant within the terminal.

Secure command runner for executing terminal commands.
"""

import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from rich.console import Console
from rich.prompt import Confirm

console = Console()


def run_command(
    command: str,
    cwd: Optional[Union[str, Path]] = None,
    timeout: Optional[int] = None,
    require_confirmation: bool = True,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    """
    Run a shell command securely with user confirmation.
    
    Args:
        command: The command to execute
        cwd: Working directory for the command (default: current directory)
        timeout: Maximum execution time in seconds (default: 30)
        require_confirmation: Whether to require user confirmation (default: True)
        env: Additional environment variables
        
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    # Default timeout
    if timeout is None:
        timeout = 30
    
    # Default working directory
    if cwd is None:
        try:
            cwd = os.getcwd()
        except (FileNotFoundError, OSError):
            # Fallback to the home directory if current directory is not accessible
            cwd = str(Path.home())
    else:
        cwd = str(cwd)
    
    # Show command and get confirmation
    console.print(f"[bold blue]Command:[/bold blue] {command}")
    console.print(f"[blue]Working directory:[/blue] {cwd}")
    
    if require_confirmation:
        if not Confirm.ask("[yellow]Execute this command?[/yellow]"):
            console.print("[red]Command execution cancelled[/red]")
            return (-1, "", "Command execution cancelled by user")
    
    try:
        # Prepare environment
        cmd_env = os.environ.copy()
        if env:
            cmd_env.update(env)
        
        # Start the command
        console.print("[bold green]Executing command...[/bold green]")
        start_time = time.time()
        
        # Check if the command has shell-specific features that require shell=True
        has_shell_features = any(char in command for char in ['|', '>', '<', '&&', '||', ';', '*', '?', '~', '$'])
        
        if has_shell_features:
            # For complex shell commands, we need to use shell=True but warn the user
            console.print("[yellow]Warning: Using shell for complex command. This could be a security risk if the command contains untrusted input.[/yellow]")
            
            # Run the command with shell=True for complex commands
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                env=cmd_env,
                timeout=timeout,
                capture_output=True,
                text=True,
            )
        else:
            # For simple commands, split the command into arguments and execute directly
            try:
                # Use shlex.split to properly handle quoted arguments
                command_args = shlex.split(command)
                
                # Run the command without shell
                result = subprocess.run(
                    command_args,
                    shell=False,
                    cwd=cwd,
                    env=cmd_env,
                    timeout=timeout,
                    capture_output=True,
                    text=True,
                )
            except ValueError as e:
                # If there's an error parsing the command, fall back to shell=True
                console.print(f"[yellow]Warning: Error parsing command ({str(e)}). Falling back to shell execution.[/yellow]")
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    env=cmd_env,
                    timeout=timeout,
                    capture_output=True,
                    text=True,
                )
        
        # Get execution time
        execution_time = time.time() - start_time
        
        # Get output
        stdout = result.stdout
        stderr = result.stderr
        return_code = result.returncode
        
        # Display results
        console.print(f"[blue]Execution time:[/blue] {execution_time:.2f} seconds")
        console.print(f"[blue]Return code:[/blue] {return_code}")
        
        if stdout:
            console.print("[bold]Standard output:[/bold]")
            console.print(stdout)
        
        if stderr:
            console.print("[bold red]Standard error:[/bold red]")
            console.print(stderr)
        
        if return_code == 0:
            console.print("[bold green]Command executed successfully[/bold green]")
        else:
            console.print(f"[bold red]Command failed with return code {return_code}[/bold red]")
        
        return (return_code, stdout, stderr)
    
    except subprocess.TimeoutExpired:
        console.print(f"[bold red]Command timed out after {timeout} seconds[/bold red]")
        return (124, "", f"Command timed out after {timeout} seconds")
    
    except Exception as e:
        console.print(f"[bold red]Error executing command:[/bold red] {str(e)}")
        return (1, "", f"Error executing command: {str(e)}")


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