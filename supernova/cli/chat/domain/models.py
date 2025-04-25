"""
Domain models for the chat session.

This module contains the core domain models used in the chat session.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union


class MessageRole(Enum):
    """Enum representing the role of a message sender."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """Represents a message in the chat session."""
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_call_id: Optional[str] = None


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""
    id: str
    function_name: str
    function_args: Dict[str, Any]
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Represents the result of a tool execution."""
    tool_name: str
    tool_args: Dict[str, Any]
    success: bool = True
    result: Any = None
    error: Optional[str] = None
    tool_call_id: str = ""
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary for serialization"""
        return {
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "tool_call_id": self.tool_call_id,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolResult':
        """Create a ToolResult from a dictionary"""
        result = cls(
            tool_name=data["tool_name"],
            tool_args=data["tool_args"],
            success=data.get("success", True),
            result=data.get("result"),
            error=data.get("error"),
            tool_call_id=data.get("tool_call_id", "")
        )
        result.timestamp = data.get("timestamp", datetime.now().timestamp())
        return result


@dataclass
class SessionState:
    """Represents the current state of a chat session."""
    cwd: str
    initial_directory: str
    executed_commands: List[str] = field(default_factory=list)
    used_tools: List[Dict[str, Any]] = field(default_factory=list)
    created_files: List[str] = field(default_factory=list)
    path_history: List[str] = field(default_factory=list)
    loaded_previous_chat: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary"""
        return {
            "cwd": self.cwd,
            "initial_directory": self.initial_directory,
            "executed_commands": self.executed_commands,
            "used_tools": self.used_tools,
            "created_files": self.created_files,
            "path_history": self.path_history,
            "loaded_previous_chat": self.loaded_previous_chat
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        """Create a SessionState from a dictionary"""
        return cls(
            cwd=data.get("cwd", ""),
            initial_directory=data.get("initial_directory", ""),
            executed_commands=data.get("executed_commands", []),
            used_tools=data.get("used_tools", []),
            created_files=data.get("created_files", []),
            path_history=data.get("path_history", []),
            loaded_previous_chat=data.get("loaded_previous_chat", False)
        )


@dataclass
class LLMResponse:
    """Represents a response from the LLM."""
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    raw_response: Any = None
    error: Optional[str] = None 