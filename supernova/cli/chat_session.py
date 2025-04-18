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
    def __init__(self, tool_name: str, tool_args: Dict[str, Any], result: Any = None, is_error: bool = False):
        """
        Initialize a tool result.
        
        Args:
            tool_name: The name of the tool that was executed
            tool_args: The arguments that were passed to the tool
            result: The result of the tool execution
            is_error: Whether the result is an error
        """
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.result = result
        self.is_error = is_error
        self.timestamp = time.time()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary for serialization"""
        return {
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "result": self.result,
            "is_error": self.is_error,
            "timestamp": self.timestamp
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolResult':
        """Create a ToolResult from a dictionary"""
        result = cls(
            tool_name=data["tool_name"],
            tool_args=data["tool_args"],
            result=data.get("result"),
            is_error=data.get("is_error", False)
        )
        result.timestamp = data.get("timestamp", time.time())
        return result

class ChatSession:
    """Interactive chat session with the AI assistant."""
    
    def __init__(self, cwd: Optional[Union[str, Path]] = None):
        """
        Initialize a new chat session.
        
        Args:
            cwd: Current working directory (default: current directory)
        """
        # Load configuration
        self.config = loader.load_config()
        
        # Setup working directory
        if cwd is not None:
            self.cwd = Path(cwd).resolve()
        else:
            self.cwd = Path.cwd().resolve()
        
        # Store the initial directory to enforce directory constraints
        self.initial_directory = self.cwd
        
        console.print(f"Working in: {self.cwd}")
        console.print(f"Initial directory: {self.initial_directory} (operations will be restricted to this directory)")
        
        # Initialize database for persistence
        # Create .supernova directory in the working directory
        local_supernova_dir = self.cwd / ".supernova"
        local_supernova_dir.mkdir(parents=True, exist_ok=True)
        db_path = local_supernova_dir / "history.db"
        self.db = DatabaseManager(db_path)
        
        # Initialize LLM provider from config
        self.llm_provider = llm_provider.get_provider()
        
        # Initialize other components
        self.tool_manager = tool_manager.ToolManager()
        console.print("Core tools loaded successfully")
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Load extension tools
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
        
        # Initialize chat history for this session
        self.messages = []
        self.chat_id = None  # Will be set when loading/creating chat
        
        # Initialize session state
        self.session_state = {
            "cwd": str(self.cwd),
            "initial_directory": str(self.initial_directory),  # Store the initial directory in session state
            "executed_commands": [],
            "used_tools": [],
            "created_files": [],
            "last_command": None,
            "LAST_ACTION_RESULT": None,
            "start_time": time.time(),
            "path_history": [str(self.cwd)],  # Track all paths we've visited
            "environment": {
                "os": os.name,
                "platform": os.uname().sysname if hasattr(os, "uname") else os.name
            },
            "all_tool_calls": []  # Track all tool calls
        }
        
        # TODO: VS Code Integration - Check if running in VS Code and initialize integration
        # if is_vscode_environment():
        #     self.vscode = VSCodeIntegration()
        #     self.session_state["editor"] = "vscode"
        
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
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """
        Add a message to the chat history.
        
        Args:
            role: Role of the message sender (user, assistant, system)
            content: Content of the message
            metadata: Optional metadata for the message
        """
        # Make sure content is a non-empty string
        if content is None:
            content = "No content provided"
        
        # Convert to string if not already
        if not isinstance(content, str):
            content = str(content)
            
        # Add to in-memory history
        timestamp = int(time.time())
        message = {
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "metadata": metadata
        }
        self.messages.append(message)
        
        # Update session state
        if role == "user":
            self.session_state["last_user_message"] = content
        
        # Add to database if enabled
        if self.db.enabled and self.chat_id:
            try:
                self.db.add_message(self.chat_id, role, content, metadata)
            except Exception as e:
                console.print(f"[yellow]Warning: Error adding message to database: {str(e)}[/yellow]")
    
    def format_messages_for_llm(
        self, 
        content: str, 
        system_prompt: str, 
        context_msg: str, 
        previous_messages: List[Dict[str, str]],
        include_tools: bool = False
    ) -> Tuple[List[Dict[str, str]], Optional[List[Dict]], Optional[str]]:
        """
        Format messages for the LLM API call.
        
        Args:
            content: The new user message
            system_prompt: The system prompt to use
            context_msg: Additional context specific to this session
            previous_messages: Previous messages in the conversation
            include_tools: Whether to include tools in the LLM call
            
        Returns:
            Tuple of (messages list, tools list or None, tool_choice or None)
        """
        # Combine system prompt and context into a single system message
        combined_system_content = f"{system_prompt}\n\n{context_msg}"
        
        # Create the message list with the system message first
        llm_messages = [{"role": "system", "content": combined_system_content}]
        
        # Add previous messages
        llm_messages.extend(previous_messages)
        
        # Add the new user message
        llm_messages.append({"role": "user", "content": content})
        
        # Initialize tools and tool_choice to None
        tools = None
        tool_choice = None
        
        # If tools are requested, get them from the tool manager
        if include_tools and self.tool_manager:
            tools = self.tool_manager.get_available_tools_for_llm(self.session_state)
            tool_choice = "auto"  # Let the model decide when to use tools
        
        return llm_messages, tools, tool_choice
    
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
        Handle a stream chunk from the LLM.
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
                
                # Process each tool call, but only if it's complete enough to process
                for tool_call in tool_calls:
                    # Only process complete tool calls (those with both name and arguments)
                    if 'function' in tool_call and 'name' in tool_call['function']:
                        function_name = tool_call['function'].get('name')
                        function_args = tool_call['function'].get('arguments', '')
                        
                        # Check if we have enough information to process this tool call
                        if function_name and function_name.strip():
                            self.logger.debug(f"Processing stream tool call: {function_name}")
                            
                            # Process the tool call
                            result = self.handle_tool_call(tool_call)
                            
                            # If we got a result, add it to the message history
                            if result:
                                # Add the result to the state
                                self.session_state["tool_results"].append(result)
                                
                                # Display the result
                                self.handle_tool_results(result)
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
            result = tool_function(**parsed_args)
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
    
    def process_llm_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the LLM response.
        
        Args:
            response: The LLM response to process
            
        Returns:
            Processed response
        """
        processed_response = {
            "content": "",
            "tool_results": []
        }
        
        # Add debug logging
        self.logger.debug(f"Processing LLM response type: {type(response)}")
        
        # Handle different response formats
        if isinstance(response, str):
            processed_response["content"] = response
        elif hasattr(response, 'choices') and hasattr(response.choices[0], 'message'):
            message = response.choices[0].message
            content = getattr(message, 'content', "")
            if content:
                processed_response["content"] = content
                
            # Handle tool calls
            if hasattr(message, 'tool_calls') and message.tool_calls:
                self.logger.debug(f"Found {len(message.tool_calls)} tool_calls in response")
                for tool_call in message.tool_calls:
                    tool_result = self.handle_tool_call(tool_call)
                    if tool_result is not None:
                        processed_response["tool_results"].append(tool_result)
                    else:
                        self.logger.warning(f"Received None tool result from handle_tool_call")
        elif isinstance(response, dict):
            # Handle streamed content if available
            if self._latest_full_content and not 'content' in response:
                processed_response["content"] = self._latest_full_content
            elif 'content' in response:
                processed_response["content"] = response['content']
            
            # Handle tool calls from response
            if 'tool_calls' in response and response['tool_calls']:
                self.logger.debug(f"Found {len(response['tool_calls'])} tool_calls in response dict")
                for tool_call in response['tool_calls']:
                    tool_result = self.handle_tool_call(tool_call)
                    if tool_result is not None:
                        processed_response["tool_results"].append(tool_result)
                    else:
                        self.logger.warning(f"Received None tool result from handle_tool_call for tool_call: {tool_call}")
            # Handle accumulated tool calls from streaming
            elif hasattr(self, '_latest_tool_calls') and self._latest_tool_calls and self._tool_calls_reported:
                # Process the accumulated tool calls from streaming
                self.logger.debug(f"Processing {len(self._latest_tool_calls)} accumulated tool calls from streaming")
                console.print(f"[dim]Processing {len(self._latest_tool_calls)} accumulated tool calls from streaming[/dim]")
                for tool_call in self._latest_tool_calls:
                    tool_result = self.handle_tool_call(tool_call)
                    if tool_result is not None:
                        processed_response["tool_results"].append(tool_result)
                    else:
                        self.logger.warning(f"Received None tool result from handle_tool_call for accumulated tool call")
                    
        # Add to message history
        if processed_response["content"]:
            self.add_message("assistant", processed_response["content"])
        
        # Log processed response for debugging
        self.logger.debug(f"Processed response content length: {len(processed_response['content'])}")
        self.logger.debug(f"Processed response tool results count: {len(processed_response['tool_results'])}")
            
        return processed_response
    
    def process_assistant_response(self, response: Any) -> str:
        """
        Process the assistant's response to handle tool calls and code blocks.
        
        This method is responsible for:
        1. Handling tool calls from LiteLLM
        2. Processing code blocks for display and file creation
        
        Args:
            response: The response from the LLM
            
        Returns:
            The processed response with tool calls handled
        """
        if not response:
            return "No response from the assistant."
        
        # Get the final response content to process
        response_content = ""
        
        # Extract content and check for tool calls
        if hasattr(response, 'choices') and hasattr(response.choices[0], 'message'):
            message = response.choices[0].message
            
            # Get content if available
            if hasattr(message, 'content') and message.content:
                response_content = message.content
            else:
                response_content = "Assistant used tools to respond to your request."
                
            # Check for tool calls that need to be executed
            if hasattr(message, 'tool_calls') and message.tool_calls:
                # Process each tool call
                for tool_call in message.tool_calls:
                    try:
                        # Extract tool information using LiteLLM's format
                        if hasattr(tool_call, 'function'):
                            function = tool_call.function
                            tool_name = getattr(function, 'name', '')
                            tool_args_str = getattr(function, 'arguments', '{}')
                            
                            # Parse arguments
                            try:
                                tool_args = json.loads(tool_args_str)
                            except json.JSONDecodeError:
                                console.print(f"[red]Error parsing tool arguments:[/red] {tool_args_str}")
                                continue
                            
                            # Special handling for terminal commands
                            if tool_name == "terminal_command":
                                self.handle_terminal_command(tool_args)
                            else:
                                # Display tool information
                                console.print(f"\n[bold cyan]Tool Call:[/bold cyan] {tool_name}")
                                console.print(f"Arguments: {tool_args}")
                                
                                # Ask for confirmation
                                confirmation = console.input("\nExecute this tool? (y/n): ").lower()
                                if confirmation != "y":
                                    console.print("[yellow]Tool execution cancelled[/yellow]")
                                    continue
                                
                                # Execute the tool
                                console.print("[bold]Executing tool...[/bold]")
                                
                                # Create context from session state
                                tool_context = {
                                    "session_state": self.session_state
                                }
                                
                                # Execute tool
                                result = self.tool_manager.execute_tool(
                                    tool_name,
                                    tool_args,
                                    session_state=self.session_state,
                                    working_dir=self.cwd
                                )
                                
                                # Record tool usage
                                self.session_state["used_tools"].append({
                                    "name": tool_name,
                                    "args": tool_args,
                                    "timestamp": int(time.time()),
                                    "success": result.get("success", False)
                                })
                                
                                # Display result
                                if result.get("success", False):
                                    console.print("[green]Tool executed successfully[/green]")
                                    console.print(result.get("result", "No result"))
                                    
                                    # Get the full tool result
                                    tool_result = result.get("result", "")
                                    
                                    # Limit the tool result content for LLM context only (not for display)
                                    limited_result = tool_result
                                    if tool_result and "\n" in tool_result:
                                        lines = tool_result.splitlines()
                                        line_limit = self.config.chat.tool_result_line_limit
                                        if len(lines) > line_limit:
                                            # Keep only the last N lines
                                            truncated_lines = lines[-line_limit:]
                                            limited_result = f"[Output truncated to last {line_limit} lines]\n" + "\n".join(truncated_lines)
                                    
                                    # Add system message with limited content for LLM
                                    self.add_message(
                                        "system",
                                        f"TOOL EXECUTION: {tool_name} | SUCCESS: {result.get('success', False)} | RESULT: {limited_result}"
                                    )
                                else:
                                    console.print(f"[red]Tool execution failed:[/red] {result.get('error', 'Unknown error')}")
                                    
                                    # Add system message
                                    self.add_message(
                                        "system",
                                        f"TOOL EXECUTION: {tool_name} | SUCCESS: {result.get('success', False)} | RESULT: {result.get('error', 'Unknown error')}"
                                    )
                    except Exception as e:
                        console.print(f"[red]Error processing tool call:[/red] {str(e)}")
        elif isinstance(response, str):
            # Simple string response
            response_content = response
        else:
            # Fallback
            response_content = str(response)
        
        # Create files from code blocks if present
        file_results = self.create_files_from_response(response_content)
        
        # Update session state with file results
        if file_results:
            self.session_state["created_files"] = file_results
            
        return response_content
    
    def handle_terminal_command(self, args: Dict[str, Any]) -> None:
        """
        Handle terminal command execution safely.
        
        Args:
            args: Terminal command arguments
        """
        if "command" not in args:
            console.print("[red]Error:[/red] Terminal command missing 'command' argument")
            return
        
        command = args.get("command")
        explanation = args.get("explanation", "")
        
        # Use the initial directory as the working directory to ensure we're always in
        # the specified directory, not the current directory that might have changed
        working_dir = args.get("working_dir", str(self.initial_directory))
        
        # Show command information
        console.print("\n[bold cyan]Command Detected:[/bold cyan] `{}`".format(command))
        if explanation:
            console.print(f"[bold yellow]Purpose:[/bold yellow] {explanation}")
        
        # Ask for confirmation
        confirmation = console.input("\nExecute this command? (y/n): ").lower()
        if confirmation != "y":
            console.print("[yellow]Command execution cancelled[/yellow]")
            self.add_message("system", f"Command execution cancelled: `{command}`")
            return
        
        # Execute the command
        console.print("[bold]Executing command...[/bold]")
        console.print(f"Working directory: {working_dir}")
        
        try:
            exit_code, stdout, stderr = command_runner.run_command(
                command,
                cwd=Path(working_dir),
                timeout=self.config.command_execution.timeout,
                require_confirmation=False  # Already confirmed above
            )
            
            # Record command execution in session state
            self.session_state["executed_commands"].append({
                "command": command,
                "exit_code": exit_code,
                "timestamp": int(time.time())
            })
            
            # Special handling for cd commands to update the working directory
            if command.strip().startswith("cd ") and exit_code == 0:
                # Extract the target directory
                target_dir = command.strip()[3:].strip()
                
                # Handle special cases
                if target_dir == "..":
                    # Go up one directory, but never above the initial directory
                    new_cwd = self.cwd.parent
                    if not str(new_cwd).startswith(str(self.initial_directory)):
                        new_cwd = self.initial_directory
                        console.print(f"[yellow]Warning: Cannot go above the initial directory: {self.initial_directory}[/yellow]")
                elif target_dir.startswith("/"):
                    # Absolute path - ensure it's within the initial directory
                    new_cwd = Path(target_dir)
                    if not str(new_cwd).startswith(str(self.initial_directory)):
                        console.print(f"[red]Error: Cannot change to directory outside the initial directory: {self.initial_directory}[/red]")
                        self.add_message("system", f"Error: Cannot change to directory {new_cwd} because it is outside the initial directory {self.initial_directory}")
                        # Stay in current directory
                        new_cwd = self.cwd
                else:
                    # Relative path
                    new_cwd = self.cwd / target_dir
                    # Check if this would go outside the initial directory
                    if not str(new_cwd).startswith(str(self.initial_directory)):
                        console.print(f"[red]Error: Cannot change to directory outside the initial directory: {self.initial_directory}[/red]")
                        self.add_message("system", f"Error: Cannot change to directory {new_cwd} because it is outside the initial directory {self.initial_directory}")
                        # Stay in current directory
                        new_cwd = self.cwd
                
                # Update the working directory
                self.cwd = new_cwd
                self.session_state["cwd"] = str(new_cwd)
                
                # Add to path history
                if "path_history" not in self.session_state:
                    self.session_state["path_history"] = []
                self.session_state["path_history"].append(str(new_cwd))
                
                console.print(f"[green]Working directory updated to:[/green] {new_cwd}")
                console.print(f"[dim]Path history:[/dim] {' -> '.join(self.session_state['path_history'][-3:])}")
            
            # Limit stdout and stderr for LLM context only
            limited_stdout = stdout
            limited_stderr = stderr
            line_limit = self.config.chat.tool_result_line_limit

            if stdout and "\n" in stdout:
                stdout_lines = stdout.splitlines()
                if len(stdout_lines) > line_limit:
                    # Keep only the last N lines
                    truncated_lines = stdout_lines[-line_limit:]
                    limited_stdout = f"[Output truncated to last {line_limit} lines]\n" + "\n".join(truncated_lines)

            if stderr and "\n" in stderr:
                stderr_lines = stderr.splitlines()
                if len(stderr_lines) > line_limit:
                    # Keep only the last N lines
                    truncated_lines = stderr_lines[-line_limit:]
                    limited_stderr = f"[Error output truncated to last {line_limit} lines]\n" + "\n".join(truncated_lines)

            # Display result with improved wording
            if exit_code == 0:
                console.print("[green]Command executed successfully[/green]")
                if stdout:
                    console.print(Panel(stdout, title="Command Output", expand=False))
                
                # Add system message with limited content for LLM - make success prominent
                self.add_message("system", f"COMMAND EXECUTED SUCCESSFULLY: `{command}`\n\nOutput:\n```\n{limited_stdout}\n```")
                
                # Update LAST_ACTION_RESULT to clearly indicate success
                self.session_state["LAST_ACTION_RESULT"] = f"COMMAND: '{command}' | STATUS: SUCCESS | OUTPUT: {limited_stdout}"
            else:
                console.print(f"[red]Command failed with exit code {exit_code}[/red]")
                if stderr:
                    console.print(Panel(stderr, title="Error Output", expand=False))
                if stdout:
                    console.print(Panel(stdout, title="Command Output", expand=False))
                
                # Add system message with limited content for LLM - make failure very prominent
                self.add_message(
                    "system", 
                    f"COMMAND FAILED (exit code {exit_code}): `{command}`\n\nError:\n```\n{limited_stderr}\n```\n\nOutput:\n```\n{limited_stdout}\n```"
                )
                
                # Update LAST_ACTION_RESULT to clearly indicate failure with the command
                self.session_state["LAST_ACTION_RESULT"] = f"COMMAND: '{command}' | STATUS: FAILED (exit code {exit_code}) | ERROR: {limited_stderr}"
        except subprocess.TimeoutExpired:
            console.print(f"[red]Command timed out after {self.config.command_execution.timeout} seconds[/red]")
            self.add_message("system", f"Command timed out: `{command}`")
        except Exception as e:
            console.print(f"[red]Error executing command:[/red] {str(e)}")
            self.add_message("system", f"Error executing command: `{command}`\nError: {str(e)}")
    
    def extract_code_blocks(self, text: str) -> List[Dict[str, str]]:
        """
        Extract code blocks from the text.
        
        Args:
            text: Text to extract code blocks from
            
        Returns:
            List of dictionaries with code blocks and their languages
        """
        # Match code blocks with language specification
        pattern = r"```(\w*)\n(.*?)```"
        matches = re.finditer(pattern, text, re.DOTALL)
        
        code_blocks = []
        for match in matches:
            language = match.group(1).strip() or "text"
            code = match.group(2).strip()
            code_blocks.append({
                "language": language,
                "code": code
            })
        
        return code_blocks
    
    def display_response(self, response: str) -> None:
        """
        Display the assistant's response with appropriate formatting.
        
        Args:
            response: The response to display
        """
        console.print("\n[Assistant]:")
        
        if self.config.chat.syntax_highlighting:
            # Extract and highlight code blocks
            code_blocks = self.extract_code_blocks(response)
            
            if code_blocks:
                # Replace code blocks with placeholders
                placeholder_response = response
                for i, block in enumerate(code_blocks):
                    placeholder = f"___CODE_BLOCK_{i}___"
                    pattern = f"```{block['language']}\n{re.escape(block['code'])}\n```"
                    placeholder_response = re.sub(pattern, placeholder, placeholder_response, flags=re.DOTALL)
                
                # Split by placeholders
                parts = re.split(r"___CODE_BLOCK_(\d+)___", placeholder_response)
                
                # Display each part with appropriate formatting
                for i, part in enumerate(parts):
                    if i % 2 == 0:  # Text part
                        if part.strip():
                            console.print(Markdown(part))
                    else:  # Code block
                        block_index = int(part)
                        if block_index < len(code_blocks):
                            block = code_blocks[block_index]
                            console.print(Syntax(
                                block["code"], 
                                block["language"], 
                                theme="monokai",
                                line_numbers=True if len(block["code"].splitlines()) > 5 else False
                            ))
            else:
                # No code blocks, just print as markdown
                console.print(Markdown(response))
        else:
            # Simple text output
            console.print(response)
    
    def extract_files_from_response(self, response: str) -> List[Dict[str, str]]:
        """
        Extract potential files from the response text.
        
        Looks for patterns like:
        ```java:com/example/nikhiltest/Main.java
        package com.example.nikhiltest;
        
        import org.springframework.boot.SpringApplication;
        ...
        ```
        
        Args:
            response: The response text
            
        Returns:
            List of dictionaries with file information
        """
        files = []
        lines = response.split("\n")
        
        in_file_block = False
        current_file = {"path": "", "content": ""}
        
        for i, line in enumerate(lines):
            if in_file_block:
                if line.strip().startswith("```"):
                    # End of file block
                    in_file_block = False
                    if current_file["path"] and current_file["content"]:
                        files.append(current_file)
                    current_file = {"path": "", "content": ""}
                else:
                    # Add to file content
                    if current_file["content"]:
                        current_file["content"] += "\n" + line
                    else:
                        current_file["content"] = line
            else:
                # Look for file code block markers
                # Pattern: ```language:path/to/file
                if line.strip().startswith("```"):
                    parts = line.strip()[3:].split(":", 1)
                    if len(parts) == 2:
                        language, file_path = parts
                        in_file_block = True
                        current_file = {"path": file_path.strip(), "content": "", "language": language.strip()}
        
        # Handle case where text ends while still in file block
        if in_file_block and current_file["path"] and current_file["content"]:
            files.append(current_file)
        
        return files
    
    def create_files_from_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Create files from code blocks in the response.
        
        Args:
            response: The response text
            
        Returns:
            List of results for created files
        """
        results = []
        extracted_files = self.extract_files_from_response(response)
        
        for file_info in extracted_files:
            file_path = Path(file_info["path"])
            
            # Make sure path is relative to working directory
            if file_path.is_absolute():
                try:
                    file_path = file_path.relative_to(self.cwd)
                except ValueError:
                    # If path cannot be made relative, use just the filename
                    file_path = Path(file_path.name)
            
            # Create absolute path for file creation
            abs_path = self.cwd / file_path
            
            # Ensure parent directory exists
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                # Write file content
                abs_path.write_text(file_info["content"])
                
                console.print(f"[green]Created file:[/green] {file_path}")
                
                results.append({
                    "success": True,
                    "path": str(file_path),
                    "absolutePath": str(abs_path),
                })
                
                # Add system message about file creation
                self.add_message("system", f"Created file: {file_path}")
            except Exception as e:
                console.print(f"[red]Error creating file {file_path}:[/red] {str(e)}")
                
                results.append({
                    "success": False,
                    "path": str(file_path),
                    "error": str(e)
                })
                
                # Add system message about file creation failure
                self.add_message("system", f"Failed to create file {file_path}: {str(e)}")
        
        return results
    
    def run_chat_loop(self):
        """
        Run the main chat loop with enhanced animations.
        """
        try:
            # Display welcome banner with animation
            display_welcome_banner()
            
            # Analyze project (already has its own progress animation)
            console.print(f"[{theme_color('primary')}]Analyzing project...[/{theme_color('primary')}]")
            project_summary = self.analyze_project()
            
            # Generate system prompt
            system_prompt = self.generate_system_prompt(project_summary)
            
            # Load chat history (already has its own progress animation)
            console.print(f"[{theme_color('secondary')}]Loading chat history...[/{theme_color('secondary')}]")
            self.load_or_create_chat()
            
            # Display project information with animation in a panel
            panel = Panel(
                f"Project: {project_summary}",
                title="🚀 Project Information",
                title_align="left",
                border_style=theme_color("success"),
                box=ROUNDED,
                padding=(1, 2)
            )
            console.print(panel)
            
            while True:
                # Display animated input prompt
                display_chat_input_prompt()
                
                # Get user input and display it in a panel
                user_input = self.get_user_input()
                
                # Check for exit commands
                if user_input.lower() in ["exit", "quit"]:
                    fade_in_text(f"[{theme_color('secondary')}]Goodbye! Thanks for using SuperNova![/{theme_color('secondary')}]")
                    break
                
                # Start thinking animation in a separate thread
                thinking_stop_event = threading.Event()
                thinking_thread = threading.Thread(
                    target=self._run_thinking_animation,
                    args=(thinking_stop_event,)
                )
                thinking_thread.daemon = True
                thinking_thread.start()
                
                # Send to LLM with streaming enabled
                response = self.send_to_llm(user_input, stream=True)
                
                # Stop thinking animation
                thinking_stop_event.set()
                if thinking_thread.is_alive():
                    thinking_thread.join()
                
                # Ensure we add a newline after streaming content
                if self._streaming_started:
                    print()  # Add a newline to ensure tool results appear on a new line
                
                # Process the response
                processed_response = self.process_tool_call_loop(response)
                
                # Display the response with animation if not already displayed through streaming
                if processed_response["content"] and not self._streaming_started:
                    display_response(processed_response["content"], role="assistant")
                
                # Handle tool results
                if processed_response["tool_results"]:
                    # Display tool processing animation
                    console.print(f"[{theme_color('highlight')}]🔧 Processing tool results...[/{theme_color('highlight')}]")
                    self.handle_tool_results(processed_response["tool_results"])
                        
        except Exception as e:
            console.print(f"\n[{theme_color('error')}]Error in chat loop:[/{theme_color('error')}] {str(e)}")
    
    def handle_tool_results(self, tool_result: Dict[str, Any]):
        """
        Display tool results with animations.
        
        Args:
            tool_result: The result of a tool call
        """
        if not tool_result:
            return
            
        # Get tool details
        tool_name = tool_result.get("tool_name", "unknown_tool")
        content = tool_result.get("content", "")
        is_error = tool_result.get("error", False)
        
        # Format the content
        formatted_content = f"[bold]{tool_name}[/bold]: {content}"
        
        # Display with appropriate styling based on error status
        if is_error:
            self.console.print(f"[red]{formatted_content}[/red]")
        else:
            # Handle display of content based on tool type
            self.display_response(formatted_content, role="tool")

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
            display_response(user_input, role="user")
        
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
        self.streaming_accumulated_content = ""
        self.streaming_accumulated_tool_calls = {}

    async def read_input(self) -> str:
        """Read user input from the console."""
        # Just use a simple prompt for now
        return input("> ")

    def process_tool_calls(self, tool_calls):
        """
        Process a list of tool calls from the LLM response.
        
        Args:
            tool_calls: List of tool calls to process
            
        Returns:
            List of tool results
        """
        # Create a set to track already processed tool call IDs
        seen_call_ids = set()
        
        # Process each tool call in sequence
        tool_results = []
        
        for tool_call in tool_calls:
            self.logger.debug(f"Processing tool call: {json.dumps(tool_call)}")
            
            # Process the tool call
            tool_result = self.handle_tool_call(tool_call, seen_call_ids)
            
            if tool_result is None:
                self.logger.debug(f"Received None tool result from handle_tool_call for tool_call: {json.dumps(tool_call)}")
                continue
                
            # Standardize the result format for display
            display_result = {
                "tool_call_id": tool_call.get('id', ''),
                "tool_name": tool_result.get("tool_name", "unknown"),
                "success": "error" not in tool_result,
                "error": "error" in tool_result
            }
            
            # Handle result based on success/error
            if "error" in tool_result:
                error_type = tool_result["error"]
                error_message = tool_result.get("message", "Unknown error")
                
                # Skip incomplete tool calls without user-facing errors
                if error_type == "incomplete_tool_call":
                    self.logger.debug(f"Skipping incomplete tool call: {error_message}")
                    continue
                
                # Add error content for display
                display_result["content"] = error_message
                
                # Special handling for unknown tools
                if error_type == "unknown_tool":
                    display_result["content"] = f"Unknown tool '{tool_result.get('tool_name', 'unknown')}'. This tool is not available or may have been mistyped."
            else:
                # Add success content
                display_result["content"] = tool_result.get("result", "")
            
            # Add the result to our list
            tool_results.append(display_result)
            
        return tool_results

    def process_tool_call_loop(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process tool calls in a loop until there are no more tool calls to process.
        Returns the final response after all tool calls have been processed.
        
        Args:
            llm_response: The initial LLM response which may contain tool calls
            
        Returns:
            The final response after all tool calls have been processed
        """
        if not llm_response:
            return llm_response
            
        # Create a copy of the response to work with
        response = copy.deepcopy(llm_response)
        tool_messages = []
        iteration_count = 0
        max_iterations = self.config.chat.max_tool_iterations
        
        # Loop until no more tool calls or we hit maximum iterations
        while 'tool_calls' in response and response['tool_calls'] and iteration_count < max_iterations:
            iteration_count += 1
            self.logger.debug(f"Tool iteration {iteration_count}/{max_iterations}")
            
            # Process all tool calls in this response
            tool_results = self.process_tool_calls(response['tool_calls'])
            
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
                    "tool_name": result["tool_name"],
                    "success": result["success"],
                    "error": result["error"],
                    "result": result["content"]
                })
            
            # If we have tool messages, send them back to LLM
            if tool_messages:
                self.console.print(f"\n[dim][Tool step {iteration_count}/{max_iterations}] Thinking based on tool results...[/dim]")
                
                # Add the tool messages to the conversation
                for tool_message in tool_messages:
                    self.conversation_history.add_message(tool_message)
                
                # Get updated conversation
                conversation = self.conversation_history.get_conversation()
                
                # Get the LLM response
                response = self.llm_provider.get_completion(
                    conversation, 
                    stream=True,
                    model=self.config.chat.model
                )
                
                # Clear tool messages for next iteration
                tool_messages = []
            else:
                # No tool messages, so we're done
                break
            
        # Return the final response
        return response


def start_chat_sync(chat_dir: Optional[Union[str, Path]] = None) -> None:
    """
    Start a synchronous chat session.
    
    Args:
        chat_dir: Optional directory to start the chat in
    """
    # Create a chat session and run it
    chat_session = ChatSession(cwd=chat_dir)
    chat_session.run()
