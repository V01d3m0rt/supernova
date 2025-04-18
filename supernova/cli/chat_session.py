"""
SuperNova - AI-powered development assistant within the terminal.

Chat session for interactive AI assistance.
"""

import json
import os
import re
import subprocess
import time
import threading
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple, Set
import uuid
import traceback
import logging
import copy
import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.box import ROUNDED
from prompt_toolkit.formatted_text import HTML

from supernova.config import loader
from supernova.config.schema import SuperNovaConfig
from supernova.core import command_runner, context_analyzer, llm_provider, tool_manager
from supernova.persistence.db_manager import DatabaseManager
from supernova.cli.ui_utils import (
    loading_animation, animated_print, display_welcome_banner,
    display_tool_execution, display_response, animated_status,
    create_progress_bar, display_command_result, display_thinking_animation,
    fade_in_text, display_chat_input_prompt, display_tool_confirmation,
    display_generating_animation, theme_color, set_theme
)

console = Console()

# TODO: VS Code Integration - Consider implementing a VSCodeIntegration class that can:
# 1. Detect if running within VS Code
# 2. Access VS Code extensions API if available
# 3. Provide methods to open files, show information, etc.

class ToolResult:
    """
    Represents the result of a tool execution.
    """
    def __init__(self, tool_name: str, tool_args: Dict[str, Any], success: bool = True, result: Any = None, error: str = None, tool_call_id: str = ""):
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

