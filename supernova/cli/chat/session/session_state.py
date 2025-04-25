"""
Session state for chat sessions.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set

class SessionState:
    """
    Manages the state of a chat session.
    """
    def __init__(self, initial_directory: Path):
        """
        Initialize the session state.
        
        Args:
            initial_directory: Initial working directory
        """
        self.initial_directory = initial_directory
        self.cwd = initial_directory
        self.state = {
            "executed_commands": [],
            "used_tools": [],
            "created_files": [],
            "cwd": str(self.cwd),
            "initial_directory": str(self.initial_directory),
            "path_history": [str(self.cwd)],
            "loaded_previous_chat": False
        }
        
    def update_cwd(self, new_cwd: Path) -> None:
        """
        Update the current working directory.
        
        Args:
            new_cwd: New working directory
        """
        self.cwd = new_cwd
        self.state["cwd"] = str(new_cwd)
        
        # Add to path history if not already there
        if str(new_cwd) not in self.state["path_history"]:
            self.state["path_history"].append(str(new_cwd))
            
    def add_executed_command(self, command: Dict[str, Any]) -> None:
        """
        Add an executed command to the state.
        
        Args:
            command: Command details
        """
        self.state["executed_commands"].append(command)
        
    def add_used_tool(self, tool: Dict[str, Any]) -> None:
        """
        Add a used tool to the state.
        
        Args:
            tool: Tool details
        """
        self.state["used_tools"].append(tool)
        
    def add_created_file(self, file_path: str) -> None:
        """
        Add a created file to the state.
        
        Args:
            file_path: Path to the created file
        """
        if file_path not in self.state["created_files"]:
            self.state["created_files"].append(file_path)
            
    def set_project_summary(self, summary: str) -> None:
        """
        Set the project summary.
        
        Args:
            summary: Project summary
        """
        self.state["project_summary"] = summary
        
    def set_project_error(self, error: str) -> None:
        """
        Set the project error.
        
        Args:
            error: Project error
        """
        self.state["project_error"] = error
        
    def set_loaded_previous_chat(self, loaded: bool, message_count: Optional[int] = None) -> None:
        """
        Set whether a previous chat was loaded.
        
        Args:
            loaded: Whether a previous chat was loaded
            message_count: Number of messages loaded
        """
        self.state["loaded_previous_chat"] = loaded
        
        if message_count is not None:
            self.state["previous_message_count"] = message_count
            
    def get_state(self) -> Dict[str, Any]:
        """
        Get the current state.
        
        Returns:
            Current state
        """
        return self.state
        
    def get_cwd(self) -> Path:
        """
        Get the current working directory.
        
        Returns:
            Current working directory
        """
        return self.cwd
        
    def get_initial_directory(self) -> Path:
        """
        Get the initial directory.
        
        Returns:
            Initial directory
        """
        return self.initial_directory