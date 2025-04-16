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
            }
        }
        
        # TODO: VS Code Integration - Check if running in VS Code and initialize integration
        # if is_vscode_environment():
        #     self.vscode = VSCodeIntegration()
        #     self.session_state["editor"] = "vscode"
        
        # Initialize session with history in the local .supernova directory
        history_file = self.cwd / ".supernova" / "prompt_history"
        self.prompt_session = PromptSession(history=FileHistory(str(history_file)))
    
    async def analyze_project(self) -> str:
        """
        Analyze the project context.
        
        Returns:
            Summary of the project
        """
        console.print("\n[bold]Analyzing project...[/bold]")
        try:
            project_summary = await context_analyzer.analyze_project(self.cwd)
            self.session_state["project_summary"] = project_summary
            console.print(f"[green]Project analyzed:[/green] {project_summary}")
            return project_summary
        except Exception as e:
            error_msg = f"Could not analyze project: {str(e)}"
            self.session_state["project_error"] = error_msg
            console.print(f"[yellow]Warning:[/yellow] {error_msg}")
            return "Unknown project"
    
    async def load_or_create_chat(self) -> None:
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
    
    async def format_messages_for_llm(
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
            tools = await self.tool_manager.get_available_tools_for_llm(self.session_state)
            tool_choice = "auto"  # Let the model decide when to use tools
        
        return llm_messages, tools, tool_choice
    
    async def get_available_tools_info(self) -> str:
        """
        Get information about available tools.
        
        Returns:
            String description of available tools
        """
        try:
            tool_info = await self.tool_manager.get_tool_info_async()
            
            if not tool_info:
                return "No tools available."
            
            tool_descriptions = []
            for info in tool_info:
                try:
                    tool_name = info.get("name", "Unknown tool")
                    description = info.get("description", "No description available")
                    usage_examples = info.get("usage_examples", [])
                    required_args = info.get("required_args", {})
                    
                    # Format usage examples
                    examples_str = ""
                    if usage_examples:
                        examples_str = "\nExamples:\n" + "\n".join([f"- {ex}" for ex in usage_examples[:2]])
                    
                    # Format required args - handle both Dict and List formats
                    args_str = ""
                    if required_args:
                        if isinstance(required_args, dict):
                            # Handle Dict[str, str] format (key: description)
                            args_str = "\nRequired arguments:\n" + "\n".join([f"- {k}: {v}" for k, v in required_args.items()])
                        elif isinstance(required_args, list):
                            # Handle List[str] format (list of argument names)
                            args_str = "\nRequired arguments:\n" + "\n".join([f"- {arg}" for arg in required_args])
                    
                    tool_descriptions.append(
                        f"- {tool_name}: {description}{examples_str}{args_str}"
                    )
                except Exception as e:
                    console.print(f"[yellow]Warning: Error processing tool info: {str(e)}[/yellow]")
                    
            return "\n".join(tool_descriptions)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not get tool info: {str(e)}[/yellow]")
            return "Could not retrieve tool information."
    
    async def get_session_state_summary(self) -> str:
        """
        Get a summary of the current session state.
        
        Returns:
            String summary of session state
        """
        try:
            # Extract key information from session state
            summary_parts = [
                f"Working directory: {self.session_state.get('cwd', 'Unknown')}",
                f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            ]
            
            # Add information about executed commands if any
            executed_commands = self.session_state.get("executed_commands", [])
            if executed_commands:
                # Show last 3 commands
                recent_commands = executed_commands[-3:]
                try:
                    cmd_summary = "\n".join([f"- `{cmd.get('command', 'Unknown command')}`" for cmd in recent_commands])
                    summary_parts.append(f"Recently executed commands:\n{cmd_summary}")
                except Exception as e:
                    console.print(f"[yellow]Warning: Error formatting executed commands: {str(e)}[/yellow]")
            
            # Add information about used tools if any
            used_tools = self.session_state.get("used_tools", [])
            if used_tools:
                # Show last 3 tool calls
                recent_tools = used_tools[-3:]
                try:
                    tool_summary = "\n".join([
                        f"- Tool: `{tool.get('name', 'Unknown')}` with args: {json.dumps(tool.get('args', {}))}" 
                        for tool in recent_tools
                    ])
                    summary_parts.append(f"Recently used tools:\n{tool_summary}")
                except Exception as e:
                    console.print(f"[yellow]Warning: Error formatting used tools: {str(e)}[/yellow]")
            
            return "\n".join(summary_parts)
        except Exception as e:
            console.print(f"[yellow]Warning: Error generating session state summary: {str(e)}[/yellow]")
            return "Error generating session state summary"
    
    async def generate_system_prompt(self, project_summary: str = "") -> str:
        """
        Generate the system prompt.
        
        Args:
            project_summary: Summary of the project
            
        Returns:
            System prompt for the LLM
        """
        tools_info = await self.get_available_tools_info()
        session_state = await self.get_session_state_summary()
        
        # If no project summary provided, use the one from session state
        if not project_summary:
            project_summary = self.session_state.get("project_summary", "Unknown project")
        
        # Get the initial directory information
        initial_directory = self.session_state.get("initial_directory", str(self.initial_directory))
        
        prompt_template = r"""
# Persona and Goal
You are SuperNova, an expert AI developer assistant operating in a CLI environment. Your primary goal is to help the user achieve their development tasks by breaking them down into logical, executable steps.

# Context
You are working within a project summarized as: {project_summary}.
You are restricted to operating within the initial directory: {initial_directory}
All file operations and directory changes must remain within this directory.

Keep track of the ongoing conversation and state:
{session_state} # Includes recent messages and crucially: LAST_ACTION_RESULT=... (Result of the last executed command or tool)

# IMPORTANT: Available Tools
You have access to these tools:
{tools_info}

# Directory Restriction
IMPORTANT: You cannot navigate or access files outside of the initial directory: {initial_directory}
All commands that would lead outside this directory will be prevented, and you should avoid suggesting such actions.
If you need to work with files or directories, make sure they're contained within this initial directory.

# Tool Call Loop Capability
You now have the ability to use multiple tools in sequence without waiting for user input between steps. This means:
1. You can call a tool
2. Receive the result of that tool call
3. Based on that result, call another tool
4. Continue this loop until the task is complete
5. Then provide a final summary to the user

This is particularly useful for multi-step tasks that require:
- Gathering information from multiple sources
- Processing that information to make decisions
- Taking actions based on those decisions

The system will automatically handle the tool call loop, executing each tool and providing you with the results. You can then decide whether to use another tool or provide a final response to the user.

# Core Task: Planning and Execution
1. **Analyze:** Understand the user's request based on the current context and session state.
2. **Plan:** Break down the request into a sequence of precise steps. Think step-by-step.
3. **Act:** For each step, determine the appropriate tool to use.
4. **Process Results:** Analyze the results of each tool call to determine next steps.
5. **Complete:** Provide a final response to the user once all necessary tool calls are complete.

# CRITICAL: Tool Usage Guidelines
You are connected to a function calling API that allows you to use tools directly through the API. This means:

1. DO NOT manually format tool calls in your response content
2. DO NOT include code blocks with tool calls
3. DO NOT mention "I'll use the X tool" in your response
4. DO NOT use any specific output format for tools

Instead, when you want to use a tool:
1. Simply DECIDE which tool is best for the task
2. The API will AUTOMATICALLY detect your intent and execute it
3. You will receive the tool's result and can decide on further actions
4. Focus on understanding the user's request and responding accurately

# Response Guidelines
* **Be Concise:** Give direct, clear, and to-the-point responses.
* **Be Natural:** For simple queries like greetings, respond naturally as a helpful assistant would.
* **Use Tools Appropriately:** Choose the right tool for each step of the task.
* **Multi-Step Thinking:** Break complex tasks into sequences of tool calls.
* **Focus on Results:** Prioritize helping the user achieve their goal efficiently.
* **Statefulness:** Pay close attention to tool results to inform your next actions.
* **Problem Solving:** If a tool fails, analyze the result and propose corrective actions.
* **Directory Awareness:** Always respect the initial directory constraint and work within it.

Remember: The system is built to handle tool calling automatically through the API's function calling mechanism. You do not need to format tool calls in any specific way - just decide which tool to use when appropriate.
"""
        
        return prompt_template.format(
            project_summary=project_summary, 
            session_state=session_state, 
            tools_info=tools_info,
            initial_directory=initial_directory
        )
    
    async def get_context_message(self) -> str:
        """
        Get a context message with session state information.
        
        Returns:
            Context message string
        """
        # Create context message with project information
        context_parts = []
        
        # Add working directory (prioritize getting it from the session state)
        cwd = self.session_state.get("cwd", str(self.cwd))
        initial_dir = self.session_state.get("initial_directory", str(self.initial_directory))
        context_parts.append(f"Current working directory: {cwd}")
        context_parts.append(f"Initial directory (restricted to): {initial_dir}")
        
        # Add path history if available (last 5 paths)
        path_history = self.session_state.get("path_history", [])
        if len(path_history) > 1:  # Only show if we have more than the initial path
            # Format path history nicely with arrows
            history_str = " → ".join([Path(p).name for p in path_history[-5:]])
            context_parts.append(f"Recent path history: {history_str}")
        
        # Add git information if available
        git_info = self.session_state.get("git_info", {})
        if git_info:
            branch = git_info.get("branch", "unknown")
            context_parts.append(f"Git branch: {branch}")
            
            # Add recent commits if available
            commits = git_info.get("recent_commits", [])
            if commits:
                commit_info = "\n".join([f"- {c.get('message', '')} ({c.get('hash', '')})" for c in commits[:3]])
                context_parts.append(f"Recent commits:\n{commit_info}")
        
        # Add recent commands from session state
        commands = self.session_state.get("executed_commands", [])
        if commands:
            # Show last 5 commands (increased from 3)
            recent_cmds = [f"- `{cmd['command']}`" for cmd in commands[-5:]]
            context_parts.append("Recently executed commands:\n" + "\n".join(recent_cmds))
        
        # Add last action result if available
        last_action_result = self.session_state.get("LAST_ACTION_RESULT")
        if last_action_result:
            context_parts.append(f"Last action result: {last_action_result}")
        
        # Add tools information
        tools_list = await self.tool_manager.list_tools_async()
        if tools_list:
            tool_names = [f"`{tool.get_name()}`" for tool in tools_list]
            context_parts.append("Available tools: " + ", ".join(tool_names))
        
        return "\n\n".join(context_parts)
    
    async def send_to_llm(self, content: str, debug_mode: bool = False, stream: bool = False) -> Dict[str, Any]:
        """
        Send a message to the LLM and get a response.
        
        Args:
            content: The user message content
            debug_mode: Whether to output debug information
            stream: Whether to stream the response
            
        Returns:
            LLM response
        """
        # Get system prompt
        system_prompt = await self.generate_system_prompt()
        
        # Get context message
        context_msg = await self.get_context_message()
        
        # Get session history
        previous_messages = [msg for msg in self.messages 
                            if msg["role"] in ["user", "assistant"]]
        
        # Format messages for the LLM
        include_tools = bool(self.tool_manager)
        llm_messages, tools, tool_choice = await self.format_messages_for_llm(
            content=content,
            system_prompt=system_prompt,
            context_msg=context_msg,
            previous_messages=previous_messages,
            include_tools=include_tools
        )
        
        # Add to history
        self.add_message("user", content)
        
        # If it's a simple greeting, no need for tools
        simple_greetings = ["hello", "hi", "hey", "greetings", "what's up", "howdy"]
        is_greeting = content.lower().strip().split()[0] in simple_greetings if content.strip() else False
        
        # For simple greetings, we'll skip tools to get a faster response
        if is_greeting:
            tools = None
            tool_choice = None
        
        # Output debug info if requested
        if debug_mode:
            console.print(f"Tools for LLM: {len(tools) if tools else 0} tools available")
            if tool_choice:
                console.print(f"Tool choice: {tool_choice}")
            console.print(f"Sending messages to LLM...")
            console.print(f"Message count: {len(llm_messages)}")
            if tools:
                console.print(f"Tools: {len(tools)} tools available")
            if stream:
                console.print("Streaming mode enabled")
        
        # Set up streaming callback if needed
        stream_callback = None
        if stream:
            self._reset_streaming_state()
            stream_callback = self.handle_stream_chunk
            console.print("\n[Assistant]: ", end="")
        
        # Try to send to the LLM
        try:
            # Get completion from the LLM - this is an async call
            response = await self.llm_provider.get_completion(
                messages=llm_messages,
                tools=tools,
                tool_choice=tool_choice,
                stream=stream,
                stream_callback=stream_callback
            )
            
            # If streaming, we need to wait for it to complete
            if stream:
                # The response is the final response after streaming completes
                pass
            
            # Update session state
            if isinstance(response, str):
                self.add_message("assistant", response)
            elif hasattr(response, 'choices') and hasattr(response.choices[0], 'message'):
                message = response.choices[0].message
                content = getattr(message, 'content', "")
                if content:
                    self.add_message("assistant", content)
            elif isinstance(response, dict) and 'content' in response:
                self.add_message("assistant", response['content'])
            
            return response
            
        except Exception as e:
            error_msg = f"Error communicating with LLM: {str(e)}"
            console.print(f"[red]{error_msg}[/red]")
            
            # Return a simple error message
            if stream:
                # End the streaming output with a newline
                console.print("")
            
            return {"content": error_msg}
        
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
    
    async def handle_tool_call(self, tool_call: Any) -> Dict[str, Any]:
        """
        Handle a tool call from the LLM using LiteLLM's tool calling format.
        
        Args:
            tool_call: The tool call information from the LLM
            
        Returns:
            The result of executing the tool
        """
        try:
            # Extract tool name and arguments based on the tool_call format from LiteLLM
            if not hasattr(tool_call, 'function') and not isinstance(tool_call, dict):
                return {
                    "name": "unknown",
                    "success": False,
                    "result": f"Error: Unsupported tool call format: {tool_call}"
                }
            
            # Extract function name and arguments
            if isinstance(tool_call, dict):
                # Handle dict format
                function = tool_call.get('function', {})
                tool_name = function.get('name', '')
                arguments_str = function.get('arguments', '{}')
            else:
                # Handle object format from LiteLLM
                function = tool_call.function
                tool_name = getattr(function, 'name', '')
                arguments_str = getattr(function, 'arguments', '{}')
            
            # Parse arguments
            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                return {
                    "name": tool_name,
                    "success": False,
                    "result": f"Error: Invalid JSON in arguments: {arguments_str}"
                }
            
            # Execute the tool using the tool manager
            if not self.tool_manager:
                return {
                    "name": tool_name,
                    "success": False,
                    "result": "Error: Tool manager not available"
                }
            
            # Log the tool call
            console.print(f"\n[bold cyan]Tool Call:[/bold cyan] {tool_name}")
            console.print(f"Arguments: {arguments}")
            
            # Execute the tool and get the result
            result = await self.tool_manager.execute_tool(
                tool_name, 
                arguments, 
                session_state=self.session_state
            )
            
            # Add to session state
            self.session_state["used_tools"].append({
                "name": tool_name,
                "args": arguments,
                "timestamp": int(time.time()),
                "success": True
            })
            
            # Add to session state's LAST_ACTION_RESULT
            self.session_state["LAST_ACTION_RESULT"] = f"Tool {tool_name} executed with result: {result}"
            
            # Update tool result format to match what the rest of the code expects
            return {
                "name": tool_name,
                "success": True,
                "result": result
            }
            
        except Exception as e:
            console.print(f"[red]Error handling tool call:[/red] {str(e)}")
            
            # In error case, attempt to extract the tool name from the tool_call more reliably
            tool_name = "unknown"
            try:
                if isinstance(tool_call, dict):
                    # Handle dict format
                    function = tool_call.get('function', {})
                    tool_name = function.get('name', 'unknown')
                elif hasattr(tool_call, 'function'):
                    # Handle object format from LiteLLM
                    function = tool_call.function
                    tool_name = getattr(function, 'name', 'unknown')
            except Exception:
                # If any error occurs in extracting tool name, fallback to unknown
                tool_name = "unknown"
                
            return {
                "name": tool_name,
                "success": False,
                "result": f"Error executing tool: {str(e)}"
            }
    
    async def process_llm_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the response from the LLM, handling tool calls if present.
        
        Args:
            response: The raw response from the LLM
            
        Returns:
            Processed response with content and any tool results
        """
        # Initialize results
        processed_response = {
            "content": "",
            "tool_results": []
        }
        
        try:
            # Check if it's a coroutine (should be awaited)
            if asyncio.iscoroutine(response):
                response = await response
                
            # Check if it's a string response
            if isinstance(response, str):
                # Sanitize the content to ensure no raw function calls
                if hasattr(self.llm_provider, '_sanitize_response_content'):
                    processed_response["content"] = self.llm_provider._sanitize_response_content(response)
                else:
                    processed_response["content"] = response
                return processed_response
            
            # Handle LiteLLM's response format (object with choices)
            if hasattr(response, 'choices') and hasattr(response.choices[0], 'message'):
                message = response.choices[0].message
                content = getattr(message, 'content', None)
                
                # Sanitize the content if present
                if content and hasattr(self.llm_provider, '_sanitize_response_content'):
                    content = self.llm_provider._sanitize_response_content(content)
                    
                processed_response["content"] = content if content is not None else "No content provided"
                
                # Process tool calls if present using LiteLLM's format
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        tool_result = await self.handle_tool_call(tool_call)
                        processed_response["tool_results"].append(tool_result)
                return processed_response
            
            # Handle dict format (e.g., from our own implementation)
            if isinstance(response, dict):
                content = response.get("content")
                
                # Sanitize the content if present
                if content and hasattr(self.llm_provider, '_sanitize_response_content'):
                    content = self.llm_provider._sanitize_response_content(content)
                    
                processed_response["content"] = content if content is not None else "No content provided"
                
                # Process tool calls if present in our custom format
                tool_calls = response.get("tool_calls", [])
                
                # Process each tool call if present
                if tool_calls and self.tool_manager:
                    for tool_call in tool_calls:
                        tool_result = await self.handle_tool_call(tool_call)
                        processed_response["tool_results"].append(tool_result)
                        
                return processed_response
            
            # Fallback: just convert the response to string
            response_str = str(response)
            if hasattr(self.llm_provider, '_sanitize_response_content'):
                processed_response["content"] = self.llm_provider._sanitize_response_content(response_str)
            else:
                processed_response["content"] = response_str
            return processed_response
            
        except Exception as e:
            console.print(f"[red]Error processing LLM response:[/red] {str(e)}")
            processed_response["content"] = "Error processing LLM response"
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
                                    tool_context,
                                    self.cwd
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
                                        f"Tool executed: {tool_name}\nResult: {limited_result}"
                                    )
                                else:
                                    console.print(f"[red]Tool execution failed:[/red] {result.get('error', 'Unknown error')}")
                                    
                                    # Add system message
                                    self.add_message(
                                        "system",
                                        f"Tool failed: {tool_name}\nError: {result.get('error', 'Unknown error')}"
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
            
            # Update LAST_ACTION_RESULT in session state
            self.session_state["LAST_ACTION_RESULT"] = f"Command {command} executed with exit code {exit_code}. Output: {stdout}"
            
            # Display result
            if exit_code == 0:
                console.print("[green]Command executed successfully[/green]")
                if stdout:
                    console.print(Panel(stdout, title="Command Output", expand=False))
                
                # Limit stdout for LLM context only
                limited_stdout = stdout
                if stdout and "\n" in stdout:
                    lines = stdout.splitlines()
                    line_limit = self.config.chat.tool_result_line_limit
                    if len(lines) > line_limit:
                        # Keep only the last N lines
                        truncated_lines = lines[-line_limit:]
                        limited_stdout = f"[Output truncated to last {line_limit} lines]\n" + "\n".join(truncated_lines)
                
                # Add system message with limited content for LLM
                self.add_message("system", f"Command executed successfully: `{command}`\n\nOutput:\n```\n{limited_stdout}\n```")
            else:
                console.print(f"[red]Command failed with exit code {exit_code}[/red]")
                if stderr:
                    console.print(Panel(stderr, title="Error Output", expand=False))
                if stdout:
                    console.print(Panel(stdout, title="Command Output", expand=False))
                
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
                
                # Add system message with limited content for LLM
                self.add_message(
                    "system", 
                    f"Command failed with exit code {exit_code}: `{command}`\n\nError:\n```\n{limited_stderr}\n```\n\nOutput:\n```\n{limited_stdout}\n```"
                )
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
    
    async def run_chat_loop(self):
        """Run the interactive chat loop with the user."""
        # Initialize chat state
        try:
            # Analyze project
            project_summary = await self.analyze_project()
            
            # Generate system prompt
            system_prompt = await self.generate_system_prompt(project_summary)
            
            # Load chat history if available
            await self.load_or_create_chat()
            
            # Display welcome message
            console.print("[bold]Welcome to SuperNova, your AI-powered developer assistant.[/bold]")
            console.print("Start chatting with me about your project, or type 'exit' to quit.")
            
            # Get welcome prompt from config
            welcome_prompt = self.config.chat.welcome_prompt
            
            # If welcome prompt is set, create a "welcome" message from the assistant
            if welcome_prompt:
                try:
                    console.print("\nGenerating welcome message...")
                    
                    # Determine if streaming should be used
                    use_streaming = self.config.chat.streaming and hasattr(self.llm_provider, 'stream_completion')
                    
                    # Send the welcome prompt to the LLM
                    response = await self.send_to_llm(
                        welcome_prompt,
                        stream=use_streaming
                    )
                    
                    # Process the response using the tool call loop
                    processed = await self.process_tool_call_loop(response)
                    
                    # Display the response if not streaming
                    if not use_streaming:
                        self.display_response(processed["content"])
                    
                except Exception as e:
                    console.print(f"[red]Error generating welcome message:[/red] {str(e)}")
                    console.print_exception()
        except Exception as e:
            console.print(f"[red]Error in chat initialization:[/red] {str(e)}")
            console.print_exception()
            return
        
        # Main chat loop
        while True:
            try:
                # Read user input
                user_input = await self.read_input()
                
                # Check for exit command
                if user_input.lower() in ["exit", "quit"]:
                    console.print("\nExiting chat. Goodbye!")
                    return
                    
                # Check for special commands
                if user_input.lower() == '/help':
                    console.print("\n[bold]Available Commands:[/bold]")
                    console.print("  /help - Display this help message")
                    console.print("  /add_tool_model <model_id> - Add a model to the list of known tool-capable models")
                    console.print("  exit or quit - Exit the chat session")
                    continue
                elif user_input.startswith('/add_tool_model '):
                    # Extract the model identifier
                    model_id = user_input.replace('/add_tool_model ', '').strip()
                    if model_id:
                        self.add_tool_capable_model(model_id)
                        continue
                    else:
                        console.print("[yellow]Usage: /add_tool_model <model_identifier>[/yellow]")
                        console.print("[yellow]Example: /add_tool_model gemma-3[/yellow]")
                        continue
                
                # Show that we're thinking
                console.print("Thinking...")
                
                # Clean up the streaming state
                self._reset_streaming_state()
                
                # Determine if streaming should be used
                use_streaming = self.config.chat.streaming and hasattr(self.llm_provider, 'stream_completion')
                
                try:
                    # Get initial response from LLM
                    response = await self.send_to_llm(
                        user_input, 
                        stream=use_streaming
                    )
                    
                    # Process the response using the tool call loop
                    processed = await self.process_tool_call_loop(response)
                    
                    # Display the final response if not streaming
                    if not use_streaming:
                        console.print("\n[Assistant]: " + processed["content"])
                        
                except Exception as e:
                    console.print(f"\n[red]Error:[/red] {str(e)}")
                    if self.config.debugging.show_traceback:
                        console.print_exception()
            except KeyboardInterrupt:
                console.print("\n[blue]Interrupted by user. Exiting SuperNova.[/blue]")
                break
            except Exception as e:
                console.print(f"[red]Error during chat:[/red] {str(e)}")
                console.print(f"Error details: {str(e)}")
                if hasattr(self, 'logger'):
                    self.logger.error(f"Error during chat: {str(e)}", exc_info=True)
    
    async def handle_tool_results(self, tool_results: List[Dict[str, Any]]):
        """
        Handle the results of tool executions.
        
        Args:
            tool_results: The list of tool execution results
        """
        for result in tool_results:
            tool_name = result.get("name", "Unknown tool")
            success = result.get("success", False)
            tool_result = result.get("result", "")
            
            if success:
                console.print(f"[bold green]Tool {tool_name} executed successfully:[/bold green]")
                console.print(tool_result)
            else:
                console.print(f"[bold red]Tool {tool_name} execution failed:[/bold red]")
                console.print(tool_result)
            
            # Limit the tool result content for LLM context only (not for display)
            limited_result = tool_result
            if tool_result and "\n" in tool_result:
                lines = tool_result.splitlines()
                line_limit = self.config.chat.tool_result_line_limit
                if len(lines) > line_limit:
                    # Keep only the last N lines
                    truncated_lines = lines[-line_limit:]
                    limited_result = f"[Output truncated to last {line_limit} lines]\n" + "\n".join(truncated_lines)
            
            # Add the tool result to the context for future messages (with limited content for LLM)
            self.add_message(
                "system", 
                f"Tool execution result for {tool_name}: {limited_result}"
            )
            
            # Update LAST_ACTION_RESULT in session state
            self.session_state["LAST_ACTION_RESULT"] = f"Tool {tool_name} execution result: {tool_result}"
    
    async def get_user_input(self) -> str:
        """
        Get input from the user.
        
        Returns:
            The user input
        """
        # Create a simple prompt
        prompt = "\n> "
        
        # Get user input (consider using prompt_toolkit for better UX)
        user_input = input(prompt)
        
        return user_input
        
    async def run(self):
        """Run the chat session asynchronously."""
        try:
            await self.run_chat_loop()
        except Exception as e:
            console.print(f"[red]Error running chat session:[/red] {str(e)}")
            console.print(f"[yellow]Error type:[/yellow] {type(e).__name__}")
            console.print(f"[yellow]Error details:[/yellow] {repr(e)}")
            if hasattr(self, 'config') and self.config.debugging.show_traceback:
                console.print_exception()

    def _reset_streaming_state(self) -> None:
        """Reset the streaming state for a new streaming session."""
        self._latest_full_content = ""
        self._latest_tool_calls = []
        self._tool_calls_reported = False

    async def read_input(self) -> str:
        """Read user input from the console."""
        # Just use a simple prompt for now
        return input("> ")

    async def display_tool_result(self, tool_result: Dict[str, Any]) -> None:
        """Display the result of a tool execution."""
        if not tool_result:
            return
            
        name = tool_result.get("name", "Unknown Tool")
        success = tool_result.get("success", False)
        result = tool_result.get("result", "No result")
        
        if success:
            console.print(f"\n[bold green]Tool {name} executed successfully[/bold green]")
            console.print(f"{result}")
        else:
            console.print(f"\n[bold red]Tool {name} failed[/bold red]")
            console.print(f"Error: {result}")
            
    def add_tool_capable_model(self, model_identifier: str) -> None:
        """
        Add a model to the list of known tool-capable models.
        
        Args:
            model_identifier: A string that identifies the model (e.g., "gemma-3")
        """
        if hasattr(self.llm_provider, 'add_tool_capable_model'):
            self.llm_provider.add_tool_capable_model(model_identifier)
            
            # Also reload or reinitialize the LLM provider to apply the changes
            current_provider = self.llm_provider.provider_name
            self.llm_provider = llm_provider.get_provider(current_provider)
            
            console.print(f"[green]LLM provider reinitialized with updated tool-capable models list[/green]")
        else:
            console.print("[red]Error: LLM provider doesn't support adding tool-capable models[/red]")

    async def process_tool_call_loop(self, initial_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process tool calls in a continuous loop until no more tool calls are returned
        or the maximum number of iterations is reached.
        
        Args:
            initial_response: The initial response from the LLM
            
        Returns:
            The final processed response after all tool calls are handled
        """
        # Initialize with the initial response
        current_response = await self.process_llm_response(initial_response)
        
        # Get max iterations from config
        max_iterations = self.config.chat.max_tool_iterations
        current_iteration = 0
        
        # Get or initialize failed commands tracking in session state
        if "failed_commands" not in self.session_state:
            self.session_state["failed_commands"] = []
        failed_commands = self.session_state["failed_commands"]
        
        # Loop until no more tool calls or max iterations
        while current_response["tool_results"] and current_iteration < max_iterations:
            # Increment iteration counter
            current_iteration += 1
            
            # Display intermediate results if there's content
            if current_response["content"]:
                console.print(f"\n[dim][Tool step {current_iteration}/{max_iterations}] Assistant's intermediate thoughts:[/dim]")
                console.print(f"[dim]{current_response['content']}[/dim]")
            
            # Process tool results and show them to the user
            for tool_result in current_response["tool_results"]:
                await self.display_tool_result(tool_result)
                
                # Track failed commands to prevent loops
                tool_name = tool_result.get("name", "Unknown tool")
                tool_success = tool_result.get("success", False)
                
                # If a command failed, add it to our tracking list
                if not tool_success:
                    # Get the proper data structure for this tool 
                    # For terminal commands, we need to extract the command from the result string since args isn't passed
                    args = {}
                    result_str = tool_result.get("result", "")
                    
                    if tool_name == "terminal_command":
                        # Try to extract the command from the result string
                        command_match = re.search(r"Command:\s*`(.*?)`", result_str)
                        if command_match:
                            args = {"command": command_match.group(1)}
                    
                    console.print(f"[yellow]Adding failed command to tracking list to prevent repetition: {tool_name}[/yellow]")
                    failed_cmd = {
                        "tool": tool_name,
                        "args": args,
                        "result": result_str,
                        "iteration": current_iteration,
                        "timestamp": int(time.time())
                    }
                    failed_commands.append(failed_cmd)
                    
                    # Update session state
                    self.session_state["failed_commands"] = failed_commands
                
                # Add the tool result to the context for the next iteration
                tool_result_content = tool_result.get("result", "")
                
                # Limit the tool result content for LLM context only (not for display)
                limited_content = tool_result_content
                if tool_result_content and "\n" in tool_result_content:
                    lines = tool_result_content.splitlines()
                    line_limit = self.config.chat.tool_result_line_limit
                    if len(lines) > line_limit:
                        # Keep only the last N lines
                        truncated_lines = lines[-line_limit:]
                        limited_content = f"[Output truncated to last {line_limit} lines]\n" + "\n".join(truncated_lines)
                
                # Add as system message for context (with limited content for LLM)
                self.add_message(
                    "system",
                    f"Tool execution result for {tool_name}: {limited_content}"
                )
            
            # Check for command repetition pattern
            if current_iteration >= 3 and len(failed_commands) >= 2:
                # Check the last 2 failed commands
                last_cmd = failed_commands[-1] if failed_commands else None
                prev_cmd = failed_commands[-2] if len(failed_commands) >= 2 else None
                
                if last_cmd and prev_cmd and last_cmd.get("tool") == prev_cmd.get("tool"):
                    # Check for exact command repetition
                    if last_cmd.get("tool") == "terminal_command":
                        last_command = last_cmd.get("args", {}).get("command", "")
                        prev_command = prev_cmd.get("args", {}).get("command", "")
                        
                        if last_command == prev_command:
                            console.print(f"[bold red]Detected command repetition pattern: '{last_command}'[/bold red]")
                            console.print("[yellow]Forcing exit from tool loop to prevent infinite repetition[/yellow]")
                            
                            # Add a system message to inform the LLM about the repetition
                            self.add_message(
                                "system",
                                f"CRITICAL: You are repeating the same exact command '{last_command}' multiple times "
                                f"despite it failing. This command will NOT work. "
                                f"You must try a completely different approach."
                            )
                            
                            # Create a final response without tool calls and break out of the loop
                            break_response = await self.send_to_llm(
                                f"You've been repeating the command '{last_command}' which failed multiple times. "
                                f"This approach is not working. Please provide a different solution or explain what's happening.",
                                stream=False
                            )
                            
                            # Process the response (without entering the loop again)
                            final_processed = await self.process_llm_response(break_response)
                            
                            # Update the content but don't process any more tool calls
                            current_response["content"] = final_processed["content"]
                            current_response["tool_results"] = []
                            
                            # Exit the loop
                            break
            
            # If we've reached max iterations, break with a warning
            if current_iteration >= max_iterations and current_response["tool_results"]:
                console.print(f"\n[yellow]Reached maximum tool call iterations ({max_iterations}). Stopping tool execution loop.[/yellow]")
                
                # Add a system message to inform the LLM about hitting the limit
                self.add_message(
                    "system",
                    f"Maximum tool call iterations ({max_iterations}) reached. Please provide a final response."
                )
                
                # Get a final response from the LLM
                try:
                    console.print("\n[bold]Getting final response...[/bold]")
                    final_response = await self.send_to_llm(
                        "The maximum number of tool call iterations has been reached. Please provide a final response summarizing what you've learned and any recommendations.",
                        stream=False
                    )
                    
                    # Process the response (without entering the loop again)
                    final_processed = await self.process_llm_response(final_response)
                    
                    # Update the content but don't process any more tool calls
                    current_response["content"] = final_processed["content"]
                    current_response["tool_results"] = []
                except Exception as e:
                    console.print(f"[red]Error getting final response: {str(e)}[/red]")
                
                break
            
            # Continue the conversation with the LLM, sending the tool results as context
            try:
                console.print(f"\n[dim][Tool step {current_iteration}/{max_iterations}] Thinking based on tool results...[/dim]")
                
                # Get updated context to include any changes from previous tool executions
                context_update = await self.get_context_message()
                
                # Get the initial directory for the restriction reminder
                initial_directory = self.session_state.get("initial_directory", str(self.initial_directory))
                
                # Create a more specific prompt for the next iteration
                next_prompt = (
                    f"You've executed previous steps and now you're in directory: {self.session_state.get('cwd', str(self.cwd))}. "
                    f"REMEMBER: You must stay within the initial directory: {initial_directory}. "
                    f"Based on the tool results, continue working on the task. "
                    f"Here's your current state:\n\n{context_update}\n\n"
                    f"Please decide whether to use another tool or provide your final response."
                )
                
                # Check if there were any failed tools in this iteration and enhance the prompt
                if any(not r.get("success", False) for r in current_response["tool_results"]):
                    # Extract the failed command details
                    failed_tools = [r for r in current_response["tool_results"] if not r.get("success", False)]
                    failed_tool_details = "\n".join([
                        f"- Tool '{r.get('name', 'unknown')}' failed with: {r.get('result', 'Unknown error')}"
                        for r in failed_tools
                    ])
                    
                    # Create more specific guidance for the next attempt
                    next_prompt = (
                        f"ERROR SUMMARY: The previous tool executions failed:\n{failed_tool_details}\n\n"
                        f"IMPORTANT: Please DO NOT repeat the same exact commands that failed. Instead:\n"
                        f"1. Analyze why the commands failed based on the error messages\n"
                        f"2. Try a completely different approach or fix the specific issues mentioned in the errors\n"
                        f"3. If one approach isn't working after multiple attempts, try an alternative method\n\n"
                        f"You're currently in directory: {self.session_state.get('cwd', str(self.cwd))}.\n"
                        f"REMEMBER: You must stay within the initial directory: {initial_directory}.\n\n"
                        f"Current state:\n{context_update}\n\n"
                        f"Please decide on a new approach or provide your final response."
                    )
                
                # If we've seen the same command fail multiple times, add a stronger warning
                if len(failed_commands) >= 2:
                    # Get the 2 most recent commands
                    recent_cmds = [fc.get("args", {}).get("command", "") for fc in failed_commands[-2:] 
                                  if fc.get("tool") == "terminal_command"]
                    
                    if len(recent_cmds) == 2 and recent_cmds[0] == recent_cmds[1] and recent_cmds[0]:
                        next_prompt = (
                            f"CRITICAL WARNING: You've repeated the command '{recent_cmds[0]}' multiple times and it "
                            f"keeps failing with the same error. This exact command WILL NOT WORK.\n\n"
                            f"You MUST try a COMPLETELY DIFFERENT approach. The current approach is not working at all.\n\n"
                            f"{next_prompt}"
                        )
                
                # Send a message to the LLM to process the tool results
                next_response = await self.send_to_llm(
                    next_prompt,
                    stream=False
                )
                
                # Process the response and continue the loop if needed
                current_response = await self.process_llm_response(next_response)
            except Exception as e:
                console.print(f"[red]Error processing tool result: {str(e)}[/red]")
                break
        
        # Return the final processed response
        return current_response


async def start_chat(directory: Optional[Path] = None) -> None:
    """
    Start an interactive chat session with the AI assistant.
    
    Args:
        directory: Optional directory to run the chat session in (default: current directory)
    """
    session = ChatSession(cwd=directory)
    await session.run()


# Non-async version for backward compatibility
def start_chat_sync(directory: Optional[Path] = None) -> None:
    """
    Start an interactive chat session with the AI assistant (synchronous wrapper).
    
    Args:
        directory: Optional directory to run the chat session in (default: current directory)
    """
    import asyncio
    asyncio.run(start_chat(directory))
