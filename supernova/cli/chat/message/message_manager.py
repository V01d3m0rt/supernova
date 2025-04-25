"""
Message manager for chat sessions.
"""

import logging
import datetime
from typing import Any, Dict, List, Optional, Union

from supernova.cli.ui_utils import format_rich_objects
from supernova.cli.chat.message.message_models import Message, ToolResult

class MessageManager:
    """
    Manages messages in a chat session.
    """
    def __init__(self, db=None, chat_id=None):
        """
        Initialize the message manager.
        
        Args:
            db: Database manager
            chat_id: Chat ID
        """
        self.db = db
        self.chat_id = chat_id
        self.messages = []
        self.logger = logging.getLogger("supernova.message_manager")
        
    def add_message(self, role: str, content: Any, name: Optional[str] = None, tool_call_id: Optional[str] = None) -> Message:
        """
        Add a message to the chat history.
        
        Args:
            role: The role of the message sender (user, assistant, system)
            content: The content of the message
            name: Optional name for the message sender
            tool_call_id: Optional ID of the tool call
            
        Returns:
            The created message
        """
        # Make sure content is a string
        if not isinstance(content, str):
            try:
                # Try to get a nice string representation using ui_utils
                content = format_rich_objects(content)
            except ImportError:
                # Fall back to str() if the function isn't available
                content = str(content)
                
        # Create message
        message = Message(
            role=role,
            content=content,
            name=name,
            tool_call_id=tool_call_id
        )
        
        # Add to the messages list
        self.messages.append(message.to_dict())
        
        # Save to the database if available
        if self.db and self.chat_id:
            try:
                self.db.add_message(
                    self.chat_id,
                    role,
                    content,
                    metadata={"name": name, "tool_call_id": tool_call_id} if name or tool_call_id else None
                )
            except Exception as e:
                self.logger.error(f"Failed to save message to database: {e}")
                
        return message
    
    def add_tool_result_message(self, tool_result: ToolResult) -> Message:
        """
        Add a tool result message to the chat history.
        
        Args:
            tool_result: The tool result to add
            
        Returns:
            The created message
        """
        # For terminal commands, create a more informative content that includes the command
        content = str(tool_result.result)
        if tool_result.tool_name == "terminal_command" and isinstance(tool_result.tool_args, dict):
            command = tool_result.tool_args.get("command", "")
            explanation = tool_result.tool_args.get("explanation", "")
            if command:
                # Create a formatted result that clearly indicates what command was run
                formatted_content = f"Command executed: `{command}`\n"
                if explanation:
                    formatted_content += f"Purpose: {explanation}\n"
                    
                # Include success/failure status
                formatted_content += f"Status: {'Succeeded' if tool_result.success else 'Failed'}\n"
                
                # Include stdout/stderr if present in the result
                if isinstance(tool_result.result, dict):
                    stdout = tool_result.result.get("stdout", "")
                    stderr = tool_result.result.get("stderr", "")
                    if stdout:
                        formatted_content += f"Output:\n```\n{stdout}```\n"
                    if stderr:
                        formatted_content += f"Error output:\n```\n{stderr}```\n"
                        
                content = formatted_content
        
        # Create message
        return self.add_message(
            role="system",
            content=content,
            name=tool_result.tool_name,
            tool_call_id=tool_result.tool_call_id
        )
    
    def get_messages(self) -> List[Dict[str, Any]]:
        """
        Get all messages.
        
        Returns:
            List of messages
        """
        return self.messages
    
    def load_messages_from_db(self, chat_id: str) -> None:
        """
        Load messages from the database.
        
        Args:
            chat_id: Chat ID to load messages from
        """
        if not self.db:
            return
            
        self.chat_id = chat_id
        db_messages = self.db.get_chat_history(chat_id)
        
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
                
                # Add name and tool_call_id if available in metadata
                if msg["metadata"]:
                    if "name" in msg["metadata"]:
                        self.messages[-1]["name"] = msg["metadata"]["name"]
                    if "tool_call_id" in msg["metadata"]:
                        self.messages[-1]["tool_call_id"] = msg["metadata"]["tool_call_id"]