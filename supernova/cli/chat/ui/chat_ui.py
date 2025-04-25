"""
UI handling for chat sessions.
"""

import time
import re
from typing import Any, Dict, List, Optional, Union

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML

from supernova.cli.ui_utils import (
    theme_color, animated_print, display_generating_animation,
    display_chat_input_prompt
)

console = Console()

class ChatUI:
    """
    Handles UI interactions for chat sessions.
    """
    def __init__(self, prompt_session: PromptSession):
        """
        Initialize the chat UI.
        
        Args:
            prompt_session: Prompt session
        """
        self.prompt_session = prompt_session
        
    def get_user_input(self) -> str:
        """
        Get input from the user with enhanced UI.
        
        Returns:
            User input
        """
        # Display the prompt
        prompt_text = "You:"#display_chat_input_prompt()
        
        # Get input from the user
        user_input = self.prompt_session.prompt(HTML(prompt_text))
        
        return user_input
        
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
            border_style = theme_color("primary")
        elif role == "user":
            title = "👤 You"
            border_style = theme_color("secondary")
        else:
            title = role.capitalize()
            border_style = theme_color("info")
        
        # Process code blocks in the response
        parts = self._split_code_blocks(response)
        
        # Create a panel for the response
        panels = []
        for part in parts:
            if isinstance(part, tuple) and len(part) == 2:
                # This is a code block
                language, code = part
                syntax = Syntax(code, language, theme="monokai", line_numbers=True)
                panels.append(Panel(syntax, border_style=border_style, expand=False))
            else:
                # This is regular text
                markdown = Markdown(part)
                panels.append(Panel(markdown, title=title, border_style=border_style, expand=False))
        
        # Print each panel
        for panel in panels:
            console.print(panel)
            
    def display_thinking_animation(self) -> None:
        """
        Display a thinking animation.
        """
        with display_generating_animation():
            time.sleep(0.5)  # Brief pause for effect
            
    def display_welcome_message(self, cwd: str, initial_directory: str) -> None:
        """
        Display a welcome message.
        
        Args:
            cwd: Current working directory
            initial_directory: Initial directory
        """
        console.print(f"Working in: {cwd}")
        console.print(f"Initial directory: {initial_directory} (operations will be restricted to this directory)")
        
    def display_project_analysis_result(self, project_summary: str) -> None:
        """
        Display the result of project analysis.
        
        Args:
            project_summary: Project summary
        """
        animated_print(
            f"[{theme_color('success')}]✅ Project analyzed successfully: {project_summary}[/{theme_color('success')}]", 
            delay=0.01
        )
        
    def display_project_analysis_error(self, error_msg: str) -> None:
        """
        Display an error that occurred during project analysis.
        
        Args:
            error_msg: Error message
        """
        animated_print(
            f"[{theme_color('warning')}]⚠️ {error_msg}[/{theme_color('warning')}]", 
            delay=0.01
        )
        
    def display_chat_loaded(self, message_count: int) -> None:
        """
        Display a message indicating that a chat was loaded.
        
        Args:
            message_count: Number of messages loaded
        """
        animated_print(
            f"[{theme_color('success')}]📚 Loaded previous chat with {message_count} messages[/{theme_color('success')}]", 
            delay=0.01
        )
        
    def display_new_chat_created(self) -> None:
        """
        Display a message indicating that a new chat was created.
        """
        animated_print(
            f"[{theme_color('success')}]🆕 Created new chat session[/{theme_color('success')}]", 
            delay=0.01
        )
        
    def display_error(self, error_msg: str) -> None:
        """
        Display an error message.
        
        Args:
            error_msg: Error message
        """
        console.print(f"[{theme_color('error')}]Error: {error_msg}[/{theme_color('error')}]")
        
    def display_exiting(self) -> None:
        """
        Display a message indicating that the application is exiting.
        """
        console.print(f"[{theme_color('secondary')}]Exiting SuperNova...[/{theme_color('secondary')}]")
        
    def _split_code_blocks(self, text: str) -> List[Union[str, tuple]]:
        """
        Split text into regular text and code blocks.
        
        Args:
            text: Text to split
            
        Returns:
            List of text parts and code block tuples
        """
        # Regular expression to match code blocks
        pattern = r"```(\w*)\n(.*?)```"
        
        # Find all code blocks
        matches = list(re.finditer(pattern, text, re.DOTALL))
        
        if not matches:
            return [text]
            
        # Split the text
        parts = []
        last_end = 0
        
        for match in matches:
            # Add text before the code block
            if match.start() > last_end:
                parts.append(text[last_end:match.start()])
                
            # Add the code block as a tuple (language, code)
            language = match.group(1) or "text"
            code = match.group(2)
            parts.append((language, code))
            
            last_end = match.end()
            
        # Add any remaining text
        if last_end < len(text):
            parts.append(text[last_end:])
            
        return parts