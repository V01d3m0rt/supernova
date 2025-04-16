"""
SuperNova - AI-powered development assistant within the terminal.

Example Tool - A sample tool to demonstrate the tool extension system.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rich.console import Console

from supernova.core.tool_base import FileToolMixin, SupernovaTool

console = Console()


class ExampleTool(SupernovaTool, FileToolMixin):
    """
    An example tool that demonstrates the tool extension system.
    
    This tool simply echoes back the provided message and demonstrates
    how to implement a SuperNova tool.
    """
    
    def get_name(self) -> str:
        """Get the name of the tool."""
        return "example"
    
    def get_description(self) -> str:
        """Get a description of what the tool does."""
        return "A sample tool that echoes back a message and lists files in a directory."
    
    def get_usage_examples(self) -> List[str]:
        """Get examples of how to use the tool."""
        return [
            "example --message 'Hello, world!'",
            "example --message 'List files' --dir '.'"
        ]
    
    def get_required_args(self) -> Dict[str, str]:
        """Get the required arguments for this tool."""
        return {
            "message": "The message to echo back"
        }
    
    def execute(self, args: Dict[str, Any], context: Dict[str, Any], 
                working_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Execute the tool with the given arguments.
        
        Args:
            args: Arguments passed to the tool
            context: Current context (session state, project info, etc.)
            working_dir: Working directory for the tool execution
            
        Returns:
            A dictionary with the results of the tool execution
        """
        # Check if we have all required args
        if not self.validate_args(args):
            return {
                "success": False,
                "error": "Missing required arguments",
                "required_args": list(self.get_required_args().keys())
            }
        
        # Get the message to echo back
        message = args.get("message", "")
        
        result = {
            "success": True,
            "message": message,
            "echoed": f"You said: {message}"
        }
        
        # If a directory is specified, list its contents
        if "dir" in args:
            dir_path = args["dir"]
            resolved_path = self._resolve_path(dir_path, working_dir)
            
            if self._dir_exists(dir_path, working_dir):
                # List files in the directory
                files = [f.name for f in resolved_path.iterdir() if f.is_file()]
                dirs = [d.name for d in resolved_path.iterdir() if d.is_dir()]
                
                result["dir_contents"] = {
                    "path": str(resolved_path),
                    "files": files,
                    "directories": dirs
                }
            else:
                result["dir_error"] = f"Directory '{dir_path}' does not exist"
        
        return result


