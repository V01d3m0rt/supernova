#!/usr/bin/env python3
"""
SuperNova - AI-powered development assistant within the terminal.

Main CLI entry point using Click.
"""

import os
import asyncio
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from supernova.cli import chat_session
from supernova.cli.tools_command import tools_group
from supernova.config import loader

console = Console()

# TODO: VS Code Integration - Add detection of VS Code environment:
# 1. Check environment variables to detect if running within VS Code
# 2. Implement VS Code Extension activation events and commands
# 3. Create a VSCode UI adapter for console output


@click.group()
@click.version_option()
def cli() -> None:
    """SuperNova: AI-powered development assistant within the terminal."""
    pass

# Add tools command group
cli.add_command(tools_group)


@cli.command()
@click.option(
    "--directory",
    "-d",
    default=".",
    help="Directory to initialize SuperNova in (default: current directory)",
)
def init(directory: str) -> None:
    """Initialize SuperNova in the specified directory."""
    try:
        init_dir = Path(directory).absolute()
        if not init_dir.exists():
            console.print(f"[red]Error:[/red] Directory {init_dir} does not exist")
            return
        
        # Create .supernova directory
        supernova_dir = init_dir / ".supernova"
        supernova_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy default config to local directory
        default_config = loader.DEFAULT_CONFIG_PATH
        local_config = supernova_dir / "config.yaml"
        
        if local_config.exists():
            overwrite = console.input(f"[yellow]Config file already exists at {local_config}. Overwrite? (y/n):[/yellow] ")
            if overwrite.lower() != 'y':
                console.print("[yellow]Initialization cancelled.[/yellow]")
                return
        
        # Read the default config and write to local config
        with open(default_config, 'r') as src:
            default_content = src.read()
        
        with open(local_config, 'w') as dest:
            dest.write(default_content)
        
        console.print(f"[green]Initialized SuperNova in:[/green] {init_dir}")
        console.print(f"[green]Created local configuration at:[/green] {local_config}")
        console.print("[blue]You can now run 'supernova chat' to start a chat session.[/blue]")
        
    except Exception as e:
        console.print(f"[red]Error during initialization:[/red] {str(e)}")
        if hasattr(e, '__traceback__'):
            import traceback
            console.print("[red]Traceback:[/red]")
            traceback.print_tb(e.__traceback__)


@cli.command()
@click.option(
    "--list", "-l", is_flag=True, help="List all configuration settings"
)
@click.option(
    "--get", "-g", help="Get a specific configuration value (dot notation, e.g., llm_providers.openai.model)"
)
@click.option(
    "--set", "-s", help="Set a specific configuration key (dot notation, e.g., llm_providers.openai.model)"
)
@click.option(
    "--value", "-v", help="Value to set for the specified key"
)
def config(list: bool, get: Optional[str], set: Optional[str], value: Optional[str]) -> None:
    """View or modify configuration settings."""
    try:
        config_obj = loader.load_config()
        
        if list:
            # Display all configuration
            console.print("[bold]SuperNova Configuration:[/bold]")
            console.print(config_obj.model_dump_json(indent=2))
        elif get:
            # Get a specific configuration value using dot notation
            try:
                value, value_type = loader.get_config_value(config_obj, get)
                console.print(f"[bold]Value for {get}:[/bold] [green]{value}[/green] (Type: {value_type})")
            except KeyError as e:
                console.print(f"[red]Error:[/red] {str(e)}")
        elif set and value:
            # Set a specific configuration value using dot notation
            try:
                # Get config as dictionary for modification
                config_dict = config_obj.model_dump()
                
                # Update the value
                updated_config = loader.set_config_value(config_dict, set, value)
                
                # Save the updated config
                config_path = loader.save_config(updated_config)
                
                console.print(f"[green]Successfully set {set} to {value}[/green]")
                console.print(f"Configuration saved to: {config_path}")
            except (KeyError, ValueError) as e:
                console.print(f"[red]Error:[/red] {str(e)}")
        else:
            # No option provided, show help
            ctx = click.get_current_context()
            click.echo(ctx.get_help())
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


@cli.command()
@click.option(
    "--directory",
    "-d",
    default=".",
    help="Directory to run the chat session in (default: current directory)",
)
def chat(directory: str) -> None:
    """Launch the interactive devchat session."""
    try:
        # This would be implemented in chat_session.py
        chat_dir = Path(directory).absolute()
        if not chat_dir.exists():
            console.print(f"[red]Error:[/red] Directory {chat_dir} does not exist")
            return
            
        console.print(f"Starting chat session in: {chat_dir}")
        # Use the synchronous wrapper function
        chat_session.start_chat_sync(chat_dir)
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


if __name__ == "__main__":
    cli() 