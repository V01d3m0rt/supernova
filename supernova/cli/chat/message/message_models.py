"""
Message models for chat sessions.
"""

import time
import datetime
from typing import Any, Dict, Optional

class Message:
    """
    Represents a message in the chat session.
    """
    def __init__(
        self, 
        role: str, 
        content: str, 
        name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a message.
        
        Args:
            role: The role of the message sender (user, assistant, system)
            content: The content of the message
            name: Optional name for the message sender
            tool_call_id: Optional ID of the tool call
            metadata: Optional metadata for the message
        """
        self.role = role
        self.content = content
        self.name = name
        self.tool_call_id = tool_call_id
        self.metadata = metadata or {}
        self.timestamp = datetime.datetime.now().isoformat()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary for serialization"""
        result = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
        
        if self.name:
            result["name"] = self.name
            
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
            
        return result
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create a Message from a dictionary"""
        message = cls(
            role=data["role"],
            content=data["content"],
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            metadata=data.get("metadata", {})
        )
        message.timestamp = data.get("timestamp", datetime.datetime.now().isoformat())
        return message


class ToolResult:
    """
    Represents the result of a tool execution.
    """
    def __init__(
        self, 
        tool_name: str, 
        tool_args: Dict[str, Any], 
        success: bool = True, 
        result: Any = None, 
        error: str = None, 
        tool_call_id: str = ""
    ):
        """
        Initialize a tool result.
        
        Args:
            tool_name: The name of the tool that was executed
            tool_args: The arguments that were passed to the tool
            success: Whether the tool execution was successful
            result: The result of the tool execution
            error: Error message if the tool execution failed
            tool_call_id: ID of the tool call (if available)
        """
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.success = success
        self.result = result
        self.error = error
        self.tool_call_id = tool_call_id
        self.timestamp = time.time()
        
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
        result.timestamp = data.get("timestamp", time.time())
        return result