"""
SuperNova - AI-powered development assistant within the terminal.

Main implementation of the chat session.
"""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

# Import our components
from supernova.cli.error_handler import ErrorHandler
from supernova.cli.llm_interface import LLMInterface
from supernova.cli.tool_handler import ToolHandler
from supernova.cli.ui_manager import UIManager
from supernova.cli.session_manager import SessionManager

# Keep the ToolResult class for backward compatibility
class ToolResult:
    """
    Represents the result of a tool execution.
    
    Attributes:
        tool_name (str): The name of the tool that was executed.
        tool_args (dict): The arguments passed to the tool.
        success (bool): Whether the tool execution was successful.
        result (Any): The result of the tool execution.
        error (str): Error message if the tool execution failed.
    """
    
    def __init__(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        success: bool = True,
        result: Any = None,
        error: str = None,
    ):
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.success = success
        self.result = result
        self.error = error
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "success": self.success,
            "result": self.result,
            "error": self.error,
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolResult":
        """Create from dictionary."""
        return cls(
            tool_name=data.get("tool_name", ""),
            tool_args=data.get("tool_args", {}),
            success=data.get("success", False),
            result=data.get("result"),
            error=data.get("error"),
        )


class ChatSession:
    """
    Manages the interactive chat session with the AI assistant.
    
    This class acts as a high-level orchestrator, delegating specific 
    responsibilities to specialized components following the Single Responsibility
    Principle.
    """
    
    def __init__(
        self,
        working_dir: Path = None,
        chat_id: str = None,
        config: Dict[str, Any] = None,
        conversation_mode: str = "chat",
        debug: bool = True,
    ):
        """
        Initialize the chat session.
        
        Args:
            working_dir: The working directory for the chat session.
            chat_id: The ID of the chat. If None, a UUID will be generated.
            config: Configuration options.
            conversation_mode: The conversation mode, "chat" or "plan".
            debug: Whether to enable debug logging.
        """
        # Set up basic attributes
        self.working_dir = working_dir or Path.cwd()
        self.chat_id = chat_id or str(uuid.uuid4())
        self.config = config or {}
        self.conversation_mode = conversation_mode
        self.debug = debug
        
        # Set up logging
        log_level = logging.DEBUG if debug else logging.INFO
        self.logger = self._setup_logger(log_level)
        
        # Set up the console for rich output
        self.console = Console()
        
        # Initialize the session state
        self.session_state = {
            "cwd": str(self.working_dir),
            "initial_dir": str(self.working_dir),
            "executed_commands": [],
            "used_tools": [],
            "created_files": [],
            "path_history": [str(self.working_dir)],
            "last_action_result": None,
        }
        
        # Initialize specialized components (following Dependency Inversion Principle)
        self.error_handler = self._create_error_handler()
        self.session_manager = self._create_session_manager()
        self.llm_interface = self._create_llm_interface()
        self.tool_handler = self._create_tool_handler()
        self.ui_manager = self._create_ui_manager()
        
        # Message management
        self.messages = []
        
        # Load messages from session manager if chat_id is provided
        if chat_id:
            self._load_chat_history()
    
    def _create_error_handler(self) -> ErrorHandler:
        """Create and configure the error handler."""
        return ErrorHandler(logger=self.logger)
    
    def _create_session_manager(self) -> SessionManager:
        """Create and configure the session manager."""
        return SessionManager(logger=self.logger)
    
    def _create_llm_interface(self) -> LLMInterface:
        """Create and configure the LLM interface."""
        api_key = self.config.get("openai_api_key", None)
        model = self.config.get("model", "gpt-4o")
        temperature = self.config.get("temperature", 0.7)
        max_tokens = self.config.get("max_tokens", None)
        
        return LLMInterface(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            logger=self.logger
        )
    
    def _create_tool_handler(self) -> ToolHandler:
        """Create and configure the tool handler."""
        return ToolHandler(session_state=self.session_state, logger=self.logger)
    
    def _create_ui_manager(self) -> UIManager:
        """Create and configure the UI manager."""
        return UIManager(working_dir=self.working_dir, logger=self.logger)
    
    def _setup_logger(self, log_level: int) -> logging.Logger:
        """Set up the logger for the chat session."""
        logger = logging.getLogger("supernova.chat_session")
        logger.setLevel(log_level)
        
        # Create a console handler if none exists
        if not logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            
            # Create a formatter
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            console_handler.setFormatter(formatter)
            
            # Add the handler to the logger
            logger.addHandler(console_handler)
        
        return logger
    
    def _load_chat_history(self) -> None:
        """Load messages from the session manager."""
        try:
            session_data = self.session_manager.load_session(self.chat_id)
            if session_data and "messages" in session_data:
                self.messages = session_data["messages"]
                self.logger.debug(f"Loaded {len(self.messages)} messages from session: {self.chat_id}")
        except Exception as e:
            self.logger.error(f"Error loading chat history: {str(e)}")
            self.error_handler.log_error(f"Error loading chat history: {str(e)}")
    
    def add_message(self, content: str, role: str = "user") -> None:
        """
        Add a message to the chat history.
        
        Args:
            content: The message content.
            role: The role of the message sender (user, assistant, system).
        """
        # Ensure content is a string
        if not isinstance(content, str):
            content = str(content)
            
        # Add the message to the history
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        self.messages.append(message)
        
        # Save to session manager
        try:
            self.session_manager.add_message(self.chat_id, message)
        except Exception as e:
            self.logger.error(f"Error saving message to session: {str(e)}")
            self.error_handler.log_error(f"Error saving message to session: {str(e)}")
    
    def add_tool_result_message(self, tool_result: dict) -> None:
        """
        Add a message for a tool result.
        
        Args:
            tool_result: The result of a tool execution.
        """
        # Extract tool information
        tool_name = tool_result.get("tool_name", "unknown")
        success = tool_result.get("success", False)
        error = tool_result.get("error", None)
        
        # Format the content based on success/failure
        if success:
            content = f"Tool {tool_name} executed successfully"
            if "result" in tool_result:
                # Format the result nicely
                formatted_result = self._format_tool_result(tool_result["result"])
                content += f"\nResult: {formatted_result}"
        else:
            content = f"Error executing tool {tool_name}: {error or 'unknown error'}"
            
        # Add the message
        self.add_message(content, role="tool")
    
    def _format_tool_result(self, result: Any) -> str:
        """
        Format a tool result for display.
        
        Args:
            result: The result to format.
            
        Returns:
            Formatted result string.
        """
        # Delegate to the tool handler
        return self.tool_handler.format_result(result)
    
    def get_session_state_summary(self) -> str:
        """
        Get a summary of the current session state.
        
        Returns:
            A string summarizing the current session state.
        """
        # Get the current working directory
        cwd = self.session_state.get("cwd", "")
        initial_dir = self.session_state.get("initial_dir", "")
        path_history = self.session_state.get("path_history", [])
        executed_commands = self.session_state.get("executed_commands", [])
        used_tools = self.session_state.get("used_tools", [])
        created_files = self.session_state.get("created_files", [])
        last_action_result = self.session_state.get("last_action_result", "")
        
        # Format the summary
        summary = []
        
        if cwd:
            summary.append(f"Current directory: {cwd}")
        
        if initial_dir and initial_dir != cwd:
            summary.append(f"Initial directory: {initial_dir}")
        
        if path_history and len(path_history) > 1:
            summary.append(f"Path history: {' -> '.join(path_history[-3:])}")
        
        if executed_commands:
            # Show the last 3 commands
            last_commands = executed_commands[-3:]
            summary.append(f"Recent commands: {', '.join(last_commands)}")
        
        if used_tools:
            # Show the last 3 tools
            last_tools = [t.get("tool_name", "unknown") for t in used_tools[-3:]]
            summary.append(f"Recent tools: {', '.join(last_tools)}")
        
        if created_files:
            # Show the last 3 files
            last_files = created_files[-3:]
            summary.append(f"Recent files created: {', '.join(last_files)}")
        
        if last_action_result:
            summary.append(f"Last action result: {last_action_result}")
        
        return "\n".join(summary)
    
    def update_session_state(self, key: str, value: Any) -> None:
        """
        Update a value in the session state.
        
        Args:
            key: The key to update.
            value: The new value.
        """
        self.session_state[key] = value
        
        # Also update the tool handler's session state
        self.tool_handler.session_state = self.session_state
    
    def get_completion(
        self,
        content: str,
        system_prompt: str = None,
        stream: bool = True,
    ) -> Dict[str, Any]:
        """
        Get a completion from the LLM.
        
        Args:
            content: The content to send to the LLM.
            system_prompt: Custom system prompt to use.
            stream: Whether to stream the response.
            
        Returns:
            The LLM response.
        """
        try:
            # Add the user message
            self.add_message(content, role="user")
            
            # Display message to the user
            self.ui_manager.display_response(content, role="user")
            
            # Get session state summary for context
            context_message = self.get_session_state_summary()
            
            # Get available tools
            tools = self.tool_handler.get_available_tools_for_llm()
            
            # Format messages for LLM
            messages, tools, tool_choice = self.llm_interface.format_messages_for_llm(
                content=content,
                system_prompt=system_prompt,
                context_message=context_message,
                previous_messages=self.messages[-10:],  # Use last 10 messages
                tools=tools
            )
            
            # Show "thinking" animation
            self.ui_manager.display_thinking_animation("Getting response from AI...")
            
            # Send to LLM
            llm_response = self.llm_interface.get_completion(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice
            )
            
            # Process the LLM response
            processed_response = self.llm_interface.process_response(llm_response)
            
            # Check for tool calls
            if "tool_calls" in processed_response and processed_response["tool_calls"]:
                # Process tool calls
                processed_response = self.tool_handler.process_tool_call_loop(
                    llm_response=llm_response,
                    process_response_fn=self.llm_interface.process_response,
                    format_messages_fn=self.llm_interface.format_messages_for_llm,
                    get_completion_fn=self.llm_interface.get_completion
                )
            
            # Add the assistant message
            if "content" in processed_response and processed_response["content"]:
                self.add_message(processed_response["content"], role="assistant")
                
                # Display the response
                self.ui_manager.display_response(processed_response["content"], role="assistant")
            
            return processed_response
        except Exception as e:
            error_message = f"Error getting completion: {str(e)}"
            self.logger.error(error_message)
            self.error_handler.log_error(error_message)
            return {"error": error_message, "content": f"I encountered an error: {str(e)}"}
    
    def start(self) -> None:
        """Start the chat session."""
        # Display welcome message
        self.ui_manager.display_welcome()
        
        try:
            # Main chat loop
            while True:
                # Get user input
                user_input = self.ui_manager.get_user_input()
                
                # Check for exit commands
                if user_input.lower() in ["exit", "quit", "q"]:
                    break
                
                # Process the input
                self.get_completion(user_input)
        except KeyboardInterrupt:
            self.console.print("[yellow]Session interrupted. Exiting...[/yellow]")
        except Exception as e:
            error_message = f"Error in chat session: {str(e)}"
            self.logger.error(error_message)
            self.error_handler.log_error(error_message)
            self.console.print(f"[red]Error: {error_message}[/red]")
        finally:
            self.console.print("[green]Chat session ended.[/green]")
    
    def display_stream(self, content: str) -> None:
        """
        Display streaming content to the console.
        
        Args:
            content: The content to display.
        """
        # Delegate to the UI manager for display
        self.ui_manager.display_stream(content)
    
    def handle_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a tool call.
        
        Args:
            tool_call: The tool call dictionary.
            
        Returns:
            The result of the tool call.
        """
        # Delegate to the tool handler for display
        return self.tool_handler.handle_tool_call(tool_call)
    
    def process_tool_results(self, tool_results: List[Dict[str, Any]]) -> None:
        """
        Process tool results from handled tool calls.
        
        Args:
            tool_results: List of tool result dictionaries.
        """
        # Delegate to the UI manager for display
        self.ui_manager.display_tool_results(tool_results)
        
        # Record tool results in session state
        for result in tool_results:
            # Add to used tools
            self.session_state.setdefault("used_tools", []).append(result)
            
            # Update last action result
            self.update_session_state("last_action_result", result)
            
            # Check for created files
            if result.get("success") and result.get("tool_name") == "file_create_tool":
                if "result" in result and isinstance(result["result"], dict):
                    filename = result["result"].get("filename")
                    if filename:
                        self.session_state.setdefault("created_files", []).append(filename)
            
            # Check for executed commands
            if result.get("success") and result.get("tool_name") == "terminal_command_tool":
                if "command" in result:
                    command = result["command"]
                    self.session_state.setdefault("executed_commands", []).append(command)
            
            # Add tool result message
            self.add_tool_result_message(result)
    
    def get_available_tools_info(self) -> str:
        """
        Get information about available tools.
        
        Returns:
            A string describing available tools.
        """
        # Delegate to the tool handler for display
        return self.tool_handler.get_available_tools_info()

def start_chat_sync(directory_path: Path) -> None:
    """
    Start a synchronous chat session in the specified directory.
    
    Args:
        directory_path: The directory to start the chat session in.
    """
    try:
        # Create a new chat session instance
        session = ChatSession(working_dir=directory_path)
        
        # Start the chat session
        session.start()
    except Exception as e:
        logging.error(f"Error in chat session: {str(e)}")
        raise
