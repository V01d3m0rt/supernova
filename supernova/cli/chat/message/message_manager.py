"""
Message manager for chat sessions.

This module contains the MessageManager class for managing messages in a chat session.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from supernova.cli.chat.domain.models import Message, ToolResult
from supernova.cli.chat.utils.formatting import format_rich_objects


class MessageManager:
    """
    Manages chat messages for a chat session.
    
    Handles adding, retrieving, and persisting messages.
    """
    
    def __init__(self, db=None, chat_id=None):
        """
        Initialize the message manager.
        
        Args:
            db: Database manager for persisting messages
            chat_id: Current chat ID
        """
        self.logger = logging.getLogger("supernova.chat.message_manager")
        self.db = db
        self.chat_id = chat_id
        self.messages: List[Dict[str, Any]] = []
    
    def add_message(self, role: str, content: Any) -> None:
        """
        Add a message to the chat history.
        
        Args:
            role: The role of the message sender (user, assistant, system, tool)
            content: The content of the message
        """
        # Make sure content is a string
        if not isinstance(content, str):
            try:
                # Try to get a nice string representation using utils
                content = format_rich_objects(content)
            except (ImportError, Exception):
                # Fall back to str() if the function isn't available
                content = str(content)
                
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to the messages list
        self.messages.append(message)
        
        # Save to the database if available
        if self.chat_id and self.db:
            try:
                self.db.add_message(
                    self.chat_id,
                    role,
                    content
                )
            except Exception as e:
                self.logger.error(f"Failed to save message to database: {e}")
    
    def add_tool_result_message(
        self, 
        tool_result: ToolResult
    ) -> None:
        """
        Add a tool result message to the chat history.
        
        Args:
            tool_result: The tool result to add
        """
        tool_name = tool_result.tool_name
        tool_args = tool_result.tool_args
        success = tool_result.success
        result = tool_result.result
        tool_call_id = tool_result.tool_call_id
        
        # For terminal commands, create a more informative content that includes the command
        content = str(result)
        if tool_name == "terminal_command" and isinstance(tool_args, dict):
            command = tool_args.get("command", "")
            explanation = tool_args.get("explanation", "")
            if command:
                # Create a formatted result that clearly indicates what command was run
                formatted_content = f"Command executed: `{command}`\n"
                if explanation:
                    formatted_content += f"Purpose: {explanation}\n"
                    
                # Include success/failure status
                formatted_content += f"Status: {'Succeeded' if success else 'Failed'}\n"
                
                # Include stdout/stderr if present in the result
                if isinstance(result, dict):
                    stdout = result.get("stdout", "")
                    stderr = result.get("stderr", "")
                    if stdout:
                        formatted_content += f"Output:\n```\n{stdout}```\n"
                    if stderr:
                        formatted_content += f"Error output:\n```\n{stderr}```\n"
                        
                content = formatted_content
        
        # Create a formatted tool result message
        message = {
            "role": "system",
            "name": tool_name,
            "content": content,
            "tool_call_id": tool_call_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add to the messages list
        self.messages.append(message)
        
        # Save to the database if available
        if self.chat_id and self.db:
            try:
                # Just use add_message for tool results as well
                self.db.add_message(
                    self.chat_id, 
                    "tool", 
                    content, 
                    {"tool_name": tool_name, "tool_args": json.dumps(tool_args), "success": success, "tool_call_id": tool_call_id}
                )
            except Exception as e:
                self.logger.error(f"Failed to save tool result to database: {e}")
    
    def add_tool_call_message(
        self, 
        tool_name: str, 
        tool_args: Dict[str, Any], 
        tool_call_id: str
    ) -> None:
        """
        Add a tool call message to the chat history.
        
        Args:
            tool_name: Name of the tool being called
            tool_args: Arguments passed to the tool
            tool_call_id: ID of the tool call
        """
        # Ensure args is a string
        if not isinstance(tool_args, str):
            try:
                args_str = json.dumps(tool_args)
            except:
                args_str = str(tool_args)
        else:
            args_str = tool_args
        
        # Create a descriptive content about the tool call
        tool_call_content = f"Tool call: {tool_name}"
        if args_str:
            try:
                # Try to format args as JSON for readability
                if args_str.strip():
                    parsed_args = json.loads(args_str)
                    formatted_args = json.dumps(parsed_args, indent=2)
                    tool_call_content += f"\nArguments:\n```json\n{formatted_args}\n```"
            except json.JSONDecodeError:
                # If parsing fails, just include the raw args
                tool_call_content += f"\nArguments: {args_str}"
        
        # Create a message
        message = {
            "role": "tool",
            "name": tool_name,
            "content": tool_call_content,
            "tool_call_id": tool_call_id,
            "timestamp": datetime.now().isoformat(),
            "is_call": True
        }
        
        # Add to the messages list
        self.messages.append(message)
        
        # Save to the database if available
        if self.chat_id and self.db:
            try:
                self.db.add_message(
                    self.chat_id,
                    "tool",
                    tool_call_content,
                    {"tool_name": tool_name, "tool_call_id": tool_call_id, "is_call": True}
                )
            except Exception as e:
                self.logger.error(f"Failed to save tool call to database: {e}")
    
    def add_tool_summary_message(self, tool_results: List[Dict[str, Any]]) -> None:
        """
        Add a summary message about multiple tool results to help the LLM understand what happened.
        
        Args:
            tool_results: List of tool result dictionaries or ToolResult objects
        """
        if not tool_results:
            return
        
        # Add individual tool messages with proper tool_call_id
        for result in tool_results:
            # Check if result is a dict or ToolResult object
            if isinstance(result, dict):
                tool_name = result.get("tool_name", "unknown")
                success = result.get("result", False).get("success", False) if isinstance(result.get("result"), dict) else False
                tool_call_id = result.get("tool_call_id", "")
                
                # Get result or error
                if success:
                    content = result.get("result", "")
                    # Format terminal command results nicely
                    if tool_name == "terminal_command" and isinstance(content, dict):
                        command = result.get("command", "")
                        if "stdout" in content and content["stdout"]:
                            formatted_content = f"Command executed successfully: {command}\nOutput:\n{content['stdout']}"
                        else:
                            formatted_content = f"Command executed successfully: {command}"
                        content = formatted_content
                else:
                    content = result.get("result", str(result)).get("stderr", str(result)) if isinstance(result.get("result"), dict) else str(result)
                
                # Add as a tool message with proper format
                # Format the message properly for OpenAI's API
                if tool_call_id:
                    # Add tool message
                    message = {
                        "role": "system",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": str(content)
                    }
                    self.messages.append(message)
                    
                    # Save to database if available
                    if self.chat_id and self.db:
                        try:
                            # Add with metadata containing tool info
                            self.db.add_message(
                                self.chat_id,
                                "tool",
                                str(content),
                                {"tool_name": tool_name, "tool_call_id": tool_call_id}
                            )
                        except Exception as e:
                            self.logger.error(f"Failed to save tool message to database: {e}")
            
            # Handle ToolResult objects for backwards compatibility
            elif hasattr(result, "tool_name") and hasattr(result, "success"):
                tool_name = result.tool_name
                success = result.success
                tool_call_id = getattr(result, "tool_call_id", "")
                content = result.result if success else result.error
                
                if tool_call_id:
                    # Add tool message
                    message = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": str(content)
                    }
                    self.messages.append(message)
                    
                    # Save to database if available
                    if self.chat_id and self.db:
                        try:
                            # Add with metadata containing tool info
                            self.db.add_message(
                                self.chat_id,
                                "tool",
                                str(content),
                                {"tool_name": tool_name, "tool_call_id": tool_call_id}
                            )
                        except Exception as e:
                            self.logger.error(f"Failed to save tool message to database: {e}")
        
        # Count successful and failed tools
        success_count = sum(1 for tr in tool_results if isinstance(tr, dict) and tr.get("success", False) or 
                           not isinstance(tr, dict) and hasattr(tr, "success") and tr.success)
        error_count = len(tool_results) - success_count
        
        # Create a system message with execution summary
        summary = f"Executed {len(tool_results)} tool calls: {success_count} succeeded, {error_count} failed."
        self.logger.debug(summary)
    
    def get_messages(self) -> List[Dict[str, Any]]:
        """
        Get all messages in the chat.
        
        Returns:
            List of message dictionaries
        """
        return self.messages
    
    def load_messages_from_db(self) -> None:
        """
        Load messages from the database for the current chat_id.
        """
        if not self.db or not self.chat_id:
            return
            
        db_messages = self.db.get_chat_history(self.chat_id)
        if db_messages:
            # Extract only the fields we need
            self.messages = []
            
            for msg in db_messages:
                self.messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": msg["timestamp"],
                    "metadata": msg["metadata"]
                })
    
    def clear_messages(self) -> None:
        """Clear all messages in the chat."""
        self.messages = []
        
    def set_chat_id(self, chat_id: str) -> None:
        """
        Set the chat ID.
        
        Args:
            chat_id: Chat ID to set
        """
        self.chat_id = chat_id 