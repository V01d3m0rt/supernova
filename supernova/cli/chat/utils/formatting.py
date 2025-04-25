"""
Formatting utilities for chat sessions.

This module contains utility functions for formatting chat messages and tool results.
"""

import json
from typing import Any, Dict, List, Optional, Union


def format_rich_objects(obj: Any) -> str:
    """
    Format rich objects for display in the chat.
    
    Args:
        obj: The object to format
        
    Returns:
        A string representation of the object
    """
    try:
        if isinstance(obj, (dict, list)):
            return json.dumps(obj, indent=2)
        elif hasattr(obj, "to_dict"):
            return json.dumps(obj.to_dict(), indent=2)
        elif hasattr(obj, "__dict__"):
            return json.dumps(obj.__dict__, indent=2)
        else:
            return str(obj)
    except Exception:
        return str(obj)


def format_command_result(command: str, result: Dict[str, Any]) -> str:
    """
    Format a command result for display.
    
    Args:
        command: The command that was executed
        result: The result of the command
        
    Returns:
        Formatted result string
    """
    # Check if the command succeeded
    success = result.get("success", False)
    
    # Format the result
    formatted_result = f"Command: {command}\n"
    formatted_result += f"Status: {'Success' if success else 'Failed'}\n"
    
    # Add stdout if available
    if "stdout" in result and result["stdout"]:
        formatted_result += f"Output:\n```\n{result['stdout']}\n```\n"
    
    # Add stderr if available
    if "stderr" in result and result["stderr"]:
        formatted_result += f"Error:\n```\n{result['stderr']}\n```\n"
    
    return formatted_result


def format_tool_result(tool_name: str, result: Any) -> str:
    """
    Format a tool result for display.
    
    Args:
        tool_name: The name of the tool
        result: The result of the tool
        
    Returns:
        Formatted result string
    """
    try:
        # For dictionaries and lists, pretty print as JSON
        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2)
        # For other types, just convert to string
        else:
            return str(result)
    except Exception as e:
        return f"Error formatting result: {str(e)}\nRaw result: {result}" 