"""
SuperNova - AI-powered development assistant within the terminal.

Terminal command execution tool.
"""

import os
import shlex
import subprocess
import asyncio
from typing import Dict, Any, List, Optional
from functools import partial
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from supernova.core.tool_base import SupernovaTool

console = Console()

class TerminalCommandTool(SupernovaTool):
    """Tool for executing terminal commands safely."""
    
    name = "terminal_command"
    description = "Execute a terminal command in the current working directory."
    
    def get_arguments_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for the tool's arguments."""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The terminal command to execute"
                },
                "explanation": {
                    "type": "string",
                    "description": "Brief explanation of what the command does"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory to execute the command in (defaults to current directory)"
                }
            },
            "required": ["command"]
        }
    
    def get_usage_examples(self) -> List[Dict[str, Any]]:
        """Get examples of how to use this tool."""
        return [
            {
                "description": "List files in the current directory",
                "arguments": {
                    "command": "ls -la"
                }
            },
            {
                "description": "Check Git status",
                "arguments": {
                    "command": "git status",
                    "explanation": "Check Git status"
                }
            }
        ]
    
    def execute(self, command: str, explanation: Optional[str] = None, working_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the terminal command.
        
        Args:
            command: The command to execute
            explanation: Optional explanation of what the command does
            working_dir: Optional working directory
        
        Returns:
            Dictionary with execution results
        """
        if not command:
            return {
                "success": False,
                "error": "Missing required argument: command",
                "output": None,
                "return_code": None
            }
        
        # Use current working directory if not specified
        if working_dir is None:
            working_dir = os.getcwd()
        elif isinstance(working_dir, str):
            working_dir = Path(working_dir)
        
        # Display the command and explanation
        if explanation:
            console.print(f"\n[bold blue]Command:[/bold blue] {command}")
            console.print(f"[bold yellow]Purpose:[/bold yellow] {explanation}")
        else:
            console.print(f"\n[bold blue]Command:[/bold blue] {command}")
        
        console.print(f"[bold green]Working directory:[/bold green] {working_dir}")
        
        try:
            # Check if the command has shell-specific features that require shell=True
            has_shell_features = any(char in command for char in ['|', '>', '<', '&&', '||', ';', '*', '?', '~', '$'])
            
            if has_shell_features:
                # For complex shell commands, we need to use shell=True but warn the user
                console.print("[yellow]Warning: Using shell for complex command. This could be a security risk if the command contains untrusted input.[/yellow]")
                
                # Execute the command with shell=True
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=working_dir
                )
            else:
                # For simple commands, split the command into arguments and execute directly
                try:
                    # Use shlex.split to properly handle quoted arguments
                    command_args = shlex.split(command)
                    
                    # Execute the command without shell=True
                    process = subprocess.Popen(
                        command_args,
                        shell=False,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=working_dir
                    )
                except ValueError as e:
                    # If there's an error parsing the command, fall back to shell=True
                    console.print(f"[yellow]Warning: Error parsing command ({str(e)}). Falling back to shell execution.[/yellow]")
                    process = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=working_dir
                    )
            
            # Capture output
            stdout, stderr = process.communicate(timeout=60)
            return_code = process.returncode
            
            # Display results
            if return_code == 0:
                console.print("[bold green]Command executed successfully[/bold green]")
                if stdout:
                    console.print(Panel(stdout, title="Command Output", expand=False))
            else:
                console.print(f"[bold red]Command failed with exit code {return_code}[/bold red]")
                if stderr:
                    console.print(Panel(stderr, title="Error Output", expand=False))
                if stdout:
                    console.print(Panel(stdout, title="Command Output", expand=False))
            
            # Check for cd command to update working directory
            updated_working_dir = None
            if command.strip().startswith("cd ") and return_code == 0:
                path = command.strip()[3:].strip()
                updated_working_dir = str(Path(working_dir) / path)
            
            result = {
                "success": return_code == 0,
                "output": stdout,
                "stderr": stderr if stderr else "",
                "return_code": return_code
            }
            
            if updated_working_dir:
                result["updated_working_dir"] = updated_working_dir
                
            return result
            
        except subprocess.TimeoutExpired:
            console.print("[bold red]Command timed out after 60 seconds[/bold red]")
            return {
                "success": False,
                "error": "Command timed out after 60 seconds",
                "output": None,
                "return_code": None
            }
            
        except Exception as e:
            console.print(f"[bold red]Error executing command:[/bold red] {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "output": None,
                "return_code": None
            }
    
    # Legacy methods for backward compatibility
    def get_name(self) -> str:
        return self.name
        
    def get_description(self) -> str:
        return self.description
        
    def get_required_args(self) -> Dict[str, str]:
        return {"command": "The terminal command to execute"}
        
    def get_optional_args(self) -> Dict[str, str]:
        return {
            "explanation": "Brief explanation of what the command does",
            "working_dir": "Working directory to execute the command in (defaults to current directory)"
        }
    
    async def async_execute(self, args: Dict[str, Any], context: Dict[str, Any] = None, working_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the terminal command asynchronously.
        
        Args:
            args: Arguments for the tool
                command: The command to execute
                explanation: Optional explanation of what the command does
                working_dir: Optional working directory
            context: Context information (optional)
            working_dir: Working directory override (optional)
            
        Returns:
            Dictionary with execution results
        """
        # If working_dir is provided as an override parameter, use it
        if working_dir:
            # Create a new args dictionary with the working_dir override
            updated_args = args.copy()
            updated_args["working_dir"] = working_dir
            args = updated_args
        
        # Use a thread pool to run the synchronous execute method
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(self.execute, args["command"], args.get("explanation"), args.get("working_dir"))) 