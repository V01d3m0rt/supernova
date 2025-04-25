"""
Chat UI manager for the SuperNova chat session.

This module contains classes for managing the chat UI.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union, Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel


class ChatUI:
    """
    Chat UI manager for the SuperNova chat session.
    
    Handles displaying messages, responses, and tool results to the user.
    """
    
    def __init__(self, config=None):
        """
        Initialize the chat UI manager.
        
        Args:
            config: Configuration object
        """
        self.logger = logging.getLogger("supernova.chat.ui")
        self.config = config
        self.console = Console()
        
        # Create a completer with common commands
        self.command_completer = WordCompleter([
            'exit', 'quit', 'help', 'clear', 'history',
            'search', 'find', 'create', 'edit', 'run',
            'install', 'update', 'delete', 'show',
            'explain', 'analyze', 'fix', 'optimize'
        ])
    
    def setup_prompt_session(self, history_file_path: str) -> PromptSession:
        """
        Set up a prompt session with history.
        
        Args:
            history_file_path: Path to the history file
            
        Returns:
            Configured prompt session
        """
        # Create a prompt session with history
        prompt_session = PromptSession(
            history=FileHistory(history_file_path),
            auto_suggest=AutoSuggestFromHistory(),
            completer=self.command_completer,
            style=Style.from_dict({
                'prompt': f'bold {self.theme_color("secondary")}',
                'completion': f'italic {self.theme_color("info")}',
                'bottom-toolbar': f'bg:{self.theme_color("primary")} {self.theme_color("info")}',
            })
        )
        
        return prompt_session
    
    def get_user_input(self, prompt_session: PromptSession) -> str:
        """
        Get input from the user.
        
        Args:
            prompt_session: Prompt session to use
            
        Returns:
            User input string
        """
        try:
            # Use the prompt session with auto-suggestions
            user_input = prompt_session.prompt(
                "",
                complete_in_thread=True,
                complete_while_typing=True,
                bottom_toolbar=" Press Tab for suggestions | Ctrl+C to cancel "
            )
            
            # Display processing message and show the input in a panel
            self.console.print(f"[{self.theme_color('secondary')}]Processing your input...[/{self.theme_color('secondary')}]")
            # Display user input in a panel
            self.display_response(user_input, role="user")
        
            return user_input
        except KeyboardInterrupt:
            self.console.print(f"[{self.theme_color('warning')}]Operation interrupted[/{self.theme_color('warning')}]")
            return "exit"
        except Exception as e:
            self.console.print(f"[{self.theme_color('error')}]Error reading input:[/{self.theme_color('error')}] {str(e)}")
            return "exit"
    
    def display_response(self, response: str, role: str = "assistant") -> None:
        """
        Display a response with enhanced UI.
        
        Args:
            response: The response content
            role: The role of the responder (assistant or user)
        """
        # Determine styling based on role
        if role == "assistant":
            title = "🤖 Assistant"
            border_style = self.theme_color("primary")
        elif role == "user":
            title = "👤 You"
            border_style = self.theme_color("secondary")
        else:
            title = role.capitalize()
            border_style = self.theme_color("info")
        
        # Format response for display
        if not isinstance(response, str):
            response = str(response)
            
        # Create a panel for the response
        panel = Panel(
            response,
            title=title,
            title_align="left",
            border_style=border_style,
            padding=(1, 2)
        )
        
        # Display the panel
        self.console.print(panel)
    
    def display_tool_execution(self, tool_name: str, args: Dict[str, Any], success: bool, result: Any) -> None:
        """
        Display tool execution results.
        
        Args:
            tool_name: Name of the tool
            args: Tool arguments
            success: Whether the tool succeeded
            result: Tool result
        """
        # Format the result for display
        if isinstance(result, dict) or isinstance(result, list):
            try:
                formatted_result = json.dumps(result, indent=2)
            except Exception:
                formatted_result = str(result)
        else:
            formatted_result = str(result)
            
        # Create a panel for the result with appropriate styling
        if success:
            result_panel = Panel(
                formatted_result,
                title=f"Result from {tool_name}",
                title_align="left",
                border_style="green"
            )
        else:
            result_panel = Panel(
                f"[red]Tool {tool_name} failed: {result}[/red]",
                title=f"Result from {tool_name}",
                title_align="left",
                border_style="red"
            )
            
        # Display the panel
        self.console.print(result_panel)
    
    def display_progress_message(self, message: str, color: str = "primary") -> None:
        """
        Display a progress message.
        
        Args:
            message: Message to display
            color: Color to use for the message
        """
        self.console.print(f"[{self.theme_color(color)}]{message}[/{self.theme_color(color)}]")
    
    def display_working_directory(self, cwd: str, initial_directory: str) -> None:
        """
        Display the working directory information.
        
        Args:
            cwd: Current working directory
            initial_directory: Initial directory
        """
        self.console.print(f"Working in: {cwd}")
        self.console.print(f"Initial directory: {initial_directory} (operations will be restricted to this directory)")
    
    def display_stream(self, content: str) -> None:
        """
        Display streaming content to the console.
        
        Args:
            content: Content to display
        """
        print(content, end="", flush=True)
    
    def theme_color(self, color_name: str) -> str:
        """
        Get a color from the theme.
        
        Args:
            color_name: The name of the color to get
            
        Returns:
            The color string for rich
        """
        # Define default colors
        theme_colors = {
            "primary": "cyan",
            "secondary": "blue",
            "success": "green",
            "warning": "yellow",
            "error": "red",
            "info": "white",
            "muted": "grey70"
        }
        
        # Return the requested color or default to white
        return theme_colors.get(color_name, "white")
    
    def animated_print(self, text: str, delay: float = 0.03) -> None:
        """
        Print text with an animation.
        
        Args:
            text: Text to print
            delay: Delay between characters
        """
        import time
        
        for char in text:
            print(char, end="", flush=True)
            time.sleep(delay)
        print()
    
    def display_loading(self, message: str) -> None:
        """
        Display a loading message.
        
        Args:
            message: Message to display
        """
        self.console.print(f"[{self.theme_color('info')}]{message}...[/{self.theme_color('info')}]") 