class ChatSession:
    """Interactive chat session with the AI assistant."""
    
    def __init__(self, config=None, db=None, initial_directory=None):
        """
        Initialize the chat session with the given configuration.
        
        Args:
            config: Configuration object
            db: Database manager
            initial_directory: Initial working directory
        """
        # Load configuration if not provided
        self.config = config or loader.load_config()
        
        # Initialize logger
        self.logger = logging.getLogger("supernova.chat_session")
        
        # Set up initial directory (current directory if not specified)
        self.initial_directory = Path(initial_directory or os.getcwd())
        self.cwd = self.initial_directory
        
        # Create .supernova directory in the working directory
        local_supernova_dir = self.cwd / ".supernova"
        local_supernova_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up database
        if db is not None:
            self.db = db
        else:
            db_path = local_supernova_dir / "history.db"
            from supernova.persistence.db_manager import DatabaseManager
            self.db = DatabaseManager(db_path)
        
        # Get the LLM provider
        self.llm_provider = llm_provider.get_provider()
        
        # Get the tool manager
        self.tool_manager = tool_manager.ToolManager()
        
        # Initialize chat state
        self.chat_id = None
        self.messages = []
        self.session_state = {
            "executed_commands": [],
            "used_tools": [],
            "created_files": [],
            "cwd": str(self.cwd),
            "path_history": [str(self.cwd)],
            "loaded_previous_chat": False
        }
        
        console.print(f"Working in: {self.cwd}")
        console.print(f"Initial directory: {self.initial_directory} (operations will be restricted to this directory)")
        
        # Initialize other components
        self.tool_manager.load_extension_tools()
        
        # Setup prompt session with history
        self.prompt_session = PromptSession(
            history=InMemoryHistory(),
            auto_suggest=AutoSuggestFromHistory(),
            completer=WordCompleter(["exit", "quit"]),
            style=Style.from_dict({
                "prompt": "ansicyan bold",
            })
        )
        
        # Initialize streaming state variables
        self._tool_calls_reported = False
        self._streaming_started = False
        self._latest_full_content = ""
        self._latest_tool_calls = []
        
        # Reset streaming state to ensure all required variables are initialized
        self._reset_streaming_state()
        
        # Initialize session with history in the local .supernova directory
        history_file = self.cwd / ".supernova" / "prompt_history"
        self.prompt_session = PromptSession(history=FileHistory(str(history_file)))
    
    def analyze_project(self) -> str:
        """
        Analyze the project context with enhanced UI.
        
        Returns:
            Summary of the project
        """
        try:
            # Display progress messages sequentially to avoid nested live displays
            console.print(f"[{theme_color('primary')}]Scanning files...[/{theme_color('primary')}]")
            time.sleep(0.3)  # Simulate work
            
            console.print(f"[{theme_color('primary')}]Identifying project type...[/{theme_color('primary')}]")
            time.sleep(0.3)  # Simulate work
            
            console.print(f"[{theme_color('primary')}]Finalizing analysis...[/{theme_color('primary')}]")
            
            # Actual project analysis
            project_summary = context_analyzer.analyze_project(self.cwd)
            self.session_state["project_summary"] = project_summary
            
            # Display success message with animation
            animated_print(f"[{theme_color('success')}]✅ Project analyzed successfully: {project_summary}[/{theme_color('success')}]", delay=0.01)
            
            return project_summary
        except Exception as e:
            error_msg = f"Could not analyze project: {str(e)}"
            self.session_state["project_error"] = error_msg
            
            # Display error with animation
            animated_print(f"[{theme_color('warning')}]⚠️ {error_msg}[/{theme_color('warning')}]", delay=0.01)
            
            return "Unknown project"
    
    def load_or_create_chat(self) -> None:
        """Load the latest chat for the project or create a new one with enhanced UI."""
        if not self.db.enabled:
            return
        
        # Display progress messages sequentially to avoid nested live displays
        console.print(f"[{theme_color('secondary')}]Initializing chat session...[/{theme_color('secondary')}]")
        time.sleep(0.3)  # Brief pause for effect
        
        # Get the latest chat for this project
        self.chat_id = self.db.get_latest_chat_for_project(self.cwd)
        
        if self.chat_id:
            # Load existing chat with animation
            console.print(f"[{theme_color('secondary')}]Loading previous chat history...[/{theme_color('secondary')}]")
            
            db_messages = self.db.get_chat_history(self.chat_id)
            if db_messages:
                # Extract only the fields we need
                self.messages = []
                
                # Load messages with a simple counter
                message_count = len(db_messages)
                console.print(f"[{theme_color('secondary')}]Loading {message_count} messages...[/{theme_color('secondary')}]")
                
                for msg in db_messages:
                    self.messages.append({
                        "role": msg["role"],
                        "content": msg["content"],
                        "timestamp": msg["timestamp"],
                        "metadata": msg["metadata"]
                    })
                
                # Display success message with animation
                animated_print(
                    f"[{theme_color('success')}]📚 Loaded previous chat with {len(self.messages)} messages[/{theme_color('success')}]", 
                    delay=0.01
                )
                
                self.session_state["loaded_previous_chat"] = True
                self.session_state["previous_message_count"] = len(self.messages)
        else:
            # Create a new chat with animation
            console.print(f"[{theme_color('secondary')}]Creating new chat session...[/{theme_color('secondary')}]")
            
            self.chat_id = self.db.create_chat(self.cwd)
           
             # Display success message with animation
            animated_print(
                f"[{theme_color('success')}]🆕 Created new chat session[/{theme_color('success')}]", 
                delay=0.01
            )
            
            self.session_state["loaded_previous_chat"] = False
    
    def add_message(self, role, content):
        """
        Add a message to the chat history.
        
        Args:
            role: The role of the message sender (user, assistant, system)
            content: The content of the message
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Add to the messages list
        self.messages.append(message)
        
        # Save to the database if available
        if hasattr(self, 'chat_id') and self.chat_id and hasattr(self, 'db'):
            try:
                self.db.add_message(
                    self.chat_id,
                    role,
                    content
                )
            except Exception as e:
                self.logger.error(f"Failed to save message to database: {e}")
    
    def add_tool_result_message(self, tool_name, tool_args, success, result, tool_call_id=""):
        """
        Add a tool result message to the chat history.
        
        Args:
            tool_name: Name of the tool that was called
            tool_args: Arguments passed to the tool
            success: Whether the tool execution was successful
            result: The result or error message from the tool
            tool_call_id: The ID of the tool call (if available)
        """
        # Create a formatted tool result message
        message = {
            "role": "tool",
            "name": tool_name,
            "content": str(result),
            "tool_call_id": tool_call_id,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Add to the messages list
        self.messages.append(message)
        
        # Save to the database if available
        if hasattr(self, 'chat_id') and self.chat_id and hasattr(self, 'db'):
            try:
                # Just use add_message for tool results as well
                self.db.add_message(
                    self.chat_id, 
                    "tool", 
                    str(result), 
                    {"tool_name": tool_name, "tool_args": json.dumps(tool_args), "success": success}
                )
            except Exception as e:
                self.logger.error(f"Failed to save tool result to database: {e}")
    
    def get_llm_response(self):
        """
        Get a response from the LLM based on the current messages.
        
        Returns:
            A dictionary containing the LLM's response and any tool calls
        """
        try:
            # Format messages for the LLM
            formatted_messages = self.format_messages_for_llm()
            
            # Get available tools
            available_tools = self.tool_manager.get_available_tools_for_llm(self.session_state)
            
            # Get LLM response
            response = self.llm_provider.get_completion(
                messages=formatted_messages,
                tools=available_tools,
                stream=False
            )
            
            # Process the response
            assistant_response = ""
            tool_calls = []
            
            # Extract assistant response and tool calls
            if isinstance(response, dict):
                # Handle dictionary response
                assistant_response = response.get("content", "")
                tool_calls = response.get("tool_calls", [])
            else:
                # Handle object response
                assistant_response = getattr(response, "content", "")
                tool_calls = getattr(response, "tool_calls", [])
            
            return {
                "assistant_response": assistant_response,
                "tool_calls": tool_calls
            }
            
        except Exception as e:
            self.logger.error(f"Error getting LLM response: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            # Return an error message
            return {
                "assistant_response": f"Error: {e}",
                "tool_calls": []
            }
    
    def format_messages_for_llm(self):
        """
        Format the chat messages for the LLM.
        
        Returns:
            A list of formatted messages for the LLM
        """
        # Return the messages list directly if it's already formatted correctly
        return self.messages
    
    def get_available_tools_info(self) -> str:
        """
        Get information about available tools.
        
        Returns:
            String describing available tools
        """
        if not self.tool_manager:
            return "No tools available"
            
        tools = self.tool_manager.get_available_tools_for_llm(self.session_state)
        if not tools:
            return "No tools available"
            
        tool_info = []
        for tool in tools:
            name = tool.get("name", "unknown")
            description = tool.get("description", "No description")
            tool_info.append(f"- {name}: {description}")
            
        return "\n".join(tool_info)
    
    def get_session_state_summary(self) -> str:
        """
        Get a summary of the current session state.
        
        Returns:
            String summary of session state
        """
        summary = []
        
        # Add working directory info
        summary.append(f"Current directory: {self.session_state['cwd']}")
        summary.append(f"Initial directory: {self.session_state['initial_directory']}")
        
        # Add path history
        if self.session_state.get("path_history"):
            summary.append("Path history:")
            for path in self.session_state["path_history"][-5:]:  # Show last 5 paths
                summary.append(f"- {path}")
        
        # Add executed commands
        if self.session_state.get("executed_commands"):
            summary.append("Recently executed commands:")
            for cmd in self.session_state["executed_commands"][-5:]:  # Show last 5 commands
                summary.append(f"- {cmd}")
        
        # Add used tools
        if self.session_state.get("used_tools"):
            summary.append("Recently used tools:")
            for tool in self.session_state["used_tools"][-5:]:  # Show last 5 tools
                summary.append(f"- {tool}")
        
        # Add created files
        if self.session_state.get("created_files"):
            summary.append("Recently created files:")
            for file in self.session_state["created_files"][-5:]:  # Show last 5 files
                summary.append(f"- {file}")
        
        # Add last action result if available
        if self.session_state.get("LAST_ACTION_RESULT"):
            summary.append("Last action result:")
            summary.append(str(self.session_state["LAST_ACTION_RESULT"]))
        
        return "\n".join(summary)
    
    def generate_system_prompt(self, project_summary: str = "") -> str:
        """
        Generate the system prompt for the LLM.
        
        Args:
            project_summary: Optional project summary to include
            
        Returns:
            System prompt for the LLM
        """
        tools_info = self.get_available_tools_info()
        session_state = self.get_session_state_summary()
        
        # If no project summary provided, use the one from session state
        if not project_summary:
            project_summary = self.session_state.get("project_summary", "Unknown project")
        
        # Build the system prompt
        prompt_parts = [
            "You are SuperNova, an AI-powered development assistant that helps with coding tasks.",
            f"You are working in the project: {project_summary}",
            "You have access to the following tools:",
            tools_info,
            "\nCurrent session state:",
            session_state,
            "\nImportant rules:",
            "1. Always stay within the initial directory specified with -d",
            "2. Use tools to perform actions when appropriate",
            "3. Provide clear explanations of your actions",
            "4. Format code blocks with proper syntax highlighting",
            "5. Handle errors gracefully and provide helpful error messages"
        ]
        
        return "\n".join(prompt_parts)
    
    def get_context_message(self) -> str:
        """
        Get the context message for the current session.
        
        Returns:
            Context message string
        """
        # Get system prompt
        system_prompt = self.generate_system_prompt()
        
        # Get context message
        context_parts = [
            "Current working directory: " + self.session_state["cwd"],
            "Initial directory: " + self.session_state["initial_directory"],
            "Path history:",
            *[f"- {path}" for path in self.session_state["path_history"][-5:]],
            "\nRecently executed commands:",
            *[f"- {cmd}" for cmd in self.session_state["executed_commands"][-5:]],
            "\nRecently used tools:",
            *[f"- {tool}" for tool in self.session_state["used_tools"][-5:]],
            "\nRecently created files:",
            *[f"- {file}" for file in self.session_state["created_files"][-5:]]
        ]
        
        if self.session_state.get("LAST_ACTION_RESULT"):
            context_parts.append("\nLast action result:")
            context_parts.append(str(self.session_state["LAST_ACTION_RESULT"]))
        
        return "\n".join(context_parts)
    
    def send_to_llm(self, content: str, debug_mode: bool = False, stream: bool = False) -> Dict[str, Any]:
        """
        Send a message to the LLM and get a response.
        
        Args:
            content: The message content
            debug_mode: Whether to print debug information
            stream: Whether to stream the response
            
        Returns:
            LLM response
        """
        # Get context message
        context_msg = self.get_context_message()
        
        # Get session history
        previous_messages = self.messages[-10:]  # Limit to last 10 messages
        
        # Format messages for the LLM
        include_tools = bool(self.tool_manager)
        llm_messages, tools, tool_choice = self.format_messages_for_llm(
            content=content,
            system_prompt=self.generate_system_prompt(),
            context_msg=context_msg,
            previous_messages=previous_messages,
            include_tools=include_tools
        )
        
        # If streaming, reset the streaming state
        if stream:
            self._reset_streaming_state()
        
        # Send to LLM
        try:
            response = self.llm_provider.get_completion(
                messages=llm_messages,
                tools=tools,
                tool_choice=tool_choice,
                stream=stream,
                stream_callback=self.handle_stream_chunk if stream else None
            )
            
            if debug_mode:
                console.print("[yellow]Debug: LLM Response[/yellow]")
                console.print(response)
            
            return response
        except Exception as e:
            console.print(f"[red]Error getting LLM response: {str(e)}[/red]")
            return {"error": str(e)}
    
    def _run_thinking_animation(self, stop_event: threading.Event) -> None:
        """
        Run the thinking animation until the stop event is set.
        
        Args:
            stop_event: Event to signal when to stop the animation
        """
        # Use the thinking animation with no fixed duration
        try:
            # More elaborate thinking animation with brain activity
            thinking_frames = [
                "🧠 ⚡ Thinking...",
                "🧠 ✨ Thinking...",
                "🧠 💭 Thinking...",
                "🧠 💡 Thinking...",
                "🧠 🔄 Thinking...",
                "🧠 🔍 Thinking...",
                "🧠 📊 Thinking...",
                "🧠 🔮 Thinking..."
            ]
            
            # Brain activity patterns (simulating neural activity)
            brain_patterns = [
                "▁▂▃▄▅▆▇█▇▆▅▄▃▂▁",
                "▁▁▂▂▃▃▄▄▅▅▆▆▇▇██▇▇▆▆▅▅▄▄▃▃▂▂▁▁",
                "▂▃▅▇█▇▅▃▂▂▃▅▇█▇▅▃▂",
                "▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅",
                "▁▂▄▆█▆▄▂▁▁▂▄▆█▆▄▂▁"
            ]
            
            # Timer display
            start_time = time.time()
            
            # Create a panel for the thinking animation
            panel_width = 60
            
            # Use Rich's Live display for smooth updates
            with Live("", refresh_per_second=10, transient=True) as live:
                while not stop_event.is_set():
                    elapsed = time.time() - start_time
                    
                    # Select frame and pattern based on time
                    frame_idx = int(elapsed * 8) % len(thinking_frames)
                    pattern_idx = int(elapsed * 5) % len(brain_patterns)
                    
                    # Create the panel content
                    frame = thinking_frames[frame_idx]
                    pattern = brain_patterns[pattern_idx]
                    
                    # Format timer
                    timer = f"{elapsed:.1f}s elapsed"
                    
                    # Create panel with thinking animation
                    panel = Panel(
                        f"{frame}\n\n{pattern}\n\n⏱️ {timer}",
                        title="🤔 Processing",
                        title_align="left",
                        border_style=theme_color("primary"),
                        box=ROUNDED,
                        width=panel_width,
                        padding=(1, 2)
                    )
                    
                    # Update the live display
                    live.update(panel)
                    
                    time.sleep(0.1)
            
        except Exception as e:
            # Fallback to simple message if animation fails
            console.print(f"[{theme_color('primary')}]🧠 Thinking...[/{theme_color('primary')}]")
            while not stop_event.is_set():
                time.sleep(0.1)
        
    def handle_stream_chunk(self, chunk: Dict[str, Any]) -> None:
        """
        Handle a streaming response chunk from the LLM.
        
        This gets called repeatedly as the LLM generates content, and is responsible for:
        1. Updating the accumulated content/tool calls
        2. Processing tool calls if they appear
        3. Displaying content that has been added
        
        Args:
            chunk: The chunk response from the LLM
        """
        # Process the streaming response chunk
        result = self.llm_provider.process_streaming_response(
            chunk, 
            self.streaming_accumulated_content, 
            self.streaming_accumulated_tool_calls
        )
        
        # Update accumulated content and tool calls from the result
        self.streaming_accumulated_content = result.get("full_content", self.streaming_accumulated_content)
        self.streaming_accumulated_tool_calls = result.get("accumulated_tool_calls", self.streaming_accumulated_tool_calls)
        
        if result.get("type") == "content":
            # Display new content
            content = result.get("content", "")
            if content:
                self.display_stream(content)
                
        elif result.get("type") == "tool_calls":
            tool_calls = result.get("tool_calls", [])
            if tool_calls:
                self.logger.debug(f"Received {len(tool_calls)} tool calls in stream chunk")
                
                # Convert tool calls to dictionaries
                converted_tool_calls = [self._convert_tool_call_to_dict(tc) for tc in tool_calls]
                
                # Process each tool call, but only if it's complete enough to process
                for tool_call in converted_tool_calls:
                    # Only process complete tool calls (those with both name and arguments)
                    if 'function' in tool_call and 'name' in tool_call['function']:
                        function_name = tool_call['function'].get('name')
                        function_args = tool_call['function'].get('arguments', '')
                        
                        # Check if we have enough information to process this tool call
                        if function_name and function_name.strip():
                            self.logger.debug(f"Processing stream tool call: {function_name}")
                            
                            # Process the tool call
                            tool_result = self.handle_tool_call(tool_call)
                            
                            # Display the result if we have one
                            if tool_result:
                                # Display tool processing animation
                                self.handle_tool_results({
                                    "tool_name": function_name,
                                    "content": tool_result.get("result", ""),
                                    "error": "error" in tool_result
                                })
                        else:
                            self.logger.warning(f"Incomplete tool call received in stream (missing name): {tool_call}")
                    else:
                        self.logger.debug(f"Incomplete tool call information, waiting for more data: {tool_call}")
    
    def handle_tool_call(self, tool_call: Dict[str, Any], seen_call_ids: Set[str] = None) -> Optional[Dict]:
        """
        Handle a tool call.
        
        Args:
            tool_call: The tool call dict from the LLM
            seen_call_ids: Set of tool call IDs that have already been processed
            
        Returns:
            Optional[Dict]: The result of the tool call or None if the tool is not found
        """
        # Initialize seen_call_ids if not provided
        if seen_call_ids is None:
            seen_call_ids = set()
            
        # Skip if we've already processed this tool call
        call_id = tool_call.get('id')
        if call_id and call_id in seen_call_ids:
            self.logger.debug(f"Skipping already processed tool call: {call_id}")
            return None
            
        # Add to seen calls if ID exists
        if call_id:
            seen_call_ids.add(call_id)
        
        # Check if function data is present
        if 'function' not in tool_call:
            self.logger.warning(f"Missing function data in tool call: {json.dumps(tool_call)}")
            return {
                "error": "incomplete_tool_call",
                "message": "No function data provided in tool call"
            }
        
        # Get function details
        function_data = tool_call['function']
        
        # Check if function has a name
        if 'name' not in function_data or not function_data['name']:
            self.logger.warning(f"No tool name provided in tool call: {json.dumps(tool_call)}")
            return {
                "error": "incomplete_tool_call",
                "message": "No tool name provided in tool call"
            }
        
        tool_name = function_data['name']
        
        # Parse function arguments
        function_args = '{}'
        if 'arguments' in function_data:
            function_args = function_data['arguments']
            
        # Parse function arguments as JSON if they're a string
        parsed_args = {}
        if isinstance(function_args, str):
            try:
                # Try to parse potentially incomplete JSON
                function_args = function_args.strip()
                
                # If it's completely empty, use empty dict
                if not function_args:
                    parsed_args = {}
                else:
                    # Handle common streaming artifacts
                    if function_args.endswith(','):
                        function_args = function_args[:-1]
                        
                    # Try to parse as JSON
                    parsed_args = json.loads(function_args)
            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to parse tool arguments as JSON: {function_args}. Error: {str(e)}")
                return {
                    "error": "invalid_arguments",
                    "message": f"Invalid arguments format: {str(e)}",
                    "tool_name": tool_name
                }
        else:
            # Already a dict
            parsed_args = function_args
        
        # Get the tool function
        tool_function = self.tool_manager.get_tool_handler(tool_name)
        
        if not tool_function:
            self.logger.warning(f"Unknown tool: {tool_name}")
            return {
                "error": "unknown_tool",
                "message": f"Unknown tool: {tool_name}",
                "tool_name": tool_name
            }
        
        try:
            # Execute the tool function
            self.logger.debug(f"Executing tool {tool_name} with args: {parsed_args}")
            result = tool_function(args=parsed_args)
            return {
                "result": result,
                "tool_name": tool_name
            }
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {
                "error": "execution_error",
                "message": f"Error executing {tool_name}: {str(e)}",
                "tool_name": tool_name
            }
                
    def get_user_input(self) -> str:
        """
        Read input from the user with enhanced UI.
        
        Returns:
            User input string
        """
        try:
            # Get input from prompt session with custom styling
            style = Style.from_dict({
                'prompt': f'bold {theme_color("secondary")}',
                'completion': f'italic {theme_color("info")}',
                'bottom-toolbar': f'bg:{theme_color("primary")} {theme_color("info")}',
                # Add more styling as needed
            })
            
            # Create a completer with common commands
            command_completer = WordCompleter([
                'exit', 'quit', 'help', 'clear', 'history',
                'search', 'find', 'create', 'edit', 'run',
                'install', 'update', 'delete', 'show',
                'explain', 'analyze', 'fix', 'optimize'
            ])
            
            # Use the prompt session with the new style and auto-suggestions
            user_input = self.prompt_session.prompt(
                "",
                style=style,
                completer=command_completer,
                auto_suggest=AutoSuggestFromHistory(),
                complete_in_thread=True,
                complete_while_typing=True,
                bottom_toolbar=" Press Tab for suggestions | Ctrl+C to cancel "
            )
            
            # Add to message history and display in a panel
            console.print(f"[{theme_color('secondary')}]Processing your input...[/{theme_color('secondary')}]")
            self.add_message("user", user_input)
            
            # Display user input in a panel
            self.display_response(user_input, role="user")
        
            return user_input
        except KeyboardInterrupt:
            console.print(f"[{theme_color('warning')}]Operation interrupted[/{theme_color('warning')}]")
            return "exit"
        except Exception as e:
            console.print(f"[{theme_color('error')}]Error reading input:[/{theme_color('error')}] {str(e)}")
            return "exit"
        
    def run(self):
        """
        Run the chat session with enhanced UI.
        """
        try:
            # Set theme based on config or default
            theme_name = self.config.ui.theme if hasattr(self.config, 'ui') and hasattr(self.config.ui, 'theme') else "default"
            set_theme(theme_name)
            
            # Simple startup message without live display
            console.print(f"[{theme_color('primary')}]Starting SuperNova...[/{theme_color('primary')}]")
            time.sleep(0.5)  # Brief pause for effect
            
            self.run_chat_loop()
            
        except KeyboardInterrupt:
            # Graceful exit with animation
            fade_in_text(f"\n[{theme_color('secondary')}]Interrupted by user. Exiting SuperNova...[/{theme_color('secondary')}]")
            
        except Exception as e:
            # Error handling with animation
            console.print(f"\n[{theme_color('error')}]Error running chat session:[/{theme_color('error')}] {str(e)}")
            
            if hasattr(e, "__traceback__"):
                traceback.print_tb(e.__traceback__)

    def _reset_streaming_state(self) -> None:
        """Reset the streaming state for a new stream."""
        self._streaming_started = False
        self._tool_calls_reported = False
        self._latest_full_content = ""
        self._latest_tool_calls = []
        self.streaming_accumulated_content = ""
        self.streaming_accumulated_tool_calls = {}

    async def read_input(self) -> str:
        """Read user input from the console."""
        # Just use a simple prompt for now
        return input("> ")

    def process_tool_calls(self, tool_calls):
        """
        Process a list of tool calls and return the results.
        
        Args:
            tool_calls: List of tool call objects
            
        Returns:
            List of tool result objects
        """
        results = []
        
        for tool_call in tool_calls:
            tool_call_dict = self._convert_tool_call_to_dict(tool_call)
            
            # Log the tool call
            debug_mode = hasattr(self.config, 'debug') and self.config.debug
            if debug_mode:
                self.logger.debug(f"Processing tool call: {json.dumps(tool_call_dict, indent=2)}")
            
            # Get the tool name and arguments
            tool_name = tool_call_dict.get('function', {}).get('name')
            tool_args = tool_call_dict.get('function', {}).get('arguments', {})
            tool_id = tool_call_dict.get('id', '')
            
            # Look up the tool
            tool = self.tool_manager.get_tool_handler(tool_name)
            
            if not tool:
                # Tool not found
                results.append(
                    ToolResult(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        success=False,
                        error=f"Tool '{tool_name}' not found",
                        tool_call_id=tool_id,
                    )
                )
                continue
                
            try:
                # Execute the tool
                tool_result = self.tool_manager.execute_tool(
                    tool_name=tool_name,
                    args=tool_args,
                    session_state=self.session_state,
                    working_dir=self.cwd
                )
                
                # Ensure the result is serializable
                tool_result = self._ensure_serializable(tool_result)
                
                # Add a successful result
                results.append(
                    ToolResult(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        success=True,
                        result=tool_result,
                        tool_call_id=tool_id,
                    )
                )
            except Exception as e:
                # Log the error
                self.logger.error(f"Error executing tool '{tool_name}': {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                
                # Add an error result
                results.append(
                    ToolResult(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        success=False,
                        error=str(e),
                        tool_call_id=tool_id,
                    )
                )
        
        return results

    def _convert_tool_call_to_dict(self, tool_call):
        """
        Convert a tool call object to a serializable dictionary
        
        Args:
            tool_call: A tool call object from the LLM API
            
        Returns:
            A serializable dictionary representation of the tool call
        """
        # If it's already a dict, return it
        if isinstance(tool_call, dict):
            return tool_call
            
        # Otherwise convert it to a dict
        try:
            return {
                "id": getattr(tool_call, "id", ""),
                "type": getattr(tool_call, "type", "function"),
                "function": {
                    "name": getattr(tool_call.function, "name", ""),
                    "arguments": json.loads(getattr(tool_call.function, "arguments", "{}")),
                }
            }
        except Exception as e:
            self.logger.error(f"Error converting tool call to dict: {e}")
            return {
                "id": "",
                "type": "function",
                "function": {
                    "name": "",
                    "arguments": {}
                }
            }
            
    def _ensure_serializable(self, obj):
        """
        Ensure an object is JSON serializable
        
        Args:
            obj: Any object
            
        Returns:
            A serializable version of the object
        """
        try:
            # Test if it's serializable
            json.dumps(obj)
            return obj
        except (TypeError, OverflowError):
            # If it's a simple type, convert to string
            if isinstance(obj, (int, float, bool, str, type(None))):
                return str(obj)
                
            # If it's a list, recursively process each item
            elif isinstance(obj, list):
                return [self._ensure_serializable(item) for item in obj]
                
            # If it's a dict, recursively process each value
            elif isinstance(obj, dict):
                return {k: self._ensure_serializable(v) for k, v in obj.items()}
                
            # For any other type, convert to string
            else:
                return str(obj)

    def process_tool_call_loop(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process tool calls in a loop until there are no more tool calls to process.
        Returns the final response after all tool calls have been processed.
        
        Args:
            llm_response: The initial LLM response which may contain tool calls
            
        Returns:
            The final response after all tool calls have been processed
        """
        # Ensure we return a properly structured response
        processed_response = {
            "content": "",
            "tool_results": []
        }
        
        if not llm_response:
            return processed_response
            
        # Initialize content if it exists in the response
        if isinstance(llm_response, dict) and "content" in llm_response:
            processed_response["content"] = llm_response["content"]
        
        # Create a copy of the response to work with
        response = copy.deepcopy(llm_response)
        tool_messages = []
        iteration_count = 0
        max_iterations = self.config.chat.max_tool_iterations
        
        try:
            # Loop until no more tool calls or we hit maximum iterations
            while (isinstance(response, dict) and 'tool_calls' in response 
                and response['tool_calls'] and iteration_count < max_iterations):
                iteration_count += 1
                self.logger.debug(f"Tool iteration {iteration_count}/{max_iterations}")
                
                # Process all tool calls in this response
                tool_results = self.process_tool_calls(response['tool_calls'])
                
                # Add to the overall tool results
                if tool_results:
                    processed_response["tool_results"].extend(tool_results)
                
                # Create tool messages for each result and handle display
                for result in tool_results:
                    # Create a tool message for the result
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": result.get("tool_call_id", ""),
                        "name": result.get("tool_name", "unknown_tool"),
                        "content": str(result.get("content", ""))
                    }
                    
                    # Add the message
                    tool_messages.append(tool_message)
                    
                    # Display the result including any errors
                    self.handle_tool_results({
                        "tool_name": result.get("tool_name", "unknown_tool"),
                        "content": result.get("content", ""),
                        "error": result.get("error", False)
                    })
                
                # If we have tool messages, send them back to LLM
                if tool_messages:
                    console.print(f"\n[dim][Tool step {iteration_count}/{max_iterations}] Thinking based on tool results...[/dim]")
                    
                    # Add the tool messages to the conversation
                    for tool_message in tool_messages:
                        self.add_message(tool_message["role"], tool_message["content"])
                    
                    # Get context message
                    context_msg = self.get_context_message()
                    
                    # Generate system prompt
                    system_prompt = self.generate_system_prompt()
                    
                    # Format messages for LLM
                    messages, tools, model = self.format_messages_for_llm(
                        "Continue based on tool results", 
                        system_prompt, 
                        context_msg, 
                        self.messages[-10:],  # Only include the last 10 messages
                        include_tools=True
                    )
                    
                    # Get the LLM response
                    next_response = self.llm_provider.get_completion(
                        messages=messages,
                        tools=tools, 
                        stream=False
                    )
                    
                    # Process the response
                    processed_next = self.process_llm_response(next_response)
                    
                    # Update the main content if there is any
                    if processed_next.get("content"):
                        processed_response["content"] = processed_next["content"]
                    
                    # Update response for next iteration
                    response = next_response
                    
                    # Clear tool messages for next iteration
                    tool_messages = []
                else:
                    # No tool messages, so we're done
                    break
        except Exception as e:
            self.logger.error(f"Error in tool call loop: {str(e)}")
            console.print(f"\n[red]Error in tool call loop: {str(e)}[/red]")
            # Ensure we have something in the response
            if not processed_response["content"]:
                processed_response["content"] = "I encountered an error while processing. Let me try again."
            
        # Return the final processed response
        return processed_response

    def display_stream(self, content: str) -> None:
        """
        Display streaming content from the LLM.
        
        Args:
            content: Content chunk to display
        """
        # Print the content without a newline to allow continuous streaming
        console.print(content, end="", markup=False)
        # Ensure the content is displayed immediately
        console.file.flush()

    def run_chat_loop(self, initial_user_input=None, auto_run=False):
        """
        Run the chat loop, processing user inputs and displaying assistant responses.
        
        Args:
            initial_user_input: Optional starting message from the user
            auto_run: Whether to run the loop automatically without user input
        """
        try:
            # Welcome message
            if not auto_run:
                display_welcome_banner()
            
            # Analyze the project if needed
            if not self.session_state.get("project_summary"):
                project_summary = self.analyze_project()
                
            # Load or create chat history
            if not self.chat_id:
                self.load_or_create_chat()
            
            while True:
                # Get or use initial user input
                if initial_user_input:
                    user_input = initial_user_input
                    initial_user_input = None  # Clear for next iteration
                else:
                    # Get the user input
                    user_input = self.get_user_input()
                
                # Check for empty input or exit commands
                if not user_input.strip():
                    continue
                
                if user_input.lower() in ["exit", "quit", "/exit", "/quit"]:
                    print("Exiting chat...")
                    break
                
                # Add the user message to the chat history
                self.add_message("user", user_input)
                
                # Show thinking animation
                thinking_stop_event = threading.Event()
                thinking_thread = threading.Thread(
                    target=self._run_thinking_animation,
                    args=(thinking_stop_event,)
                )
                thinking_thread.daemon = True
                thinking_thread.start()
                
                try:
                    # Get a response from the LLM
                    llm_response = self.get_llm_response()
                    
                    # Stop thinking animation
                    thinking_stop_event.set()
                    if thinking_thread.is_alive():
                        thinking_thread.join()
                    
                    # Process any tool calls in the response
                    
                    while "tool_calls" in llm_response and llm_response["tool_calls"]:
                        
                        
                        # Process all tool calls and get their results
                        tool_results = self.process_tool_calls(llm_response["tool_calls"])
                        
                        # Add tool results as messages
                        for tool_result in tool_results:
                            # Format and add the tool result message
                            success = tool_result.success
                            raw_result = tool_result.result if success else tool_result.error
                            
                            # Ensure the result is a string
                            if isinstance(raw_result, dict):
                                try:
                                    formatted_result = json.dumps(raw_result, indent=2)
                                except:
                                    formatted_result = str(raw_result)
                            else:
                                formatted_result = str(raw_result)
                            
                            # Add as a tool message
                            self.add_tool_result_message(
                                tool_name=tool_result.tool_name,
                                tool_args=tool_result.tool_args,
                                success=success,
                                result=formatted_result,
                                tool_call_id=tool_result.tool_call_id
                            )
                            
                            # Display the tool result to the user
                            self.display_response(formatted_result, role="tool")
                        
                        # Get the next response from the LLM
                        llm_response = self.get_llm_response()
                    
                    # Display the final assistant response
                    assistant_message = llm_response.get("assistant_response", "")
                    if assistant_message:
                        # Add to history
                        self.add_message("assistant", assistant_message)
                        
                        # Display to the user
                        self.display_response(assistant_message, role="assistant")
                except Exception as e:
                    # Stop thinking animation if still running
                    thinking_stop_event.set()
                    if thinking_thread.is_alive():
                        thinking_thread.join()
                    
                    self.logger.error(f"Error processing request: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())
                    self.display_response(f"Error processing request: {e}", role="system")
        
        except KeyboardInterrupt:
            print("\nExiting chat...")
        except Exception as e:
            print(f"Error in chat loop: {e}")
            import traceback
            print(traceback.format_exc())

    def display_response(self, response, role="assistant"):
        """
        Display the assistant's response with proper formatting.
        
        Args:
            response: The text response from the assistant
            role: The role of the message sender (default: "assistant")
        """
        # Import the display_response function from ui_utils
        from supernova.cli.ui_utils import display_response as ui_display_response
        
        # Call the display_response function
        ui_display_response(response, role=role)

def start_chat_sync(chat_dir: Optional[Union[str, Path]] = None) -> None:
    """
    Start a synchronous chat session.
    
    Args:
        chat_dir: Optional directory to start the chat in
    """
    # Create a chat session and run it
    chat_session = ChatSession(initial_directory=chat_dir)
    chat_session.run_chat_loop()
