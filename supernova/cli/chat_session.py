"""
SuperNova - AI-powered development assistant within the terminal.

Chat session for interactive AI assistance.
"""

import json
import os
import re
import subprocess
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple

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

from supernova.config import loader
from supernova.config.schema import SuperNovaConfig
from supernova.core import command_runner, context_analyzer, llm_provider, tool_manager
from supernova.persistence.db_manager import DatabaseManager

console = Console()

# TODO: VS Code Integration - Consider implementing a VSCodeIntegration class that can:
# 1. Detect if running within VS Code
# 2. Access VS Code extensions API if available
# 3. Provide methods to open files, show information, etc.


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
        Analyze the project context.
        
        Returns:
            Summary of the project
        """
        console.print("\n[bold]Analyzing project...[/bold]")
        try:
            project_summary = context_analyzer.analyze_project(self.cwd)
            self.session_state["project_summary"] = project_summary
            console.print(f"[green]Project analyzed:[/green] {project_summary}")
            return project_summary
        except Exception as e:
            error_msg = f"Could not analyze project: {str(e)}"
            self.session_state["project_error"] = error_msg
            console.print(f"[yellow]Warning:[/yellow] {error_msg}")
            return "Unknown project"
    
    def load_or_create_chat(self) -> None:
        """Load the latest chat for the project or create a new one."""
        if not self.db.enabled:
            return
        
        # Get the latest chat for this project
        self.chat_id = self.db.get_latest_chat_for_project(self.cwd)
        
        if self.chat_id:
            # Load existing chat
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
                console.print(f"[green]Loaded previous chat with {len(self.messages)} messages[/green]")
                self.session_state["loaded_previous_chat"] = True
                self.session_state["previous_message_count"] = len(self.messages)
        else:
            # Create a new chat
            self.chat_id = self.db.create_chat(self.cwd)
            console.print("[green]Created new chat session[/green]")
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
    
    def handle_stream_chunk(self, chunk: Dict[str, Any]) -> None:
        """
        Handle a streaming chunk from the LLM.
        
        Args:
            chunk: The chunk data from the streaming response
        """
        try:
            chunk_type = chunk.get("type", "unknown")
            
            if chunk_type == "content":
                # Handle content chunks
                content = chunk.get("content", "")
                full_content = chunk.get("full_content", "")
                
                # Update the latest full content for later use
                self._latest_full_content = full_content
                
                # Print the content without a newline to simulate streaming
                if content:
                    print(content, end="", flush=True)
                    
            elif chunk_type == "tool_calls":
                # Handle tool call chunks
                tool_calls = chunk.get("tool_calls", [])
                
                # Update the latest tool calls for later use
                self._latest_tool_calls = tool_calls
                
                # Print a placeholder for tool calls if this is the first one
                if tool_calls and not self._tool_calls_reported:
                    print("\n[Tool Call]", end="", flush=True)
                    self._tool_calls_reported = True
        
        except Exception as e:
            console.print(f"\n[red]Error handling streaming chunk:[/red] {str(e)}")
    
    def handle_tool_call(self, tool_call: Any) -> Dict[str, Any]:
        """
        Handle a tool call from the LLM.
        
        Args:
            tool_call: The tool call to handle
            
        Returns:
            Tool call result
        """
        try:
            # Extract tool name and arguments based on the format
            tool_name = ""
            tool_args = {}
            
            # Handle different tool call formats
            if hasattr(tool_call, 'function'):
                # Handle OpenAI-style function call format
                function = tool_call.function
                tool_name = getattr(function, 'name', '')
                
                # Parse arguments string to dict if needed
                args_str = getattr(function, 'arguments', '{}')
                if isinstance(args_str, str):
                    try:
                        tool_args = json.loads(args_str)
                    except json.JSONDecodeError:
                        tool_args = {"raw_args": args_str}
                else:
                    tool_args = args_str or {}
            elif isinstance(tool_call, dict):
                # Handle dictionary format
                if 'function' in tool_call:
                    # Handle nested function format
                    function = tool_call.get('function', {})
                    tool_name = function.get('name', '')
                    
                    # Parse arguments
                    args_str = function.get('arguments', '{}')
                    if isinstance(args_str, str):
                        try:
                            tool_args = json.loads(args_str)
                        except json.JSONDecodeError:
                            tool_args = {"raw_args": args_str}
                    else:
                        tool_args = args_str or {}
                else:
                    # Direct format
                    tool_name = tool_call.get('name', '')
                    tool_args = tool_call.get('arguments', {})
            
            # Check if we have a valid tool name
            if not tool_name:
                return {
                    "error": "No tool name provided in tool call"
                }
            
            # Execute the tool
            result = self.tool_manager.execute_tool(
                tool_name=tool_name,
                args=tool_args,
                session_state=self.session_state,
                working_dir=self.cwd
            )
            
            # Update session state
            self.session_state["used_tools"].append({
                "name": tool_name,
                "args": tool_args,
                "result": result
            })
            
            # If this was a terminal command, update the executed commands list
            if tool_name == "terminal_command":
                self.session_state["executed_commands"].append({
                    "command": tool_args.get("command", ""),
                    "result": result
                })
            
            # Update last action result
            self.session_state["LAST_ACTION_RESULT"] = result
            
            return result
        except Exception as e:
            error_msg = f"Error executing tool: {str(e)}"
            console.print(f"[red]{error_msg}[/red]")
            return {"error": error_msg}
    
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
                for tool_call in message.tool_calls:
                    tool_result = self.handle_tool_call(tool_call)
                    processed_response["tool_results"].append(tool_result)
        elif isinstance(response, dict):
            if 'content' in response:
                processed_response["content"] = response['content']
            if 'tool_calls' in response:
                tool_calls = response['tool_calls']
                if tool_calls and self.tool_manager:
                    for tool_call in tool_calls:
                        tool_result = self.handle_tool_call(tool_call)
                        processed_response["tool_results"].append(tool_result)
        
        # Add to message history
        if processed_response["content"]:
            self.add_message("assistant", processed_response["content"])
            
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
        Run the main chat loop.
        """
        try:
            # Analyze project
            project_summary = self.analyze_project()
            
            # Generate system prompt
            system_prompt = self.generate_system_prompt(project_summary)
            
            # Load chat history if available
            self.load_or_create_chat()
            
            # Display welcome message
            console.print("\n[bold cyan]Welcome to SuperNova![/bold cyan]")
            console.print(f"[cyan]Project:[/cyan] {project_summary}")
            console.print("[cyan]Type 'exit' or 'quit' to end the session[/cyan]")
            
            while True:
                # Get user input
                user_input = self.get_user_input()
                
                # Check for exit commands
                if user_input.lower() in ["exit", "quit"]:
                    console.print("\n[cyan]Goodbye![/cyan]")
                    break
                
                # Send to LLM and get response
                response = self.send_to_llm(user_input)
                
                # Process the response
                processed_response = self.process_llm_response(response)
                
                # Display the response
                if processed_response["content"]:
                    self.display_response(processed_response["content"])
                
                # Handle tool results
                if processed_response["tool_results"]:
                    self.handle_tool_results(processed_response["tool_results"])
                    
        except Exception as e:
            console.print(f"\n[red]Error in chat loop:[/red] {str(e)}")
    
    def handle_tool_results(self, tool_results: List[Dict[str, Any]]):
        """
        Handle the results of tool calls.
        
        Args:
            tool_results: List of tool call results
        """
        for result in tool_results:
            # Display the result
            self.display_tool_result(result)
            
            # Update session state
            if "error" in result:
                self.session_state["LAST_ACTION_RESULT"] = f"Error: {result['error']}"
            else:
                self.session_state["LAST_ACTION_RESULT"] = result
    
    def get_user_input(self) -> str:
        """
        Read input from the user.
        
        Returns:
            User input string
        """
        try:
            # Get input from prompt session
            user_input = self.prompt_session.prompt("You: ")
            
            # Add to message history
            self.add_message("user", user_input)
            
            return user_input
        except KeyboardInterrupt:
            return "exit"
        except Exception as e:
            console.print(f"[red]Error reading input:[/red] {str(e)}")
            console.print(f"[red]Error getting user input:[/red] {str(e)}")
            return "exit"
        
    def run(self):
        """
        Run the chat session.
        """
        try:
            # Run the chat loop
            self.run_chat_loop()
        except KeyboardInterrupt:
            console.print("\n[cyan]Interrupted by user. Exiting SuperNova.[/cyan]")
        except Exception as e:
            console.print(f"\n[red]Error running chat session:[/red] {str(e)}")
    
    def _reset_streaming_state(self) -> None:
        """Reset the streaming state for a new streaming session."""
        self._latest_full_content = ""
        self._latest_tool_calls = []
        self._tool_calls_reported = False

    async def read_input(self) -> str:
        """Read user input from the console."""
        # Just use a simple prompt for now
        return input("> ")

    def display_tool_result(self, tool_result: Dict[str, Any]) -> None:
        """
        Display a tool result.
        
        Args:
            tool_result: The tool result to display
        """
        if "error" in tool_result:
            console.print(f"\n[red]Error:[/red] {tool_result['error']}")
        else:
            console.print("\n[bold green]Tool Result:[/bold green]")
            console.print(tool_result)
    
    def process_tool_call_loop(self, initial_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process tool calls in a loop until no more tool calls are needed.
        
        Args:
            initial_response: The initial response from the LLM
            
        Returns:
            Final processed response
        """
        # Initialize with the initial response
        current_response = self.process_llm_response(initial_response)
        
        # Get max iterations from config
        max_iterations = self.config.chat.max_tool_iterations
        current_iteration = 0
        
        # Loop until no more tool calls or max iterations
        while current_response["tool_results"] and current_iteration < max_iterations:
            # Increment iteration counter
            current_iteration += 1
            
            # Display intermediate results if there's content
            if current_response["content"]:
                console.print(f"\n[dim][Tool step {current_iteration}/{max_iterations}] Assistant's intermediate thoughts:[/dim]")
                console.print(f"[dim]{current_response['content']}[/dim]")
            
            # Process tool results
            self.handle_tool_results(current_response["tool_results"])
            
            # If we've reached max iterations, break with a warning
            if current_iteration >= max_iterations and current_response["tool_results"]:
                console.print(f"\n[yellow]Reached maximum tool call iterations ({max_iterations}). Stopping tool execution loop.[/yellow]")
                break
            
            # Continue the conversation with the LLM
            try:
                console.print(f"\n[dim][Tool step {current_iteration}/{max_iterations}] Thinking based on tool results...[/dim]")
                
                # Get updated context
                context_update = self.get_context_message()
                
                # Create a prompt for the next iteration
                next_prompt = (
                    f"TOOL EXECUTION RESULTS:\n{current_response['tool_results']}\n\n"
                    f"CURRENT CONTEXT:\n{context_update}\n\n"
                    f"Based on the above information, please decide your next action."
                )
                
                # Send a message to the LLM to process the tool results
                next_response = self.send_to_llm(next_prompt)
                
                # Process the response and continue the loop if needed
                current_response = self.process_llm_response(next_response)
            except Exception as e:
                console.print(f"[red]Error processing tool result:[/red] {str(e)}")
                break
        
        # Return the final processed response
        return current_response


def start_chat_sync(chat_dir: Optional[Union[str, Path]] = None) -> None:
    """
    Start a synchronous chat session.
    
    Args:
        chat_dir: Optional directory to start the chat in
    """
    # Create a chat session and run it
    chat_session = ChatSession(cwd=chat_dir)
    chat_session.run()
    