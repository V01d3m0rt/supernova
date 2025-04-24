"""
SuperNova - AI-powered development assistant within the terminal.

File Info Tool - Gets information about a file in the project.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from supernova.core.tool_base import SupernovaTool, FileToolMixin


class FileInfoTool(SupernovaTool, FileToolMixin):
    """
    A tool that provides information about a file.
    """
    
    def __init__(self):
        """Initialize the file info tool."""
        super().__init__(
            name="file_info",
            description="Get information about a file, including size, modification time, and permissions.",
            required_args={
                "path": "Path to the file to get information about"
            },
            optional_args={}
        )
    
    def get_usage_examples(self) -> List[str]:
        """Get examples of how to use the tool."""
        return [
            "file_info path=src/main.py",
            "file_info path=README.md"
        ]
    
    def execute(self, args: Dict[str, Any], context: Dict[str, Any], 
                working_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Get information about the specified file.
        
        Args:
            args: Must contain 'path' key with the file path
            context: Session context
            working_dir: Current working directory
            
        Returns:
            Dictionary with file information
        """
        # Validate arguments
        validation = self.validate_args(args)
        if not validation["valid"]:
            return self._create_standard_response(
                success=False,
                error=validation.get("error", "Missing required argument: 'path'")
            )
        
        # Get the file path
        file_path = args["path"]
        
        try:
            # Normalize the path
            norm_path = self.normalize_path(file_path, working_dir)
            
            # Use the _get_file_info method from FileToolMixin to get basic file info
            file_info = self._get_file_info(norm_path)
            
            if not file_info.get("exists", False):
                return self._create_standard_response(
                    success=False,
                    error=f"File does not exist: {norm_path}",
                    path=str(norm_path)
                )
            
            if not file_info.get("is_file", False):
                return self._create_standard_response(
                    success=False,
                    error=f"Path is not a file: {norm_path}",
                    path=str(norm_path),
                    is_directory=file_info.get("is_dir", False)
                )
            
            # Add additional formatted information
            file_info.update({
                "size_human": self._format_size(file_info.get("size", 0)),
                "modified_iso": datetime.fromtimestamp(file_info.get("modified", 0)).isoformat(),
                "created_iso": datetime.fromtimestamp(file_info.get("created", 0)).isoformat(),
                "is_executable": os.access(norm_path, os.X_OK),
                "file_type": self._get_file_type(norm_path)
            })
            
            return self._create_standard_response(
                success=True,
                file_info=file_info
            )
            
        except PermissionError as e:
            return self._create_standard_response(
                success=False,
                error=f"Permission denied: {str(e)}",
                path=str(file_path)
            )
        except Exception as e:
            return self._create_standard_response(
                success=False,
                error=str(e),
                path=str(file_path)
            )
    
    async def execute_async(self, args: Dict[str, Any], context: Dict[str, Any] = None, 
                          working_dir: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Execute the tool asynchronously.
        
        Args:
            args: Tool arguments
            context: Execution context
            working_dir: Working directory
            
        Returns:
            Result of the file information request
        """
        # Default implementation runs synchronous version
        return self.execute(args, context or {}, working_dir)
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in a human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024 or unit == 'TB':
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
    
    def _get_file_type(self, file_path: Path) -> str:
        """Get the file type based on extension."""
        extension = file_path.suffix.lower()
        
        # Map common extensions to file types
        extension_map = {
            # Code files
            '.py': 'Python Source',
            '.js': 'JavaScript Source',
            '.ts': 'TypeScript Source',
            '.java': 'Java Source',
            '.c': 'C Source',
            '.cpp': 'C++ Source',
            '.h': 'C/C++ Header',
            '.go': 'Go Source',
            '.rb': 'Ruby Source',
            '.php': 'PHP Source',
            '.rs': 'Rust Source',
            
            # Data files
            '.json': 'JSON Data',
            '.yml': 'YAML Data',
            '.yaml': 'YAML Data',
            '.xml': 'XML Data',
            '.csv': 'CSV Data',
            
            # Text files
            '.txt': 'Text File',
            '.md': 'Markdown File',
            '.rst': 'reStructuredText File',
            
            # Configuration files
            '.toml': 'TOML Configuration',
            '.ini': 'INI Configuration',
            '.cfg': 'Configuration File',
            '.conf': 'Configuration File',
            
            # Other common files
            '.html': 'HTML Document',
            '.css': 'CSS Stylesheet',
            '.scss': 'SASS Stylesheet',
            '.sh': 'Shell Script',
            '.bat': 'Windows Batch File',
            '.ps1': 'PowerShell Script',
        }
        
        return extension_map.get(extension, f"File ({extension or 'no extension'})") 