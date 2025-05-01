"""
SuperNova - AI-powered development assistant within the terminal.

Tool to detect and process file/folder references in user messages.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rich.console import Console
from rich.panel import Panel

from supernova.core.tool_base import SupernovaTool, FileToolMixin

console = Console()

class FileReferenceTool(SupernovaTool, FileToolMixin):
    """Tool for detecting and processing file/folder references in user messages."""
    
    def __init__(self):
        """Initialize the file reference tool."""
        super().__init__(
            name="file_reference",
            description="Process file and folder references in user messages that use @File or @Folder notation",
            required_args={
                "message": "The user message to process for file references"
            },
            optional_args={
                "working_dir": "Directory to resolve relative paths from"
            }
        )
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the schema for this tool.
        
        Returns:
            Tool schema dictionary
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The user message to process for file references"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Directory to resolve relative paths from"
                    }
                },
                "required": ["message"]
            }
        }
    
    def get_arguments_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for the tool's arguments."""
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The user message to process for file references"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Directory to resolve relative paths from"
                }
            },
            "required": ["message"]
        }
    
    def get_usage_examples(self) -> List[Dict[str, Any]]:
        """Get examples of how to use the tool."""
        return [
            {
                "description": "Process a message with file references",
                "arguments": {
                    "message": "Please check this file @File /path/to/file.txt and tell me what's in it."
                }
            },
            {
                "description": "Process a message with folder references",
                "arguments": {
                    "message": "List all the files in this folder @Folder ./my_project"
                }
            }
        ]
    
    def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None, working_dir: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Execute the file reference tool.
        
        Args:
            args: Dictionary with command arguments
            context: Optional execution context
            working_dir: Optional working directory
            
        Returns:
            Dictionary with execution results
        """
        if not isinstance(args, dict):
            return {
                "success": False, 
                "error": "Arguments must be a dictionary"
            }
            
        # Get the message from args
        message = args.get("message", "")
        args_working_dir = args.get("working_dir", "")
        
        # If working_dir is provided as a function parameter, it takes precedence
        effective_working_dir = working_dir if working_dir is not None else args_working_dir
        if not effective_working_dir:
            effective_working_dir = os.getcwd()
            
        # Convert to Path if it's a string
        if isinstance(effective_working_dir, str):
            effective_working_dir = Path(effective_working_dir)
            
        return self.process_file_references(message, effective_working_dir)
    
    def process_file_references(self, message: str, working_dir: Path) -> Dict[str, Any]:
        """
        Process file and folder references in a message.
        
        Args:
            message: The message to process
            working_dir: Directory to resolve relative paths from
            
        Returns:
            Dictionary with processing results
        """
        if not message:
            return {
                "success": False,
                "error": "No message provided"
            }
        
        # Find file references using regex
        file_references = self._find_file_references(message)
        folder_references = self._find_folder_references(message)
        
        if not file_references and not folder_references:
            return {
                "success": True,
                "references_found": False,
                "message": "No file or folder references found in the message."
            }
        
        # Process file references
        processed_files = []
        for path in file_references:
            try:
                file_path = self._resolve_path(path, working_dir)
                if file_path.exists() and file_path.is_file():
                    content = self._read_file(str(file_path))
                    file_info = {
                        "path": str(file_path),
                        "exists": True,
                        "type": "file",
                        "size": file_path.stat().st_size,
                        "content": content
                    }
                else:
                    file_info = {
                        "path": str(file_path),
                        "exists": False,
                        "type": "file",
                        "error": f"File not found: {file_path}"
                    }
                processed_files.append(file_info)
            except Exception as e:
                processed_files.append({
                    "path": path,
                    "exists": False,
                    "type": "file",
                    "error": str(e)
                })
        
        # Process folder references
        processed_folders = []
        for path in folder_references:
            try:
                folder_path = self._resolve_path(path, working_dir)
                if folder_path.exists() and folder_path.is_dir():
                    # List files and folders in the directory
                    contents = list(folder_path.iterdir())
                    files = [str(f.relative_to(folder_path)) for f in contents if f.is_file()]
                    folders = [str(f.relative_to(folder_path)) for f in contents if f.is_dir()]
                    
                    folder_info = {
                        "path": str(folder_path),
                        "exists": True,
                        "type": "folder",
                        "file_count": len(files),
                        "folder_count": len(folders),
                        "files": files,
                        "folders": folders
                    }
                else:
                    folder_info = {
                        "path": str(folder_path),
                        "exists": False,
                        "type": "folder",
                        "error": f"Folder not found: {folder_path}"
                    }
                processed_folders.append(folder_info)
            except Exception as e:
                processed_folders.append({
                    "path": path,
                    "exists": False,
                    "type": "folder",
                    "error": str(e)
                })
        
        return {
            "success": True,
            "references_found": True,
            "file_references": processed_files,
            "folder_references": processed_folders,
            "message": f"Found {len(file_references)} file references and {len(folder_references)} folder references."
        }
    
    def _find_file_references(self, message: str) -> List[str]:
        """
        Find file references in a message.
        
        Args:
            message: The message to search
            
        Returns:
            List of file paths found
        """
        pattern = r'@File\s+([^\s,;]+)'
        matches = re.findall(pattern, message)
        return matches
    
    def _find_folder_references(self, message: str) -> List[str]:
        """
        Find folder references in a message.
        
        Args:
            message: The message to search
            
        Returns:
            List of folder paths found
        """
        pattern = r'@Folder\s+([^\s,;]+)'
        matches = re.findall(pattern, message)
        return matches
    
    async def execute_async(self, args: Dict[str, Any], context: Dict[str, Any] = None, working_dir: Union[str, Path] = None) -> Dict[str, Any]:
        """
        Execute the file reference tool asynchronously.
        
        Args:
            args: Dictionary with command arguments
            context: Optional execution context
            working_dir: Optional working directory
            
        Returns:
            Dictionary with execution results
        """
        # This is a simple wrapper around the synchronous execute method
        return self.execute(args, context, working_dir)
    
    def get_name(self) -> str:
        """Get the name of the tool."""
        return self.name
    
    def get_description(self) -> str:
        """Get the description of the tool."""
        return self.description 