class FileInfoTool(SupernovaTool, FileToolMixin):
    """Tool for getting information about a file."""
    
    def get_name(self) -> str:
        """Get the name of the tool."""
        return "file"
    
    def get_description(self) -> str:
        """Get the description of the tool."""
        return "Get information about a file or directory"
    
    def get_usage_examples(self) -> List[str]:
        """Get examples of how to use the tool."""
        return [
            "file info path/to/file.txt",
            "file list path/to/directory",
            "file find pattern path/to/directory"
        ]
    
    def get_required_args(self) -> List[str]:
        """Get the list of required arguments."""
        return ["action", "path"]
    
    def validate_args(self, args: Dict[str, Any]) -> bool:
        """Validate the arguments for the tool."""
        if "action" not in args:
            return False
        
        if args["action"] not in ["info", "list", "find"]:
            return False
        
        if "path" not in args:
            return False
        
        return True
    
    def execute(
        self,
        args: Dict[str, Any],
        context: Dict[str, Any],
        working_dir: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Execute the tool.
        
        Args:
            args: Arguments for the tool
            context: Context information
            working_dir: Working directory
            
        Returns:
            Result of the tool execution
        """
        action = args["action"]
        path = args["path"]
        
        # Normalize the path
        norm_path = self.normalize_path(path, working_dir)
        
        if action == "info":
            return self._get_file_info(norm_path)
        elif action == "list":
            return self._list_directory(norm_path)
        elif action == "find":
            pattern = args.get("pattern", "*")
            return self._find_files(norm_path, pattern)
        else:
            return {"error": f"Unknown action '{action}'"}
    
    def _get_file_info(self, path: Path) -> Dict[str, Any]:
        """
        Get information about a file.
        
        Args:
            path: Path to the file
            
        Returns:
            File information
        """
        try:
            if not path.exists():
                return {"error": f"File/directory not found: {path}"}
            
            stats = path.stat()
            
            info = {
                "path": str(path),
                "absolute_path": str(path.absolute()),
                "name": path.name,
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
                "size": stats.st_size,
                "last_modified": time.ctime(stats.st_mtime),
                "last_accessed": time.ctime(stats.st_atime),
                "created": time.ctime(stats.st_ctime),
            }
            
            if path.is_file():
                info["extension"] = path.suffix
            
            return {"result": info}
        
        except Exception as e:
            return {"error": f"Error getting file info: {str(e)}"}
    
    def _list_directory(self, path: Path) -> Dict[str, Any]:
        """
        List contents of a directory.
        
        Args:
            path: Path to the directory
            
        Returns:
            Directory contents
        """
        try:
            if not path.exists():
                return {"error": f"Directory not found: {path}"}
            
            if not path.is_dir():
                return {"error": f"Not a directory: {path}"}
            
            # Get all files and directories
            entries = list(path.iterdir())
            
            # Group by type
            files = [entry.name for entry in entries if entry.is_file()]
            dirs = [entry.name for entry in entries if entry.is_dir()]
            
            return {
                "result": {
                    "path": str(path),
                    "files": files,
                    "directories": dirs,
                    "total_files": len(files),
                    "total_dirs": len(dirs)
                }
            }
        
        except Exception as e:
            return {"error": f"Error listing directory: {str(e)}"}
    
    def _find_files(self, path: Path, pattern: str) -> Dict[str, Any]:
        """
        Find files matching a pattern.
        
        Args:
            path: Path to search in
            pattern: Glob pattern to match
            
        Returns:
            Matching files
        """
        try:
            if not path.exists():
                return {"error": f"Directory not found: {path}"}
            
            if not path.is_dir():
                return {"error": f"Not a directory: {path}"}
            
            # Find matching files
            matches = list(path.glob(pattern))
            
            return {
                "result": {
                    "path": str(path),
                    "pattern": pattern,
                    "matches": [str(match.relative_to(path)) for match in matches],
                    "total_matches": len(matches)
                }
            }
        
        except Exception as e:
            return {"error": f"Error finding files: {str(e)}"}


class SystemInfoTool(SupernovaTool):
    """Tool for getting information about the system."""
    
    def get_name(self) -> str:
        """Get the name of the tool."""
        return "system"
    
    def get_description(self) -> str:
        """Get the description of the tool."""
        return "Get information about the system"
    
    def get_usage_examples(self) -> List[str]:
        """Get examples of how to use the tool."""
        return [
            "system info",
            "system env VARIABLE_NAME"
        ]
    
    def get_required_args(self) -> List[str]:
        """Get the list of required arguments."""
        return ["action"]
    
    def validate_args(self, args: Dict[str, Any]) -> bool:
        """Validate the arguments for the tool."""
        if "action" not in args:
            return False
        
        if args["action"] not in ["info", "env"]:
            return False
        
        return True
    
    def execute(
        self,
        args: Dict[str, Any],
        context: Dict[str, Any],
        working_dir: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Execute the tool.
        
        Args:
            args: Arguments for the tool
            context: Context information
            working_dir: Working directory
            
        Returns:
            Result of the tool execution
        """
        action = args["action"]
        
        if action == "info":
            return self._get_system_info()
        elif action == "env":
            var_name = args.get("var", "")
            return self._get_env_var(var_name)
        else:
            return {"error": f"Unknown action '{action}'"}
    
    def _get_system_info(self) -> Dict[str, Any]:
        """
        Get information about the system.
        
        Returns:
            System information
        """
        try:
            import platform
            import sys
            
            info = {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": sys.version,
                "python_implementation": platform.python_implementation(),
                "python_compiler": platform.python_compiler(),
                "current_directory": os.getcwd()
            }
            
            return {"result": info}
        
        except Exception as e:
            return {"error": f"Error getting system info: {str(e)}"}
    
    def _get_env_var(self, var_name: str) -> Dict[str, Any]:
        """
        Get an environment variable.
        
        Args:
            var_name: Name of the environment variable
            
        Returns:
            Environment variable value
        """
        try:
            if not var_name:
                # Return all environment variables if no name is specified
                return {
                    "result": {
                        "variables": dict(os.environ)
                    }
                }
            
            # Get the specific environment variable
            value = os.environ.get(var_name)
            
            if value is None:
                return {"error": f"Environment variable '{var_name}' not found"}
            
            return {
                "result": {
                    "name": var_name,
                    "value": value
                }
            }
        
        except Exception as e:
            return {"error": f"Error getting environment variable: {str(e)}"} 