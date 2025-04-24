"""
SuperNova - AI-powered development assistant within the terminal.

UI management functionality for CLI.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.styles import Style

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from supernova.cli.ui_utils import (
    loading_animation, animated_print, display_welcome_banner,
    display_tool_execution, display_response, animated_status,
    create_progress_bar, display_command_result, display_thinking_animation,
    fade_in_text, display_chat_input_prompt, display_tool_confirmation,
    display_generating_animation, theme_color, set_theme, format_rich_objects
)

console = Console()

class UIManager:
    """
    Manages the user interface for the CLI application.
    
    Responsibilities:
    - Displaying messages and responses
    - Handling user input
    - Managing UI state
    - Displaying tool results
    - Managing UI animations and styling
    """
    
    def __init__(self, working_dir: Path = None, logger=None):
        """
        Initialize the UI manager.
        
        Args:
            working_dir: Current working directory
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger("supernova.ui_manager")
        self.working_dir = working_dir or Path.cwd()
        
        # Initialize prompt session
        history_file = self.working_dir / ".supernova" / "prompt_history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.prompt_session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=WordCompleter(["exit", "quit", "help", "clear", "history"]),
            style=Style.from_dict({
                "prompt": "ansicyan bold",
            })
        )
    
    def display_welcome(self):
        """Display welcome message and initial information."""
        display_welcome_banner()
        console.print(f"Working in: {self.working_dir}")
    
    def get_user_input(self) -> str:
        """
        Read input from the user with enhanced UI.
        
        Returns:
            User input string
        """
        try:
            # Get input from prompt session with custom styling
            style = Style.from_dict({
                'prompt': f'bold {theme_color("secondary")}',
                'completion': f'italic {theme_color("info")}',
                'bottom-toolbar': f'bg:{theme_color("primary")} {theme_color("info")}',
            })
            
            # Create a completer with common commands
            command_completer = WordCompleter([
                'exit', 'quit', 'help', 'clear', 'history',
                'search', 'find', 'create', 'edit', 'run',
                'install', 'update', 'delete', 'show',
                'explain', 'analyze', 'fix', 'optimize'
            ])
            
            # Use the prompt session with the new style and auto-suggestions
            user_input = self.prompt_session.prompt(
                "",
                style=style,
                completer=command_completer,
                auto_suggest=AutoSuggestFromHistory(),
                complete_in_thread=True,
                complete_while_typing=True,
                bottom_toolbar=" Press Tab for suggestions | Ctrl+C to cancel "
            )
            
            # Display processing message and show the input in a panel
            console.print(f"[{theme_color('secondary')}]Processing your input...[/{theme_color('secondary')}]")
            
            # Display user input in a panel
            self.display_response(user_input, role="user")
        
            return user_input
        except KeyboardInterrupt:
            console.print(f"[{theme_color('warning')}]Operation interrupted[/{theme_color('warning')}]")
            return "exit"
        except Exception as e:
            console.print(f"[{theme_color('error')}]Error reading input:[/{theme_color('error')}] {str(e)}")
            return "exit"
    
    def display_response(self, response, role="assistant"):
        """
        Display a response message.
        
        Args:
            response: Content to display
            role: Role of the response sender (user, assistant, system)
        """
        # Skip empty responses
        if not response or (isinstance(response, str) and not response.strip()):
            return
            
        # Format based on role
        if role == "assistant":
            # Use rich Markdown for assistant responses
            try:
                # Check if it's already a Rich renderable object
                if hasattr(response, "__rich__"):
                    console.print(response)
                else:
                    # Format as Markdown
                    md = Markdown(str(response))
                    console.print(md)
            except Exception as e:
                # Fall back to plain text if Markdown parsing fails
                console.print(f"[{theme_color('secondary')}]{response}[/{theme_color('secondary')}]")
                self.logger.error(f"Error rendering Markdown: {str(e)}")
        elif role == "user":
            # Create a panel for user messages
            panel = Panel(
                str(response),
                title="You",
                title_align="left",
                border_style=theme_color("secondary"),
                padding=(1, 2)
            )
            console.print(panel)
        elif role == "system":
            # Format system messages differently
            console.print(f"[{theme_color('info')}]{response}[/{theme_color('info')}]")
        elif role == "error":
            # Format error messages
            console.print(f"[{theme_color('error')}]Error: {response}[/{theme_color('error')}]")
        else:
            # Default formatting
            console.print(response)
    
    def display_tool_results(self, tool_results: List[Dict]):
        """
        Process tool results from handled tool calls.
        
        Args:
            tool_results: List of tool result dictionaries
        """
        if not tool_results:
            return
            
        for result in tool_results:
            tool_name = result.get("tool_name", "unknown")
            success = result.get("success", False)
            error = result.get("error", None)
            raw_result = result.get("result", None)
            
            if success:
                # Format the result for display
                if isinstance(raw_result, dict) or isinstance(raw_result, list):
                    try:
                        import json
                        formatted_result = json.dumps(raw_result, indent=2)
                    except Exception:
                        formatted_result = str(raw_result)
                else:
                    formatted_result = str(raw_result)
                
                # Display success message
                if tool_name == "terminal_command" and isinstance(raw_result, dict):
                    # Special display for terminal commands
                    stdout = raw_result.get("stdout", "").strip()
                    stderr = raw_result.get("stderr", "").strip()
                    command = raw_result.get("command", "")
                    
                    if stdout or stderr:
                        # Display command result with stdout/stderr
                        display_command_result(command, stdout, stderr)
                else:
                    # Create a panel for the result if it's not empty
                    if formatted_result and formatted_result.strip():
                        # Create a panel for the result
                        result_panel = Panel(
                            formatted_result,
                            title=f"Result from {tool_name}",
                            title_align="left",
                            border_style="green"
                        )
                        console.print(result_panel)
            else:
                # Handle error case
                error_msg = error or "Unknown error"
                if isinstance(raw_result, dict) and "stderr" in raw_result:
                    error_msg = raw_result["stderr"] or error_msg
                    
                # Format error message
                error_panel = Panel(
                    str(error_msg),
                    title=f"Error from {tool_name}",
                    title_align="left",
                    border_style="red"
                )
                console.print(error_panel)
    
    def display_thinking_animation(self, message: str = "Thinking"):
        """
        Display a thinking animation.
        
        Args:
            message: Message to display
        """
        display_thinking_animation(message)
    
    def display_tool_execution(self, tool_name: str, args: Dict[str, Any]):
        """
        Display tool execution information.
        
        Args:
            tool_name: Name of the tool being executed
            args: Arguments for the tool
        """
        display_tool_execution(tool_name, args)
    
    def display_stream(self, content: str) -> None:
        """
        Display streaming content to the console.
        
        Args:
            content: The content to display
        """
        # Simply print the content
        print(content, end="", flush=True)
    
    def display_progress(self, current: int, total: int, description: str = "Processing"):
        """
        Display a progress bar.
        
        Args:
            current: Current progress
            total: Total progress
            description: Description of the operation
        """
        progress_bar = create_progress_bar()
        with progress_bar:
            task = progress_bar.add_task(description, total=total)
            progress_bar.update(task, completed=current)
    
    def display_table(self, headers: List[str], rows: List[List[str]], title: str = None):
        """
        Display a table.
        
        Args:
            headers: List of column headers
            rows: List of row data
            title: Optional title for the table
        """
        from rich.table import Table
        
        table = Table(title=title)
        
        # Add headers
        for header in headers:
            table.add_column(header)
        
        # Add rows
        for row in rows:
            table.add_row(*row)
        
        console.print(table)
    
    def display_code(self, code: str, language: str = "python", title: str = None):
        """
        Display formatted code.
        
        Args:
            code: Code to display
            language: Programming language
            title: Optional title
        """
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        
        if title:
            panel = Panel(syntax, title=title, border_style=theme_color("primary"))
            console.print(panel)
        else:
            console.print(syntax) 