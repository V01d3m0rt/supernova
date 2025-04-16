"""
SuperNova - AI-powered development assistant within the terminal.

File Edit Tool - Tool for editing files in the project.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from supernova.core.tool_base import SupernovaTool, FileToolMixin


class FileEditTool(SupernovaTool, FileToolMixin):
    """
    A tool that allows editing of files within the project.
    """
    
    name = "file_edit"
    description = "Edit an existing file or create a new file with the specified content."
    
    def get_arguments_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for the tool's arguments."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit or create"
                },
                "content": {
                    "type": "string",
                    "description": "New content to write to the file"
                },
                "create_if_not_exists": {
                    "type": "boolean",
                    "description": "Create the file if it doesn't exist",
                    "default": True
                },
                "append": {
                    "type": "boolean",
                    "description": "Append to the file instead of replacing its contents",
                    "default": False
                }
            },
            "required": ["path", "content"]
        }
    
    def get_usage_examples(self) -> List[Dict[str, Any]]:
        """Get examples of how to use this tool."""
        return [
            {
                "description": "Edit an existing file",
                "arguments": {
                    "path": "src/main.py",
                    "content": "print('Hello, World!')"
                }
            },
            {
                "description": "Create a new file",
                "arguments": {
                    "path": "README.md",
                    "content": "# My Project\n\nThis is a README file.",
                    "create_if_not_exists": True
                }
            },
            {
                "description": "Append to an existing file",
                "arguments": {
                    "path": "requirements.txt",
                    "content": "pytest==7.3.1",
                    "append": True
                }
            }
        ]
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Edit a file with the given content.
        
        Args:
            path: The path to the file to edit or create
            content: The content to write to the file
            create_if_not_exists: Whether to create the file if it doesn't exist
            append: Whether to append to the file instead of replacing its contents
            working_dir: Optional working directory

        Returns:
            Dictionary with the result of the operation
        """
        # Extract arguments
        path = kwargs.get("path")
        content = kwargs.get("content")
        create_if_not_exists = kwargs.get("create_if_not_exists", True)
        append = kwargs.get("append", False)
        working_dir = kwargs.get("working_dir")
        
        if not path or not content:
            return {
                "success": False,
                "error": "Missing required arguments: path and content must be provided"
            }
        
        try:
            # Resolve the file path
            file_path = self._resolve_path(path, working_dir)
            
            # Check if the file exists
            file_exists = file_path.exists() and file_path.is_file()
            
            # If the file doesn't exist and we're not allowed to create it
            if not file_exists and not create_if_not_exists:
                return {
                    "success": False,
                    "error": f"File does not exist: {file_path}"
                }
            
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to the file
            if append and file_exists:
                # Append to the file
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write(content)
            else:
                # Create or overwrite the file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            # Return success
            action = 'created' if not file_exists else 'appended to' if append else 'updated'
            return {
                "success": True,
                "result": f"File {action}: {file_path}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error editing file: {str(e)}"
            }
    
    # Legacy method implementations for backward compatibility
    def get_name(self) -> str:
        return self.name
        
    def get_description(self) -> str:
        return self.description
        
    def get_required_args(self) -> Dict[str, str]:
        return {
            "path": "Path to the file to edit or create",
            "content": "New content to write to the file"
        } 