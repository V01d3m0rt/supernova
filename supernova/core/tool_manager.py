"""
SuperNova - AI-powered development assistant within the terminal.

Tool Manager - Responsible for loading, registering, and managing tools.
"""

import importlib
import importlib.util
import inspect
import os
import sys
import pkgutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type, Any, Union

from rich.console import Console
from supernova.core.tool_base import SupernovaTool

# Set up logging
logger = logging.getLogger(__name__)
console = Console()

# TODO: VS Code Integration - Consider creating VSCodeTool base class or mixin for VS Code specific tools


class ToolManager:
    """
    Tool Manager - Handles loading, registering, and execution of tools.
    
    This class is responsible for:
    1. Discovering and dynamically loading tool modules
    2. Registering tool instances
    3. Providing access to available tools
    4. Executing tool requests
    5. Managing tool lifecycle
    
    Tools are discovered from the specified package path and dynamically loaded.
    Each tool is an instance of a class that inherits from SupernovaTool.
    """
    
    def __init__(self):
        """Initialize the tool manager."""
        # Initialize tools
        self._tools = {}
        
        # Register core tools
        from supernova.tools.terminal_command_tool import TerminalCommandTool
        # Disabled other core tools for now and only using terminal_command
        # from supernova.tools.file_tool import FileTool
        # from supernova.tools.file_create_tool import FileCreateTool
        # from supernova.tools.file_info_tool import FileInfoTool
        # from supernova.tools.file_stats_tool import FileStatsTool
        # from supernova.tools.system_tool import SystemTool
        # from supernova.tools.example_tool import ExampleTool
        
        # Register only terminal command tool
        self.register_tool(TerminalCommandTool())
        
        # Disabled other core tools
        # self.register_tool(FileTool())
        # self.register_tool(FileCreateTool())
        # self.register_tool(FileInfoTool()) 
        # self.register_tool(FileStatsTool())
        # self.register_tool(SystemTool())
        # self.register_tool(ExampleTool())

    def load_extension_tools(self) -> None:
        """
        Load additional tools from the extensions directory.
        
        This method:
        1. Looks for tool modules in the extensions directory
        2. Imports and instantiates tools found there
        3. Registers them with the tool manager
        """
        # Disabled extension tools loading for now
        # Only using terminal_command tool
        return
    
    def discover_tools(self, package_path: str = "supernova.extensions") -> List[str]:
        """
        Discover and load all tools in the specified package.
        
        This method scans the given package for modules containing tool classes
        that inherit from SupernovaTool. Each discovered tool is instantiated
        and registered with the tool manager.
        
        Args:
            package_path: Dotted path to the package containing tools
            
        Returns:
            List of tool names that were successfully loaded
            
        Raises:
            ImportError: If the package cannot be imported
            AttributeError: If the package does not have a proper structure
        """
        loaded_tools = []
        try:
            package = importlib.import_module(package_path)
            
            # Get the path to the package
            if not hasattr(package, "__path__"):
                logger.warning(f"Package {package_path} does not have a __path__ attribute")
                return loaded_tools
                
            # Iterate through all modules in the package
            for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
                # Skip packages, only load modules
                if is_pkg:
                    continue
                    
                # Import the module using the correct path format
                module_path = f"{package_path}.{module_name}"
                try:
                    logger.debug(f"Loading module {module_path}")
                    module = importlib.import_module(module_path)
                    
                    # Find all classes in the module that inherit from SupernovaTool
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, SupernovaTool) and 
                            obj != SupernovaTool):
                            
                            # Create an instance and register it
                            try:
                                tool_instance = obj()
                                tool_name = tool_instance.get_name()
                                if self.register_tool(tool_instance):
                                    loaded_tools.append(tool_name)
                                    logger.info(f"Loaded tool: {tool_name}")
                            except Exception as e:
                                logger.error(f"Error instantiating tool {name}: {str(e)}")
                            
                except Exception as e:
                    logger.error(f"Error loading tool module {module_path}: {str(e)}")
                    console.print(f"[yellow]Warning:[/yellow] Error loading tool module {module_path}: {str(e)}")
        except ImportError as e:
            logger.error(f"Error importing package {package_path}: {str(e)}")
            console.print(f"[red]Error:[/red] Could not import tool package {package_path}: {str(e)}")
                    
        return loaded_tools
    
    # TODO: VS Code Integration - Add method to discover VS Code specific tools
    # def discover_vscode_tools(self) -> List[str]:
    #     """
    #     Discover and load VS Code specific tools.
    #     
    #     Returns:
    #         List of VS Code tool names that were successfully loaded
    #     """
    #     # Implementation would be similar to discover_tools but look for VSCodeTool subclasses
    #     pass
    
    def register_tool(self, tool: SupernovaTool) -> bool:
        """
        Register a tool with the manager.
        
        Adds a tool instance to the internal registry, making it available
        for execution. Tools are indexed by their name, which must be unique.
        
        Args:
            tool: Tool instance to register
            
        Returns:
            True if successfully registered, False if already exists or invalid
            
        Raises:
            ValueError: If the tool is None or doesn't implement required methods
        """
        if tool is None:
            logger.error("Attempted to register None as a tool")
            raise ValueError("Cannot register None as a tool")
            
        try:
            tool_name = tool.get_name()
            if not tool_name:
                logger.error("Tool has empty name")
                return False
                
            if tool_name in self._tools:
                logger.warning(f"Tool {tool_name} is already registered")
                return False
                
            self._tools[tool_name] = tool
            logger.debug(f"Registered tool: {tool_name}")
            return True
        except Exception as e:
            logger.error(f"Error registering tool: {str(e)}")
            return False
        
    def get_tool(self, name: str) -> Optional[SupernovaTool]:
        """
        Get a tool by name.
        
        Retrieves a tool instance from the registry by its name.
        
        Args:
            name: Name of the tool to retrieve
            
        Returns:
            Tool instance or None if not found
        """
        if not name:
            logger.warning("Attempted to get tool with empty name")
            return None
            
        tool = self._tools.get(name)
        if tool is None:
            logger.debug(f"Tool not found: {name}")
        return tool
        
    def get_all_tools(self) -> Dict[str, SupernovaTool]:
        """
        Get all registered tools.
        
        Returns:
            Dictionary of tool instances by name
        """
        return self._tools.copy()
        
    def get_tool_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all registered tools.
        
        Returns detailed information about each registered tool,
        including name, description, usage examples, and required arguments.
        This information is used to present tools to users and the LLM.
        
        Returns:
            List of dictionaries with tool info
        """
        tool_info = []
        for name, tool in self._tools.items():
            try:
                tool_info.append({
                    "name": name,
                    "description": tool.get_description(),
                    "usage_examples": tool.get_usage_examples(),
                    "required_args": tool.get_required_args()
                })
            except Exception as e:
                logger.error(f"Error getting info for tool {name}: {str(e)}")
                # Include partial info with error note
                tool_info.append({
                    "name": name,
                    "description": f"Error retrieving tool info: {str(e)}",
                    "usage_examples": [],
                    "required_args": {}
                })
        return tool_info
        
    def execute_tool(self, tool_name: str, args: Dict[str, Any], context: Dict[str, Any], working_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Execute a tool with the given arguments.
        
        Args:
            tool_name: Name of the tool to execute
            args: Dictionary of arguments to pass to the tool
            context: Dictionary containing context information like session state
            working_dir: Working directory for tool execution
            
        Returns:
            Dictionary containing the result of tool execution
        """
        # Get the tool
        tool = self.get_tool(tool_name)
        if tool is None:
            logger.error(f"Tool not found: {tool_name}")
            return {
                "success": False,
                "error": f"Tool not found: {tool_name}"
            }
        
        # Validate arguments
        validation = tool.validate_args(args)
        if not validation["valid"]:
            missing_args = ", ".join(validation["missing"])
            logger.error(f"Missing required arguments for tool {tool_name}: {missing_args}")
            return {
                "success": False,
                "error": f"Missing required arguments: {missing_args}"
            }
            
        # Execute the tool with the provided arguments
        try:
            # Pass the arguments as keyword arguments
            result = tool.execute(**args)
            if "working_dir" in result:
                context["working_dir"] = result["working_dir"]
            return result
        except TypeError as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return {
                "success": False,
                "error": f"Error executing tool {tool_name}: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error executing tool {tool_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"Unexpected error executing tool {tool_name}: {str(e)}"
            }

    def list_tools(self) -> List[SupernovaTool]:
        """
        Get a list of all available tools.
        
        Returns:
            List of tool instances
        """
        return list(self._tools.values())
    
    def get_tools(self) -> Dict[str, SupernovaTool]:
        """
        Get a dictionary of all available tools.
        
        Returns:
            Dictionary mapping tool names to tool instances
        """
        return self._tools

    async def get_available_tools_for_llm(self, session_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get the available tools formatted for the LLM.
        
        Args:
            session_state: Current session state
            
        Returns:
            List of tool definitions formatted for the LLM
        """
        tools_for_llm = []
        
        # Get tool info and iterate through each tool
        tool_info = self.get_tool_info()
        
        for info in tool_info:
            tool_name = info["name"]
            description = info["description"]
            
            # Get the tool instance to access its schema
            tool = self.get_tool(tool_name)
            if not tool:
                continue
                
            try:
                # Try to get the arguments schema from the tool
                parameters = tool.get_arguments_schema()
                
                # If the schema doesn't have the right structure, create it
                if not isinstance(parameters, dict) or "type" not in parameters:
                    # Fall back to a simplified schema based on required args
                    parameters = {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                    
                    # Add required arguments based on the tool's required_args
                    required_args = info["required_args"]
                    if isinstance(required_args, dict):
                        # Handle Dict[str, str] format (name: description)
                        for name, desc in required_args.items():
                            parameters["properties"][name] = {
                                "type": "string",
                                "description": desc
                            }
                            parameters["required"].append(name)
                    elif isinstance(required_args, list):
                        # Handle List[str] format (list of argument names)
                        for arg in required_args:
                            parameters["properties"][arg] = {
                                "type": "string",
                                "description": f"The {arg} parameter"
                            }
                            parameters["required"].extend(required_args)
                
                # Create tool schema - follow OpenAI's format exactly
                tool_schema = {
                    "function": {
                        "name": tool_name,
                        "description": description,
                        "parameters": parameters
                    },
                    "type": "function"
                }
                
                tools_for_llm.append(tool_schema)
            except Exception as e:
                logger.error(f"Error generating schema for tool {tool_name}: {str(e)}")
                # Skip this tool if we can't generate its schema
                continue
        
        return tools_for_llm
    
    async def get_tool_info_async(self) -> List[Dict[str, Any]]:
        """
        Get information about all registered tools (async version).
        
        Returns detailed information about each registered tool,
        including name, description, usage examples, and required arguments.
        This information is used to present tools to users and the LLM.
        
        Returns:
            List of dictionaries with tool info
        """
        # Call the synchronous version
        return self.get_tool_info()
        
    async def list_tools_async(self) -> List[SupernovaTool]:
        """
        Get a list of all available tools (async version).
        
        Returns:
            List of tool instances
        """
        # Call the synchronous version
        return self.list_tools()
        
    async def execute_tool(
        self, 
        tool_name: str, 
        args: Dict[str, Any], 
        session_state: Dict[str, Any],
        working_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool by name (async version).
        
        This method handles:
        1. Retrieving the tool by name
        2. Validating the provided arguments
        3. Executing the tool with the provided context
        4. Handling any exceptions that occur during execution
        
        Args:
            tool_name: Name of the tool to execute
            args: Arguments to pass to the tool
            session_state: Current session state
            working_dir: Working directory for relative path resolution
            
        Returns:
            Result dictionary with at least a 'success' key indicating execution status
        """
        logger.debug(f"Executing tool: {tool_name} with args: {args}")
        
        if not tool_name:
            return {
                "success": False,
                "error": "Tool name cannot be empty"
            }
            
        tool = self.get_tool(tool_name)
        if not tool:
            logger.warning(f"Tool not found: {tool_name}")
            return {
                "success": False,
                "error": f"Tool not found: {tool_name}"
            }
            
        # Validate arguments
        try:
            validation = tool.validate_args(args)
            if not validation["valid"]:
                missing = ', '.join(validation['missing'])
                logger.warning(f"Missing required arguments for tool {tool_name}: {missing}")
                return {
                    "success": False,
                    "error": f"Missing required arguments: {missing}",
                    "missing_args": validation['missing']
                }
        except Exception as e:
            logger.error(f"Error validating arguments for tool {tool_name}: {str(e)}")
            return {
                "success": False,
                "error": f"Error validating arguments: {str(e)}"
            }
            
        # Create context dictionary from session state
        # Prioritize using initial_directory when available
        working_directory = working_dir
        if not working_directory:
            # Prefer initial_directory over cwd from session state
            if "initial_directory" in session_state:
                working_directory = session_state.get("initial_directory")
            else:
                working_directory = session_state.get("cwd", str(Path.cwd()))
                
        context = {
            "session_state": session_state,
            "cwd": working_directory
        }
            
        # Execute the tool
        try:
            # Check if the tool has an async_execute method
            if hasattr(tool, "async_execute") and callable(getattr(tool, "async_execute")):
                result = await tool.async_execute(args, context, str(working_directory))
            else:
                # Fall back to synchronous execution
                result = tool.execute(args, context, working_directory)
            
            # Ensure result has a success key
            if "success" not in result:
                logger.warning(f"Tool {tool_name} did not return a success status, assuming success")
                result["success"] = True
                
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return {
                "success": False,
                "error": f"Error executing tool: {str(e)}"
            }


# Singleton instance
_manager = None


def get_manager() -> ToolManager:
    """
    Get the tool manager instance.
    
    Returns the singleton instance of the ToolManager, creating it if needed.
    
    Returns:
        ToolManager instance
    """
    global _manager
    if _manager is None:
        _manager = ToolManager()
    return _manager


# TODO: VS Code Integration - Add function to create VS Code tool extensions
# def register_vscode_tool_command(tool_name: str) -> None:
#     """
#     Register a tool as a VS Code command.
#     
#     Args:
#         tool_name: Name of the tool to register
#     """
#     pass 
#     pass 