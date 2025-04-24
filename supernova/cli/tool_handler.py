"""
SuperNova - AI-powered development assistant within the terminal.

Tool handling functionality for CLI.
"""

import json
import logging
import importlib
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from pathlib import Path

from rich.console import Console

from supernova.core import tool_manager
from supernova.core.tool_base import BaseTool
from supernova.core.command_executor import CommandExecutor
from supernova.extensions.file_create_tool import FileCreateTool
from supernova.extensions.file_info_tool import FileInfoTool
from supernova.tools.terminal_command_tool import TerminalCommandTool

console = Console()

class ToolHandler:
    """
    Handles tool execution and management for the CLI.
    
    Responsibilities:
    - Verifying tool existence
    - Handling tool calls
    - Processing tool results
    - Managing tool execution loop
    """
    
    def __init__(self, session_state: Dict[str, Any] = None, logger=None):
        """
        Initialize the tool handler.
        
        Args:
            session_state: Current session state
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger("supernova.tool_handler")
        self.tool_manager = tool_manager.ToolManager()
        self.session_state = session_state or {}
        
        # Initialize command executor
        self.command_executor = CommandExecutor()
        
        # Initialize available tools
        self.available_tools = {}
        self._initialize_tools()
    
    def _initialize_tools(self):
        """Initialize all available tools."""
        # Common tools
        self.add_tool(FileCreateTool())
        self.add_tool(FileInfoTool())
        self.add_tool(TerminalCommandTool())
        
        # Try to load additional tools
        self._load_extension_tools()
    
    def _load_extension_tools(self):
        """Load tools from extensions directory."""
        try:
            # Here we would dynamically load tools from the extensions directory
            # For now, let's just log that we're trying to load extensions
            self.logger.debug("Attempting to load extension tools")
            
            # This is where we would scan for and load additional tools
            # For example:
            # for tool_module in extension_modules:
            #     try:
            #         module = importlib.import_module(tool_module)
            #         for name in dir(module):
            #             obj = getattr(module, name)
            #             if isinstance(obj, type) and issubclass(obj, BaseTool) and obj != BaseTool:
            #                 self.add_tool(obj())
            #     except Exception as e:
            #         self.logger.error(f"Error loading extension tool {tool_module}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error loading extension tools: {str(e)}")
    
    def add_tool(self, tool: BaseTool):
        """
        Add a tool to the available tools.
        
        Args:
            tool: The tool to add
        """
        try:
            if tool.name in self.available_tools:
                self.logger.warning(f"Tool {tool.name} already exists, overwriting")
            
            self.available_tools[tool.name] = tool
            self.logger.debug(f"Added tool: {tool.name}")
        except Exception as e:
            self.logger.error(f"Error adding tool {getattr(tool, 'name', 'unknown')}: {str(e)}")
    
    def get_available_tools(self) -> Dict[str, BaseTool]:
        """
        Get all available tools.
        
        Returns:
            Dictionary of available tools
        """
        return self.available_tools
    
    def get_available_tools_for_llm(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions in a format suitable for LLM.
        
        Returns:
            List of tool definitions
        """
        tools = []
        
        # Format each tool for the LLM
        for tool_name, tool in self.available_tools.items():
            try:
                # Use get_arguments_schema() instead of accessing parameters directly
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.get_arguments_schema()
                    }
                }
                tools.append(tool_def)
            except Exception as e:
                self.logger.error(f"Error formatting tool {tool_name} for LLM: {str(e)}")
        
        return tools
    
    def get_available_tools_info(self) -> str:
        """
        Get information about available tools.
        
        Returns:
            A string describing available tools
        """
        tool_info = []
        
        for tool_name, tool in self.available_tools.items():
            try:
                # Format tool information
                info = f"- {tool_name}: {tool.description}"
                tool_info.append(info)
            except Exception as e:
                self.logger.error(f"Error getting info for tool {tool_name}: {str(e)}")
        
        if not tool_info:
            return "No tools available."
        
        return "Available tools:\n" + "\n".join(tool_info)
    
    def verify_tool_exists(self, tool_name: str) -> bool:
        """
        Check if a tool exists.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if the tool exists, False otherwise
        """
        return tool_name in self.available_tools
    
    def handle_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a tool call.
        
        Args:
            tool_call: Tool call dictionary
            
        Returns:
            Result of the tool call
        """
        # Extract tool information
        tool_name = tool_call.get("name", "")
        function_args = tool_call.get("arguments", {})
        
        # Convert string arguments to dict if needed
        if isinstance(function_args, str):
            try:
                function_args = json.loads(function_args)
            except Exception as e:
                self.logger.error(f"Error parsing tool arguments: {str(e)}")
                return {
                    "tool_name": tool_name,
                    "tool_args": function_args,
                    "success": False,
                    "error": f"Invalid JSON arguments: {str(e)}"
                }
        
        # Verify the tool exists
        if not self.verify_tool_exists(tool_name):
            self.logger.error(f"Tool not found: {tool_name}")
            return {
                "tool_name": tool_name,
                "tool_args": function_args,
                "success": False,
                "error": f"Tool not found: {tool_name}"
            }
        
        # Get the tool
        tool = self.available_tools[tool_name]
        
        # Execute the tool
        try:
            self.logger.debug(f"Executing tool: {tool_name} with args: {function_args}")
            
            # Update the tool with the session state if supported
            if hasattr(tool, "update_with_session_state"):
                tool.update_with_session_state(self.session_state)
            
            # Execute the tool
            tool_result = tool.execute(**function_args)
            
            # Handle the result
            return {
                "tool_name": tool_name,
                "tool_args": function_args,
                "success": True,
                "result": tool_result
            }
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return {
                "tool_name": tool_name,
                "tool_args": function_args,
                "success": False,
                "error": str(e)
            }
    
    def process_tool_call_loop(
        self,
        llm_response: Dict[str, Any],
        process_response_fn: Callable,
        format_messages_fn: Callable,
        get_completion_fn: Callable
    ) -> Dict[str, Any]:
        """
        Process a loop of tool calls from an LLM response.
        
        Args:
            llm_response: Initial LLM response
            process_response_fn: Function to process LLM response
            format_messages_fn: Function to format messages for LLM
            get_completion_fn: Function to send to LLM
            
        Returns:
            Final processed response
        """
        # Process the LLM response
        processed_response = process_response_fn(llm_response)
        
        # Maximum number of tool call iterations
        max_iterations = 5
        current_iteration = 0
        
        # Tool call loop
        while (
            "tool_calls" in processed_response and 
            processed_response["tool_calls"] and 
            current_iteration < max_iterations
        ):
            current_iteration += 1
            self.logger.debug(f"Tool call iteration: {current_iteration}")
            
            # Handle each tool call
            tool_results = []
            for tool_call in processed_response["tool_calls"]:
                # Handle the tool call
                result = self.handle_tool_call(tool_call)
                tool_results.append(result)
            
            # Format tool results for the LLM
            tool_results_formatted = []
            for result in tool_results:
                tool_result = {
                    "id": tool_call.get("id", "tool_call_id"),
                    "type": "function",
                    "function": {
                        "name": result["tool_name"],
                        "arguments": json.dumps(result["tool_args"]),
                    }
                }
                
                if result["success"]:
                    # Add result
                    tool_result["function"]["response"] = json.dumps(result["result"])
                else:
                    # Add error
                    tool_result["function"]["response"] = json.dumps(
                        {"error": result["error"]}
                    )
                
                tool_results_formatted.append(tool_result)
            
            # Format messages for LLM
            messages, tools, tool_choice = format_messages_fn(
                content="",
                previous_messages=None,  # Use existing messages
                include_tools=True,
                tools=self.get_available_tools_for_llm()
            )
            
            # Send to LLM
            llm_response = get_completion_fn(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice
            )
            
            # Process the response
            processed_response = process_response_fn(llm_response)
        
        return processed_response
    
    def format_result(self, result: Any) -> str:
        """
        Format a tool result for display.
        
        Args:
            result: The result to format
            
        Returns:
            Formatted result string
        """
        # Handle different result types
        if isinstance(result, dict):
            try:
                return json.dumps(result, indent=2)
            except Exception:
                return str(result)
        elif isinstance(result, list):
            try:
                return json.dumps(result, indent=2)
            except Exception:
                return str(result)
        else:
            return str(result)
    
    def _convert_tool_call_to_dict(self, tool_call) -> Dict[str, Any]:
        """
        Convert a tool call object to a dictionary.
        
        Args:
            tool_call: Tool call object
            
        Returns:
            Dictionary representation of the tool call
        """
        # If it's already a dict, return it
        if isinstance(tool_call, dict):
            return tool_call
            
        # Convert to dict
        result = {}
        
        # Extract function info
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
    
    def handle_terminal_command(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a terminal command.
        
        This is a special handler that properly handles terminal commands by using
        the command executor directly.
        
        Args:
            args: Command arguments
            
        Returns:
            Command execution result
        """
        # Extract command and validation info
        command = args.get("command", "")
        explanation = args.get("explanation", "")
        
        # Special handling for terminal commands to avoid security issues
        # This is a placeholder - in a real implementation, we would:
        # 1. Validate the command against a whitelist/blacklist
        # 2. Check for dangerous operations
        # 3. Potentially restrict to certain directories
        
        # Get working directory
        cwd = args.get("cwd") or self.session_state.get("cwd")
        if cwd:
            # Convert to Path
            if not isinstance(cwd, Path):
                cwd = Path(cwd)
        
        # Execute command
        result = {}
        try:
            import subprocess
            # Execute command and capture output
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd
            )
            
            # Format result
            result = {
                "stdout": process.stdout,
                "stderr": process.stderr,
                "returncode": process.returncode,
                "success": process.returncode == 0
            }
        except Exception as e:
            # Handle execution errors
            result = {
                "stdout": "",
                "stderr": str(e),
                "returncode": 1,
                "success": False
            }
        
        # Add command info to result
        result["command"] = command
        result["explanation"] = explanation
        
        return result 