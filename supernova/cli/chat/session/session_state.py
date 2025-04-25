"""
Session state management for chat sessions.

This module contains classes for managing the chat session state.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from supernova.cli.chat.domain.models import SessionState


class SessionStateManager:
    """
    Manages the state of a chat session.
    
    Handles tracking current directory, command history, and other session-specific information.
    """
    
    def __init__(self, initial_directory: Optional[Union[str, Path]] = None):
        """
        Initialize the session state manager.
        
        Args:
            initial_directory: Initial working directory for the session
        """
        self.logger = logging.getLogger("supernova.chat.session_state")
        
        # Set up initial directory (current directory if not specified)
        self.initial_directory = Path(initial_directory or Path.cwd())
        self.current_directory = self.initial_directory
        
        # Initialize session state
        self._state = SessionState(
            cwd=str(self.current_directory),
            initial_directory=str(self.initial_directory),
            path_history=[str(self.current_directory)],
        )
    
    @property
    def state_dict(self) -> Dict[str, Any]:
        """
        Get the session state as a dictionary.
        
        Returns:
            Dictionary representation of the session state
        """
        return self._state.to_dict()
    
    def update_current_directory(self, new_dir: Union[str, Path]) -> Dict[str, Any]:
        """
        Update the current working directory.
        
        Args:
            new_dir: New directory path
        
        Returns:
            Dict with success status and information
        """
        try:
            # Convert to Path object
            new_path = Path(new_dir)
            
            # Resolve to absolute path
            new_path = new_path.resolve()
            
            # Check if the new directory is within the initial directory
            if not str(new_path).startswith(str(self.initial_directory)):
                return {
                    "success": False,
                    "error": f"Cannot navigate outside of the initial directory: {self.initial_directory}",
                    "current_dir": str(self.current_directory)
                }
            
            # Check if the directory exists
            if not new_path.exists() or not new_path.is_dir():
                return {
                    "success": False,
                    "error": f"Directory does not exist: {new_path}",
                    "current_dir": str(self.current_directory)
                }
            
            # Update the working directory
            self.current_directory = new_path
            self._state.cwd = str(new_path)
            
            # Add to path history
            self._state.path_history.append(str(new_path))
            
            return {
                "success": True,
                "current_dir": str(new_path),
                "message": f"Changed directory to {new_path}"
            }
        except Exception as e:
            self.logger.error(f"Error changing directory: {str(e)}")
            return {
                "success": False,
                "error": f"Error changing directory: {str(e)}",
                "current_dir": str(self.current_directory)
            }
    
    def add_executed_command(self, command: str) -> None:
        """
        Add a command to the executed commands history.
        
        Args:
            command: The command that was executed
        """
        self._state.executed_commands.append(command)
    
    def add_used_tool(self, tool_info: Dict[str, Any]) -> None:
        """
        Add a tool to the used tools history.
        
        Args:
            tool_info: Information about the tool that was used
        """
        self._state.used_tools.append(tool_info)
    
    def add_created_file(self, file_path: str) -> None:
        """
        Add a file to the created files history.
        
        Args:
            file_path: Path of the file that was created
        """
        self._state.created_files.append(file_path)
    
    def set_action_result(self, result: Any) -> None:
        """
        Set the result of the last action.
        
        Args:
            result: Result of the last action
        """
        self._state.LAST_ACTION_RESULT = result
    
    def get_context_message(self) -> str:
        """
        Get a formatted context message describing the current session state.
        
        Returns:
            Formatted context message string
        """
        context_parts = [
            f"Current working directory: {self._state.cwd}",
            f"Initial directory: {self._state.initial_directory}",
            "Path history:"
        ]
        
        # Add path history if available
        if self._state.path_history:
            for path in self._state.path_history[-5:]:  # Show last 5 paths
                context_parts.append(f"- {path}")
        
        # Add executed commands if available
        if self._state.executed_commands:
            context_parts.append("\nRecently executed commands:")
            for cmd in self._state.executed_commands[-5:]:  # Show last 5 commands
                context_parts.append(f"- {cmd}")
        
        # Add used tools if available
        if self._state.used_tools:
            context_parts.append("\nRecently used tools:")
            for tool in self._state.used_tools[-5:]:  # Show last 5 tools
                context_parts.append(f"- {tool}")
        
        # Add created files if available
        if self._state.created_files:
            context_parts.append("\nRecently created files:")
            for file in self._state.created_files[-5:]:  # Show last 5 files
                context_parts.append(f"- {file}")
        
        # Add last action result if available
        if hasattr(self._state, "LAST_ACTION_RESULT"):
            context_parts.append("\nLast action result:")
            context_parts.append(str(getattr(self._state, "LAST_ACTION_RESULT", "")))
        
        return "\n".join(context_parts)
        
    def set_loaded_previous_chat(self, loaded: bool, message_count: Optional[int] = None) -> None:
        """
        Set whether a previous chat was loaded.
        
        Args:
            loaded: Whether a previous chat was loaded
            message_count: Number of messages loaded (if applicable)
        """
        self._state.loaded_previous_chat = loaded
        if message_count is not None:
            self._state.previous_message_count = message_count 