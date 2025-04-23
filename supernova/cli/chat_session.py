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
    display_generating_animation, theme_color, set_theme, format_rich_objects
)

console = Console()

def theme_color(color_name):
    """
    Get a color from the current theme.
    
    Args:
        color_name: The name of the color to get
        
    Returns:
        The color string for rich
    """
    # Define default colors
    theme_colors = {
        "primary": "cyan",
        "secondary": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "info": "white",
        "muted": "grey70"
    }
    
    # Return the requested color or default to white
    return theme_colors.get(color_name, "white")


def set_theme(theme_name: str) -> None:
    """Set the current theme."""
    # Placeholder for future theme support
    pass

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
        
        # Token allocation constants
        self.max_tokens = 4096  # Default max tokens
        self.llm_token_allocation_constants = {
            "PROMPT_OVERHEAD": 0.2,  # 20% reserved for overhead
            "SYSTEM_MESSAGE": 0.5,   # 50% of remaining tokens for system message
            "CONTEXT": 0.2,          # 20% of remaining tokens for context
            "HISTORY": 0.3           # 30% of remaining tokens for chat history
        }
        
        # If config has token allocation settings, use those
        if hasattr(self.config, "token_allocation"):
            if hasattr(self.config.token_allocation, "max_tokens"):
                self.max_tokens = self.config.token_allocation.max_tokens
            if hasattr(self.config.token_allocation, "constants"):
                token_constants = self.config.token_allocation.constants
                for key, value in token_constants.items():
                    if key in self.llm_token_allocation_constants:
                        self.llm_token_allocation_constants[key] = value
        
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
            "initial_directory": str(self.cwd),
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
            # todo change these with actual analysis.
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
            self.add_message("system", self.generate_system_prompt(cli_args={}))
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
        # Make sure content is a string
        if not isinstance(content, str):
            try:
                # Try to get a nice string representation using ui_utils
                content = format_rich_objects(content)
            except ImportError:
                # Fall back to str() if the function isn't available
                content = str(content)
                
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
            "role": "tool",
            "name": tool_name,
            "content": content,
            "tool_call_id": tool_call_id,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Add to the messages list
        self.messages.append(message)
        
        # Update session state with tool usage
        if "used_tools" not in self.session_state:
            self.session_state["used_tools"] = []
            
        self.session_state["used_tools"].append({
            "name": tool_name,
            "args": tool_args,
            "success": success,
            "result": result,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        # Set last action result to help the LLM know the most recent result
        if tool_name == "terminal_command" and isinstance(tool_args, dict):
            command = tool_args.get("command", "")
            self.session_state["LAST_ACTION_RESULT"] = f"TOOL: {tool_name} | COMMAND: {command} | SUCCESS: {success}"
        else:
            self.session_state["LAST_ACTION_RESULT"] = f"TOOL: {tool_name} | SUCCESS: {success} | RESULT: {result}"
        
        # Save to the database if available
        if hasattr(self, 'chat_id') and self.chat_id and hasattr(self, 'db'):
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
    
    def get_llm_response(self):
        """
        Get a response from the LLM based on the current messages.
        
        Returns:
            A dictionary containing the LLM's response and any tool calls
        """
        try:
            # Get context message
            context_msg = self.get_context_message()
            
            # Generate system prompt
            system_prompt = self.generate_system_prompt()
            
            # Format messages for the LLM
            formatted_messages, tools, tool_choice = self.format_messages_for_llm(
                content="", 
                system_prompt=system_prompt,
                context_msg=context_msg,
                previous_messages=self.messages,
                include_tools=True
            )
            
            # Get LLM response
            response = self.llm_provider.get_completion(
                messages=formatted_messages,
                tools=tools,
                stream=False
            )
            
            # Process the response
            assistant_response = ""
            tool_calls = []
            
            # Ensure response is a dictionary
            if not isinstance(response, dict):
                self.logger.warning(f"Expected dict response from get_completion, got {type(response)}")
                if hasattr(response, 'content'):
                    assistant_response = response.content
                elif hasattr(response, 'choices') and response.choices:
                    assistant_response = response.choices[0].message.content or ""
                else:
                    assistant_response = str(response)
            else:
                # Extract assistant response and tool calls
                if "content" in response:
                    assistant_response = response["content"]
                elif "assistant_response" in response:
                    assistant_response = response["assistant_response"]
                
                # Extract tool calls if available
                if "tool_calls" in response:
                    tc = response["tool_calls"]
                    # Ensure tool_calls is a list
                    if isinstance(tc, list):
                        tool_calls = tc
                    else:
                        tool_calls = [tc]
            
            # Ensure assistant_response is a string
            if assistant_response is None:
                assistant_response = ""
            elif not isinstance(assistant_response, str):
                assistant_response = str(assistant_response)
            
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
    
    def format_messages_for_llm(
        self, 
        content: str = "", 
        system_prompt: str = "", 
        context_msg: str = "", 
        previous_messages: List[Dict[str, Any]] = None,
        include_tools: bool = True
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Format messages for the LLM.
        
        Args:
            content: The current message content
            system_prompt: The system prompt
            context_msg: The context message
            previous_messages: Previous messages to include
            include_tools: Whether to include tools
            
        Returns:
            Tuple of (formatted messages, tools, tool_choice)
        """
        # Initialize previous_messages if not provided
        if previous_messages is None:
            previous_messages = []
            
        # Format messages for the LLM
        formatted_messages = []
        
        # Add system message
        if system_prompt:
            formatted_messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Add previous messages
        for msg in previous_messages:
            if msg["role"] in ["user", "assistant", "system", "tool"]:
                formatted_msg = {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                formatted_messages.append(formatted_msg)
        
        # Add context message as a system message if provided
        if context_msg:
            formatted_messages.append({
                "role": "system",
                "content": f"Current session state:\n{context_msg}"
            })
        
        # Add current message if provided
        if content:
            formatted_messages.append({
                "role": "user",
                "content": content
            })
        
        # Prepare tools if required
        tools = []
        tool_choice = None
        
        if include_tools and self.tool_manager:
            tools = self.tool_manager.get_available_tools_for_llm(self.session_state)
            # Let the model choose which tool to use
            tool_choice = {"type": "auto"}
        
        return formatted_messages, tools, tool_choice
    
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
            if isinstance(tool, dict) and "function" in tool:
                func = tool["function"]
                name = func.get("name", "unknown")
                description = func.get("description", "No description")
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
    
    def generate_system_prompt(
        self, cli_args: Dict[str, Any] = None, is_initial_prompt: bool = False
    ) -> str:
        """
        Generate the system prompt for the LLM.
        
        Args:
            cli_args: Optional CLI arguments
            is_initial_prompt: Whether this is the initial prompt
            
        Returns:
            The system prompt
        """
        # Use empty dict if cli_args is None
        if cli_args is None:
            cli_args = {}
            
        max_token_allocation = self.max_tokens - (
            self.max_tokens * self.llm_token_allocation_constants["PROMPT_OVERHEAD"]
        )
        system_token_allocation_percentage = (
            self.llm_token_allocation_constants["SYSTEM_MESSAGE"]
        )
        system_token_allocation = max_token_allocation * system_token_allocation_percentage
        
        # Get the list of actually available tools
        available_tools = []
        if self.tool_manager:
            tools = self.tool_manager.get_available_tools_for_llm(self.session_state)
            for tool in tools:
                if isinstance(tool, dict) and "function" in tool:
                    func = tool["function"]
                    name = func.get("name", "unknown")
                    description = func.get("description", "No description")
                    available_tools.append(f"- `{name}`: {description}")
        
        available_tools_text = "\n".join(available_tools) if available_tools else "No tools are currently available."
        
        # Format guidance for tool calling
        tool_call_guidance = f"""
⚠️ ⚠️ ⚠️ CRITICAL INSTRUCTION: TOOL CALLING FORMAT ⚠️ ⚠️ ⚠️

You MUST use ONLY the native tool calling API for ALL tool usage. ANY other format WILL FAIL and result in TASK FAILURE.

❌ NEVER use these incorrect formats:
  1. NEVER output tool calls as raw JSON
  2. NEVER use a ```tool_request ... [END_TOOL_REQUEST]``` format
  3. NEVER use <tool_name> or similar custom XML formats
  4. NEVER output tool calls as code blocks

✅ ALWAYS use the native API format for tool calls:
  - Use the built-in tool calling API that returns "finish_reason": "tool_calls"
  - Let the system handle the JSON conversion and tool execution
  - ONLY use tools that are actually provided to you in the API request
  - DO NOT attempt to use any tools that are not explicitly provided

⚠️ IMPORTANT: You MUST ONLY use the tools that are specifically provided to you in this session.
The following tools are currently available:

{available_tools_text}

DO NOT attempt to use any tools not listed above, even if they seem like they would be helpful.

Example of CORRECT tool usage (DO THIS):
  When you need to use a tool, simply declare your intent to use it normally within the API.
  The system will automatically convert your request to the appropriate JSON format.

This is an absolute requirement for successful task completion.
"""

        # Base system prompt with critical tool guidance first
        system_prompt = f"""You are SuperNova, a powerful AI-powered development assistant, built by ex-OpenAI engineers. You are both skilled at software engineering and effective at helping users plan and execute complex creative and analytical projects.

{tool_call_guidance}

{getattr(self.config, "system_prompt_override", "")}

For this conversation, let's break down our workflow into the following clear steps:

1. First, analyze what the user is asking for to understand their goal. Read their question carefully.

2. If this is a "fresh" conversation with a new task (i.e., this is the initial message), I should explore the Memory Bank to understand context. The Memory Bank is a collection of knowledge files about our project:
   - projectbrief.md: Overview of the project
   - activeContext.md: Current work focus
   - systemPatterns.md: Architecture and patterns
   - techContext.md: Technologies in use
   - productContext.md: Product context
   - progress.md: Current progress
   - Any additional context files that may be available

3. My source of truth for what's been asked, agreed, and done during the current task should be documented in the active_task.md file, including:
    - The initial goal stated by the user
    - The agreed plan
    - Progress made so far
    - Any important decisions
    - Future steps to be taken

4. When I analyze the results of a tool, I should:
   - Carefully look at all the output
   - Consider whether there were errors
   - Remember important file content
   - Use these findings to develop a comprehensive understanding for my next action

5. When I need to accomplish a task:
   - ⚠️ REMEMBER: ONLY use the tools that are available to me (listed above) ⚠️
   - Use tools in a way that's appropriate to the task I'm trying to accomplish
   - I must NEVER try to use tools that aren't available to me
   - If I can't accomplish a task with available tools, I should explain what I would do if I had the appropriate tools
   - NEVER invent or assume the existence of tools that aren't explicitly provided

6. When I write code, I should:
   - Review existing patterns first
   - Match the surrounding style and conventions
   - Import all necessary dependencies
   - Add descriptive comments (but not excessively)
   - Be mindful of edge cases
   - Avoid redundant or duplicate code
   - Write complete, correct implementations

7. When given a task, I should break it down into:
   - Immediate actions
   - Later steps
   - Information that needs to be discovered
   - Potential challenges

8. IMPORTANT: I should not repeat the same actions! If I've already looked at a file and found that it doesn't contain what I'm looking for, I should focus my search elsewhere. Similarly, if I've tried to run a command and it failed, I should adapt my approach rather than just trying the same thing again.

9. Throughout the conversation, I will:
   - Keep my responses focused and concise
   - Clearly indicate when I'm using tools to gather information
   - Summarize findings succinctly without excessive detail
   - Focus on delivering solutions rather than explaining generic concepts

10. ⚠️ Tool usage rule: I MUST ONLY use the standard tool call format built into the API, and ONLY for tools that are available (listed above). I must NEVER provide tool calls as raw code blocks or JSON, and must NEVER use any custom format like ```tool_request``` or similar. Failure to follow this rule will result in tool execution failure. ⚠️

When analyzing code, I'll look beyond just syntax to understand architecture, data flow, and potential edge cases.

I may proactively provide advice on code improvements, potential bugs, or design considerations based on my analysis.

I am here to help you build great software!
"""

        def calculate_tokens_for_text(text: str) -> int:
            estimated_tokens = len(text.split())
            return estimated_tokens

        # Calculate tokens for the base prompt
        base_prompt_tokens = calculate_tokens_for_text(system_prompt)

        # Calculate how many tokens we have left for memory
        memory_token_allocation = system_token_allocation - base_prompt_tokens

        # If we have memory items and memory tokens available, include memory content
        memory_content = self.get_memory_content_for_prompt(
            memory_token_allocation, cli_args, is_initial_prompt
        )

        # Assemble the final system prompt
        final_system_prompt = system_prompt

        if memory_content:
            final_system_prompt += f"\n\nHere is relevant information from your Memory Bank:\n\n{memory_content}"

        return final_system_prompt

    def get_memory_content_for_prompt(
        self, token_allocation: int, cli_args: Dict[str, Any] = None, is_initial_prompt: bool = False
    ) -> str:
        """
        Get memory content for the system prompt within token allocation.
        
        Args:
            token_allocation: Maximum tokens to allocate for memory content
            cli_args: CLI arguments that may contain memory-related options
            is_initial_prompt: Whether this is the initial prompt
            
        Returns:
            Formatted memory content string
        """
        # Simple placeholder implementation - in a real scenario, we'd read 
        # actual memory files from the .supernova directory based on token allocation
        memory_content = []
        
        # If we're in a project with a .supernova directory, try to read some basic files
        supernova_dir = Path(self.cwd) / ".supernova"
        if supernova_dir.exists() and supernova_dir.is_dir():
            # Priority files to include
            priority_files = [
                "project_brief.md",
                "active_task.md", 
                "progress_log.md"
            ]
            
            # Try to read each priority file
            for filename in priority_files:
                file_path = supernova_dir / filename
                if file_path.exists() and file_path.is_file():
                    try:
                        # Read the file content
                        content = file_path.read_text()
                        if content.strip():
                            # Add a header and the content
                            memory_content.append(f"## {filename}")
                            memory_content.append(content.strip())
                            memory_content.append("")  # Empty line for separation
                    except Exception as e:
                        self.logger.warning(f"Could not read memory file {filename}: {str(e)}")
        
        # Join the memory content with newlines
        return "\n".join(memory_content) if memory_content else ""

    def process_tool_call_loop(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a continuous loop of tool calls from the LLM.
        
        This method executes a loop where:
        1. Tool calls are extracted from the LLM response
        2. Tools are executed
        3. Results are fed back to the LLM
        4. This continues until there are no more tool calls
        
        Args:
            llm_response: The raw response from the LLM
            
        Returns:
            A dictionary containing the final response after all tool calls
        """
        # Initialize variables
        processed_response = self.process_llm_response(llm_response)
        tool_calls = processed_response.get("tool_calls", []) if isinstance(processed_response, dict) else []
        
        # Get max iterations from config with a default of 5
        max_iterations = 5  # Default value
        try:
            # Try to get from config if available
            if hasattr(self.config, "max_tool_iterations"):
                max_iterations = self.config.max_tool_iterations
        except Exception:
            # If there's an error, use the default
            pass
            
        iteration_count = 0
        response = llm_response
        processed_next = None  # Initialize processed_next
        
        # Track processed call IDs to avoid duplicates
        processed_call_ids = set()
        
        # Process tool calls in a loop until there are no more or we hit the limit
        while tool_calls and iteration_count < max_iterations:
            iteration_count += 1
            self.logger.debug(f"Tool call iteration {iteration_count}/{max_iterations}")
            self.logger.debug(f"Processing {len(tool_calls)} tool calls")
            
            # Display iteration info if verbose
            debug_show_tool_iterations = False
            try:
                if hasattr(self.config, "debug") and hasattr(self.config.debug, "show_tool_iterations"):
                    debug_show_tool_iterations = self.config.debug.show_tool_iterations
            except Exception:
                # If there's an error, use the default
                pass
                
            if debug_show_tool_iterations:
                console.print(f"\n[dim][Tool step {iteration_count}/{max_iterations}][/dim]")
            
            # Process each tool call
            tool_results = []
            tool_messages = []
            invalid_tool_names = []
            
            # Pre-filter tool calls to check for invalid tools
            filtered_tool_calls = []
            for tc in tool_calls:
                # Extract the tool name and call ID
                tool_name = None
                call_id = None
                
                if isinstance(tc, dict):
                    if 'function' in tc and 'name' in tc['function']:
                        tool_name = tc['function']['name']
                    call_id = tc.get('id')
                elif hasattr(tc, 'function') and hasattr(tc.function, 'name'):
                    tool_name = tc.function.name
                    call_id = tc.id if hasattr(tc, 'id') else None
                
                # Skip if we've already processed this call ID
                if call_id and call_id in processed_call_ids:
                    self.logger.debug(f"Skipping already processed tool call: {call_id}")
                    continue
                
                # Verify the tool exists
                if tool_name and not self.verify_tool_exists(tool_name):
                    invalid_tool_names.append(tool_name)
                    # Add an error message for this invalid tool
                    tool_results.append({
                        "tool_name": tool_name,
                        "success": False,
                        "error": "unknown_tool",
                        "tool_call_id": call_id
                    })
                    # Add tool message with error
                    tool_messages.append({
                        "role": "tool",
                        "content": f"Error executing tool {tool_name}: unknown_tool",
                        "name": tool_name,
                        "tool_call_id": call_id
                    })
                    
                    # Mark as processed
                    if call_id:
                        processed_call_ids.add(call_id)
                else:
                    # Tool exists or we couldn't determine its name, let handle_tool_call deal with it
                    filtered_tool_calls.append(tc)
            
            # Log invalid tools
            if invalid_tool_names:
                self.logger.warning(f"Found {len(invalid_tool_names)} invalid tool calls: {', '.join(invalid_tool_names)}")
                console.print(f"[yellow]Warning: Found invalid tool calls: {', '.join(invalid_tool_names)}[/yellow]")
            
            # Process the filtered tool calls
            for tc in filtered_tool_calls:
                # Handle different types of tool call objects
                if isinstance(tc, dict):
                    # Dictionary format
                    if 'function' not in tc:
                        self.logger.warning(f"Invalid tool call missing function: {tc}")
                        continue
                    
                    tc_function = tc.get('function', {})
                    if 'name' not in tc_function:
                        self.logger.warning(f"Invalid tool call missing function name: {tc}")
                        continue
                    
                    tool_name = tc_function.get('name', '')
                    args = tc_function.get('arguments', {})
                    call_id = tc.get('id', 'unknown')
                    
                elif hasattr(tc, 'function') and hasattr(tc, 'id') and hasattr(tc, 'type'):
                    # ChatCompletionMessageToolCall or similar object
                    if not hasattr(tc.function, 'name'):
                        self.logger.warning(f"Invalid tool call missing function name: {tc}")
                        continue
                    
                    tool_name = tc.function.name
                    # Parse arguments if they're in string format
                    if hasattr(tc.function, 'arguments'):
                        args_str = tc.function.arguments
                        try:
                            args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        except json.JSONDecodeError:
                            self.logger.warning(f"Failed to parse arguments as JSON: {args_str}")
                            args = {}
                    else:
                        args = {}
                    
                    call_id = tc.id
                else:
                    self.logger.warning(f"Unsupported tool call format: {type(tc)}")
                    continue
                
                # Skip if we've already processed this call ID
                if call_id in processed_call_ids:
                    self.logger.debug(f"Skipping already processed tool call: {call_id}")
                    continue
                
                # Mark this call ID as processed
                processed_call_ids.add(call_id)
                
                # Show info about the tool call
                self.logger.debug(f"Processing tool call: {tool_name} with ID {call_id}")
                
                # For cd commands, we need to update the directory
                if tool_name == "terminal_command" or tool_name == "run_terminal_cmd":
                    # Handle terminal command (with special handling for cd)
                    command = args.get("command", "")
                    
                    # Check if this is a cd command
                    if command.strip().startswith("cd "):
                        # Handle cd command by updating the working directory
                        result = self.handle_terminal_command(args)
                        
                        # Update the session state with the command result
                        self.session_state["LAST_ACTION"] = "terminal_command"
                        self.session_state["LAST_ACTION_ARGS"] = args
                        self.session_state["LAST_ACTION_RESULT"] = result
                        
                        # Create a summary of the command result for the LLM
                        if isinstance(result, dict) and result.get("success"):
                            if "current_dir" in result:
                                tool_msg = f"Current directory is now: {result['current_dir']}"
                            else:
                                tool_msg = f"Command executed successfully: {command}"
                        else:
                            err = result.get("error", "unknown error") if isinstance(result, dict) else "unknown error"
                            tool_msg = f"Error executing command: {err}"
                        
                        # Add to tool messages
                        tool_messages.append({
                            "role": "tool",
                            "content": tool_msg,
                            "tool_call_id": call_id,
                            "name": tool_name
                        })
                        
                        # Add to tool results
                        tool_results.append({
                            "tool_name": tool_name,
                            "success": result.get("success", False) if isinstance(result, dict) else False,
                            "result": result,
                            "tool_call_id": call_id
                        })
                    else:
                        # Create a dictionary format that handle_tool_call can process
                        tool_call_dict = {
                            "id": call_id,
                            "function": {
                                "name": tool_name,
                                "arguments": args
                            }
                        }
                        
                        # Handle other terminal commands normally
                        result = self.handle_tool_call(tool_call_dict)
                        
                        if result:
                            # Add to tool results
                            tool_results.append(result)
                            
                            # Create tool message
                            success = result.get("success", False) if isinstance(result, dict) else False
                            if success:
                                content = f"Command executed successfully: {command}"
                                if "stdout" in result and result["stdout"]:
                                    content += f"\nOutput:\n{result['stdout']}"
                            else:
                                error = result.get("result", "unknown error").get("stderr","unknow_error") if isinstance(result, dict) else "unknown error"
                                content = f"Error executing command: {error}"
                                
                            tool_messages.append({
                                "role": "tool",
                                "content": content,
                                "tool_call_id": call_id,
                                "name": tool_name
                            })
                else:
                    # Create a dictionary format that handle_tool_call can process
                    tool_call_dict = {
                        "id": call_id,
                        "function": {
                            "name": tool_name,
                            "arguments": args
                        }
                    }
                    
                    # Handle other types of tools
                    result = self.handle_tool_call(tool_call_dict)
                    
                    if result:
                        # Add to tool results
                        tool_results.append(result)
                        
                        # Create tool message
                        if isinstance(result, dict):
                            success = result.get("success", False)
                            error = result.get("error", None)
                            
                            if success:
                                content = f"Tool {tool_name} executed successfully"
                                if "result" in result:
                                    # For complex results, format them nicely
                                    content += f"\nResult: {self.format_result(result['result'])}"
                            else:
                                content = f"Error executing tool {tool_name}: {error or 'unknown error'}"
                        else:
                            content = f"Tool {tool_name} returned: {result}"
                            
                        tool_messages.append({
                            "role": "tool",
                            "content": content,
                            "tool_call_id": call_id,
                            "name": tool_name
                        })
            
            # Process the tool results
            if tool_results:
                self.process_tool_results(tool_results)
                
                # Add a single summary message for all tool results instead of individual messages
                if len(tool_messages) > 0:
                    self.add_tool_summary_message(tool_results)
                
                # If we have tool messages, send them back to LLM
                if tool_messages:
                    console.print(f"\n[dim][Tool step {iteration_count}/{max_iterations}] Thinking based on tool results...[/dim]")
                    
                    # Format messages for LLM - make sure we include tool_call_id in messages
                    messages, tools, model = self.format_messages_for_llm(
                        "", # Remove the content from here so it doesn't become a user message
                        self.generate_system_prompt(), 
                        self.get_context_message() + "\n\nContinue based on tool results", # Add the instruction here as part of the context message
                        self.messages, 
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
                    if isinstance(processed_next, dict) and "content" in processed_next:
                        processed_response["content"] = processed_next["content"]
                    
                    # Update response for next iteration
                    response = next_response
            
            # Get the tool calls for the next iteration
            tool_calls = []  # Default to empty list
            if processed_next is not None and isinstance(processed_next, dict) and "tool_calls" in processed_next:
                tool_calls = processed_next.get("tool_calls", [])
                # Ensure tool_calls is a list
                if tool_calls is None:
                    tool_calls = []
                elif not isinstance(tool_calls, list):
                    tool_calls = [tool_calls]
        
        # Add a final summary message if we ran any iterations
        if iteration_count > 0:
            summary = f"\n[yellow]Completed {iteration_count} tool call iterations[/yellow]"
            if iteration_count >= max_iterations:
                summary += " [reached maximum limit]"
            console.print(summary)
        
        return processed_response

    def display_stream(self, content: str) -> None:
        """
        Display streaming content to the console.
        
        Args:
            content: The content to display
        """
        # Simply print the content
        print(content, end="", flush=True)
    
    def process_tool_results(self, tool_results: List[Dict]) -> None:
        """
        Process tool results from handled tool calls.
        
        Args:
            tool_results: List of tool result dictionaries
        """
        if not tool_results:
            return
            
        for result in tool_results:
            tool_name = result.get("tool_name", "unknown")
            success = result.get("success", False)
            error = result.get("result", None).get("stderr", None)
            raw_result = result.get("result", None).get("result", None)
            
            if success:
                # Format the result for display
                if isinstance(raw_result, dict) or isinstance(raw_result, list):
                    try:
                        formatted_result = json.dumps(raw_result, indent=2)
                    except Exception:
                        formatted_result = str(raw_result)
                else:
                    formatted_result = str(raw_result)
                    
                # Add to session state
                self.session_state["LAST_ACTION_RESULT"] = formatted_result
                
                # Display success message
                console.print(f"[green]Tool {tool_name} executed successfully[/green]")
                
                # Display the tool result in a panel if it's not empty
                if formatted_result and formatted_result.strip():
                    # Create a panel for the result
                    result_panel = Panel(
                        formatted_result,
                        title=f"Result from {tool_name}",
                        title_align="left",
                        border_style="green"
                    )
                    console.print(result_panel)
            else:
                # Add to session state
                self.session_state["LAST_ACTION_RESULT"] = f"Error: {error}"
                
                # Display error message
                console.print(f"[red]Tool {tool_name} failed: {error}[/red]")

    def run_chat_loop(self, initial_user_input=None, auto_run=False):
        """
        Run the chat loop with enhanced UI.
        
        Args:
            initial_user_input: Initial input from the user
            auto_run: Whether to auto-run the initial input
        """
        try:
            # Load or create chat session
            self.load_or_create_chat()
            
            # Initialize variables
            keep_running = True
            first_message = True
            
            # Run the chat loop
            while keep_running:
                try:
                    # Get user input if not provided
                    if initial_user_input and first_message:
                        user_input = initial_user_input
                        first_message = False
                    else:
                        user_input = self.get_user_input()
                    
                    # Check for exit commands
                    if user_input.lower() in ["exit", "quit"]:
                        console.print(f"[{theme_color('secondary')}]Exiting SuperNova...[/{theme_color('secondary')}]")
                        break
                    
                    # Add user message to chat history
                    self.add_message("user", user_input)
                    
                    # Get response from LLM
                    response = self.get_llm_response()
                    
                    # Process the response
                    if "error" in response:
                        console.print(f"[{theme_color('error')}]Error: {response['error']}[/{theme_color('error')}]")
                    else:
                        # Process content
                        content = response.get("content", "")
                        if content:
                            self.add_message("assistant", content)
                            self.display_response(content)
                        
                        # Process tool calls
                        tool_calls = response.get("tool_calls", [])
                        if tool_calls:
                            # Process tool calls in a loop until there are no more
                            final_response = self.process_tool_call_loop(response)
                            
                            # Add final response to chat history
                            if final_response.get("content"):
                                self.add_message("assistant", final_response["content"])
                                self.display_response(final_response["content"])
                
                except KeyboardInterrupt:
                    console.print(f"[{theme_color('warning')}]Operation interrupted[/{theme_color('warning')}]")
                    
                except Exception as e:
                    console.print(f"[{theme_color('error')}]Error in chat loop: {str(e)}[/{theme_color('error')}]")
                    traceback.print_exc()
        
        except Exception as e:
            console.print(f"[{theme_color('error')}]Error in chat loop: {str(e)}[/{theme_color('error')}]")
            traceback.print_exc()

    def display_response(self, response, role="assistant"):
        """
        Display a response with enhanced UI.
        
        Args:
            response: The response content
            role: The role of the responder (assistant or user)
        """
        # Determine styling based on role
        if role == "assistant":
            title = "🤖 Assistant"
            border_style = theme_color("primary")
        elif role == "user":
            title = "👤 You"
            border_style = theme_color("secondary")
        else:
            title = role.capitalize()
            border_style = theme_color("info")
        
        # Format response for display
        if not isinstance(response, str):
            response = str(response)
            
        # Create a panel for the response
        panel = Panel(
            response,
            title=title,
            title_align="left",
            border_style=border_style,
            padding=(1, 2)
        )
        
        # Display the panel
        console.print(panel)

    def add_tool_summary_message(self, tool_results):
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
                success = result.get("result", False).get("success", False)
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
                    content = result.get("result", "unknown_error").get("stderr","unknow_error")
                
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
                    if hasattr(self, 'chat_id') and self.chat_id and hasattr(self, 'db'):
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
                    if hasattr(self, 'chat_id') and self.chat_id and hasattr(self, 'db'):
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

    def _reset_streaming_state(self) -> None:
        """Reset the streaming state for a new stream."""
        self._streaming_started = False
        self._tool_calls_reported = False
        self._latest_full_content = ""
        self._latest_tool_calls = []
        self.streaming_accumulated_content = ""
        self.streaming_accumulated_tool_calls = {}

    def get_context_message(self) -> str:
        """
        Get the context message for the current session.
        
        Returns:
            Context message string
        """
        # Get context message
        context_parts = [
            "Current working directory: " + self.session_state["cwd"],
            "Initial directory: " + self.session_state["initial_directory"],
            "Path history:"
        ]
        
        # Add path history if available
        if self.session_state.get("path_history"):
            for path in self.session_state["path_history"][-5:]:  # Show last 5 paths
                context_parts.append(f"- {path}")
        
        # Add executed commands if available
        if self.session_state.get("executed_commands"):
            context_parts.append("\nRecently executed commands:")
            for cmd in self.session_state["executed_commands"][-5:]:  # Show last 5 commands
                context_parts.append(f"- {cmd}")
        
        # Add used tools if available
        if self.session_state.get("used_tools"):
            context_parts.append("\nRecently used tools:")
            for tool in self.session_state["used_tools"][-5:]:  # Show last 5 tools
                context_parts.append(f"- {tool}")
        
        # Add created files if available
        if self.session_state.get("created_files"):
            context_parts.append("\nRecently created files:")
            for file in self.session_state["created_files"][-5:]:  # Show last 5 files
                context_parts.append(f"- {file}")
        
        # Add last action result if available
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
            system_prompt=self.generate_system_prompt(cli_args={}),
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
        try:
            # Process the streaming response chunk
            result = self.llm_provider.process_streaming_response(
                chunk, 
                self.streaming_accumulated_content, 
                self.streaming_accumulated_tool_calls
            )
            
            # Make sure result is a dictionary
            if not isinstance(result, dict):
                self.logger.warning(f"Expected dict result from process_streaming_response, got {type(result)}")
                return
            
            # Update accumulated content if provided in result
            if "full_content" in result:
                self.streaming_accumulated_content = result["full_content"]
            
            # Update accumulated tool calls if provided in result
            if "accumulated_tool_calls" in result:
                if isinstance(result["accumulated_tool_calls"], (dict, list)):
                    self.streaming_accumulated_tool_calls = result["accumulated_tool_calls"]
            
            # Check for response type
            response_type = result.get("type") if isinstance(result, dict) else None
            
            if response_type == "content":
                # Display new content
                content = result.get("content", "")
                if content:
                    self.display_stream(content)
                    
            elif response_type == "tool_calls":
                tool_calls = result.get("tool_calls", [])
                if isinstance(tool_calls, list) and tool_calls:
                    self.logger.debug(f"Received {len(tool_calls)} tool calls in stream chunk")
                    
                    # Convert tool calls to dictionaries
                    converted_tool_calls = [self._convert_tool_call_to_dict(tc) for tc in tool_calls]
                    
                    # Process each tool call, but only if it's complete enough to process
                    for tool_call in converted_tool_calls:
                        # Only process complete tool calls (those with both name and arguments)
                        if isinstance(tool_call, dict) and 'function' in tool_call:
                            function = tool_call['function']
                            if isinstance(function, dict) and 'name' in function:
                                function_name = function.get('name')
                                function_args = function.get('arguments', '')
                                
                                # Check if we have enough information to process this tool call
                                if function_name and function_name.strip():
                                    self.logger.debug(f"Processing stream tool call: {function_name}")
                                    
                                    # Process the tool call
                                    tool_result = self.handle_tool_call(tool_call)
                                    
                                    # Display the result if we have one
                                    if tool_result:
                                        # Handle the tool results
                                        self.process_tool_results([tool_result])
            # If no type is provided, still display content if available
            elif isinstance(result, dict) and "content" in result and result["content"]:
                self.display_stream(result["content"])
        
        except Exception as e:
            self.logger.error(f"Error processing stream chunk: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _convert_tool_call_to_dict(self, tool_call):
        """
        Convert a tool call object to a dictionary for consistent processing.
        
        Args:
            tool_call: The tool call object, which might be a dict or another type
            
        Returns:
            A dictionary representing the tool call
        """
        # If already a dict, use it directly
        if isinstance(tool_call, dict):
            return tool_call
            
        # Otherwise, try to convert to dict based on common formats
        result = {}
        
        # Handle OpenAI style tool calls
        if hasattr(tool_call, 'function'):
            function_info = {}
            if hasattr(tool_call.function, 'name'):
                function_info['name'] = tool_call.function.name
            if hasattr(tool_call.function, 'arguments'):
                try:
                    # Try to parse JSON arguments
                    function_info['arguments'] = json.loads(tool_call.function.arguments)
                except:
                    # Fall back to string if can't parse
                    function_info['arguments'] = tool_call.function.arguments
                    
            result['function'] = function_info
            
        # Include ID if available
        if hasattr(tool_call, 'id'):
            result['id'] = tool_call.id
            
        return result

    def verify_tool_exists(self, tool_name: str) -> bool:
        """
        Verify that a tool exists and is available for use.
        
        Args:
            tool_name: Name of the tool to verify
            
        Returns:
            True if the tool exists, False otherwise
        """
        if not self.tool_manager:
            return False
            
        return self.tool_manager.has_tool(tool_name)
        
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
        
        # Verify the tool exists
        if not self.verify_tool_exists(tool_name):
            self.logger.warning(f"Unknown tool: {tool_name}")
            return {
                "error": "unknown_tool",
                "message": f"Unknown tool: {tool_name}",
                "tool_name": tool_name
            }
        
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
            
            # Add session_state to kwargs - the tool handler expects named arguments only
            kwargs = parsed_args.copy()
            kwargs['session_state'] = self.session_state
            
            # Call the function with kwargs only, no positional args
            result = tool_function(**kwargs)
            
            return {
                "result": result,
                "tool_name": tool_name,
                "success": result.get("success", False),
                "tool_call_id": call_id,
                "command": parsed_args.get("command")
            }
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {
                "error": "execution_error",
                "message": f"Error executing {tool_name}: {str(e)}",
                "tool_name": tool_name,
                "success": False
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
            
            # Display processing message and show the input in a panel
            console.print(f"[{theme_color('secondary')}]Processing your input...[/{theme_color('secondary')}]")
            # Display user input in a panel
            self.display_response(user_input, role="user")
        
            return user_input
        except KeyboardInterrupt:
            console.print(f"[{theme_color('warning')}]Operation interrupted[/{theme_color('warning')}]")
            return "exit"
        except Exception as e:
            console.print(f"[{theme_color('error')}]Error reading input:[/{theme_color('error')}] {str(e)}")
            return "exit"

    def process_llm_response(self, response) -> Dict[str, Any]:
        """
        Process a response from the LLM.
        
        Args:
            response: The raw response from the LLM
            
        Returns:
            Processed response with content and tool calls
        """
        processed = {
            "content": "",
            "tool_calls": []
        }
        
        self.logger.debug(f"Processing LLM response of type: {type(response)}")
        
        try:
            # Handle different response formats
            if isinstance(response, dict):
                # Extract content if available
                if "content" in response:
                    processed["content"] = response["content"]
                elif "assistant_response" in response:
                    processed["content"] = response["assistant_response"]
                elif "choices" in response and len(response["choices"]) > 0:
                    choice = response["choices"][0]
                    if isinstance(choice, dict) and "message" in choice:
                        message = choice["message"]
                        if isinstance(message, dict) and "content" in message:
                            processed["content"] = message["content"]
                
                # Extract tool calls if available
                tool_calls = []
                
                # Try to get tool_calls directly
                if "tool_calls" in response:
                    tool_calls = response["tool_calls"]
                # Try to get tool_calls from choices[0].message.tool_calls
                elif "choices" in response and len(response["choices"]) > 0:
                    choice = response["choices"][0]
                    if isinstance(choice, dict) and "message" in choice:
                        message = choice["message"]
                        if isinstance(message, dict) and "tool_calls" in message:
                            tool_calls = message["tool_calls"]
                
                # Ensure tool_calls is a list
                if tool_calls:
                    if not isinstance(tool_calls, list):
                        tool_calls = [tool_calls]
                    processed["tool_calls"] = tool_calls
            
            # Handle object-style responses (e.g., OpenAI's response objects)
            elif hasattr(response, "choices") and hasattr(response.choices, "__getitem__"):
                try:
                    # Get the first choice
                    choice = response.choices[0]
                    
                    # Extract message content
                    if hasattr(choice, "message"):
                        if hasattr(choice.message, "content") and choice.message.content:
                            processed["content"] = choice.message.content
                        
                        # Extract tool calls if available
                        if hasattr(choice.message, "tool_calls"):
                            tool_calls = choice.message.tool_calls
                            if tool_calls:
                                # Keep original tool_calls objects (ChatCompletionMessageToolCall)
                                # Do not convert them to dictionaries
                                if not isinstance(tool_calls, list):
                                    tool_calls = [tool_calls]
                                processed["tool_calls"] = tool_calls
                except (IndexError, AttributeError) as e:
                    self.logger.warning(f"Error extracting from choices: {e}")
            
            # Handle simpler response objects
            elif hasattr(response, "content"):
                processed["content"] = response.content
                
                # Extract tool calls if available
                if hasattr(response, "tool_calls"):
                    tool_calls = response.tool_calls
                    if tool_calls:
                        # Keep original tool_calls objects
                        if not isinstance(tool_calls, list):
                            tool_calls = [tool_calls]
                        processed["tool_calls"] = tool_calls
        
            # Note: No regex-based extraction of tool calls from content 
            # Only using standard tool calling API
        
        except Exception as e:
            self.logger.error(f"Error processing LLM response: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            processed["error"] = str(e)
        
        # Ensure content is a string
        if processed["content"] is None:
            processed["content"] = ""
        elif not isinstance(processed["content"], str):
            processed["content"] = str(processed["content"])
            
        # Log the processed response for debugging (without tool calls details which might be large)
        self.logger.debug(f"Processed response content: {processed['content'][:50]}{'...' if len(processed['content']) > 50 else ''}")
        self.logger.debug(f"Found {len(processed['tool_calls'])} tool calls")
        
        return processed

    def format_result(self, result) -> str:
        """
        Format a tool result for display.
        
        Args:
            result: The result object from a tool
            
        Returns:
            Formatted string
        """
        if result is None:
            return "No result"
            
        try:
            if isinstance(result, dict):
                # Try to convert to JSON
                import json
                return json.dumps(result, indent=2)
            elif isinstance(result, list):
                # Try to convert to JSON
                import json
                return json.dumps(result, indent=2)
            else:
                # Just convert to string
                return str(result)
        except Exception as e:
            self.logger.warning(f"Error formatting result: {str(e)}")
            return str(result)

    def handle_terminal_command(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a terminal command, with special handling for directory changes.
        
        Args:
            args: Arguments for the terminal command
            
        Returns:
            Dictionary with result information
        """
        if "command" not in args:
            return {
                "success": False,
                "error": "No command provided"
            }
            
        command = args.get("command", "").strip()
        
        # Handle cd command specially
        if command.startswith("cd "):
            try:
                # Extract the target directory
                target_dir = command[3:].strip()
                
                # Get current working directory
                current_dir = Path(self.session_state["cwd"])
                
                # Handle special cases
                if target_dir == "..":
                    # Go up one level
                    new_dir = current_dir.parent
                elif target_dir == "~":
                    # Go to home directory
                    new_dir = Path.home()
                elif target_dir.startswith("~/"):
                    # Go to path relative to home
                    new_dir = Path.home() / target_dir[2:]
                elif target_dir == "-":
                    # Go to previous directory (if available)
                    if "path_history" in self.session_state and len(self.session_state["path_history"]) > 1:
                        # Get the previous directory from history
                        new_dir = Path(self.session_state["path_history"][-2])
                    else:
                        return {
                            "success": False,
                            "error": "No previous directory in history",
                            "current_dir": str(current_dir)
                        }
                elif target_dir.startswith("/"):
                    # Absolute path
                    new_dir = Path(target_dir)
                else:
                    # Relative path
                    new_dir = current_dir / target_dir
                
                # Resolve to absolute path
                new_dir = new_dir.resolve()
                
                # Check if the new directory is within the initial directory
                initial_dir = Path(self.session_state["initial_directory"])
                if not str(new_dir).startswith(str(initial_dir)):
                    return {
                        "success": False,
                        "error": f"Cannot navigate outside of the initial directory: {initial_dir}",
                        "current_dir": str(current_dir)
                    }
                
                # Check if the directory exists
                if not new_dir.exists() or not new_dir.is_dir():
                    return {
                        "success": False,
                        "error": f"Directory does not exist: {new_dir}",
                        "current_dir": str(current_dir)
                    }
                
                # Update the working directory
                self.cwd = new_dir
                self.session_state["cwd"] = str(new_dir)
                
                # Add to path history
                if "path_history" not in self.session_state:
                    self.session_state["path_history"] = []
                self.session_state["path_history"].append(str(new_dir))
                
                return {
                    "success": True,
                    "current_dir": str(new_dir),
                    "message": f"Changed directory to {new_dir}"
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error changing directory: {str(e)}"
                }
        else:
            # For other commands, use the command_runner
            try:
                from supernova.core import command_runner
                result = command_runner.run_command(command, cwd=self.session_state["cwd"])
                
                # Check if the command succeeded
                success = result.get("exit_code", 1) == 0
                
                # Format result for return
                return {
                    "success": success,
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "exit_code": result.get("exit_code", 1),
                    "command": command
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error executing command: {str(e)}",
                    "command": command
                }

def start_chat_sync(chat_dir: Optional[Union[str, Path]] = None) -> None:
    """
    Start a synchronous chat session.
    
    Args:
        chat_dir: Optional directory to start the chat in
    """
    # Create a chat session and run it
    chat_session = ChatSession(initial_directory=chat_dir)
    chat_session.run_chat_loop()
