"""
SuperNova - AI-powered development assistant within the terminal.

Tools CLI - Command-line interface for interacting with tools.
"""

import json
import os
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from supernova.core.tool_manager import ToolManager

console = Console()


@click.group(name="tools")
def tools_group():
    """Manage and execute SuperNova tools."""
    pass


@tools_group.command("list")
def list_tools():
    """List all available tools."""
    manager = ToolManager()
    loaded_tools = manager.discover_tools()
    
    if not loaded_tools:
        console.print("[yellow]No tools found.[/yellow]")
        return
    
    # Create a table for the tools
    table = Table(title=f"SuperNova Tools ({len(loaded_tools)} found)")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Required Arguments", style="yellow")
    
    tool_info = manager.get_tool_info()
    for info in tool_info:
        required_args = ", ".join([f"{k}: {v}" for k, v in info["required_args"].items()])
        table.add_row(info["name"], info["description"], required_args or "[italic]None[/italic]")
    
    console.print(table)


@tools_group.command("info")
@click.argument("tool_name")
def tool_info(tool_name: str):
    """Show detailed information about a specific tool."""
    manager = ToolManager()
    manager.discover_tools()
    
    tool = manager.get_tool(tool_name)
    if not tool:
        console.print(f"[red]Tool '{tool_name}' not found.[/red]")
        return
    
    # Create a panel with tool information
    usage_examples = "\n".join([f"- `{example}`" for example in tool.get_usage_examples()])
    required_args = "\n".join([f"- `{k}`: {v}" for k, v in tool.get_required_args().items()])
    
    md_content = f"""
# {tool_name}

{tool.get_description()}

## Usage Examples
{usage_examples}

## Required Arguments
{required_args or "None"}
"""
    
    console.print(Panel(Markdown(md_content), title=f"Tool: {tool_name}", border_style="cyan"))


@tools_group.command("run")
@click.argument("tool_name")
@click.argument("args", nargs=-1)
@click.option("--working-dir", "-d", type=click.Path(exists=True, file_okay=False), 
              help="Working directory for the tool")
@click.option("--json-output", "-j", is_flag=True, help="Output results as JSON")
def run_tool(tool_name: str, args, working_dir: Optional[str] = None, json_output: bool = False):
    """Run a tool with the specified arguments."""
    # Parse args into a dictionary
    args_dict = {}
    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            args_dict[key] = value
        else:
            # Handle flag-style arguments (presence implies true)
            args_dict[arg] = "true"
    
    manager = ToolManager()
    manager.discover_tools()
    
    # Set up the context (would be more detailed in a real system)
    context = {
        "cwd": os.getcwd(),
        "env": dict(os.environ),
    }
    
    # Execute the tool
    working_dir_path = Path(working_dir) if working_dir else Path.cwd()
    result = manager.execute_tool(tool_name, args_dict, context, working_dir_path)
    
    # Output the result
    if json_output:
        console.print(json.dumps(result, indent=2))
    else:
        if result.get("success", False):
            console.print(Panel(str(result), title=f"[green]Tool Executed Successfully: {tool_name}[/green]", 
                                border_style="green"))
        else:
            console.print(Panel(str(result), title=f"[red]Tool Execution Failed: {tool_name}[/red]", 
                                border_style="red"))


if __name__ == "__main__":
    tools_group() 