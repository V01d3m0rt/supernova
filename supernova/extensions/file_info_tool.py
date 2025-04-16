"""
SuperNova - AI-powered development assistant within the terminal.

File Info Tool - Gets information about a file in the project.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from supernova.core.tool_base import SupernovaTool, FileToolMixin


class FileInfoTool(SupernovaTool, FileToolMixin):
    """
    A tool that provides information about a file.
    """
    
    def get_name(self) -> str:
        return "file_info"
    
    def get_description(self) -> str:
        return "Get information about a file, including size, modification time, and permissions."
    
    def get_usage_examples(self) -> List[str]:
        return [
            "file_info path=src/main.py",
            "file_info path=README.md"
        ]
    
    def get_required_args(self) -> List[str]:
        return ["path"]
    
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
        if not self.validate_args(args):
            return {
                "success": False,
                "error": f"Missing required argument: 'path'"
            }
        
        # Get the file path
        file_path = args["path"]
        
        # Normalize the path
        file_path = self.normalize_path(Path(file_path), 
                                       working_dir or Path.cwd())
        
        # Check if the file exists
        if not self.validate_file_path(file_path):
            return {
                "success": False,
                "error": f"File does not exist: {file_path}"
            }
        
        # Get file information
        file_stats = file_path.stat()
        
        # Format the results
        return {
            "success": True,
            "data": {
                "path": str(file_path),
                "size": file_stats.st_size,
                "size_human": self._format_size(file_stats.st_size),
                "modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                "permissions": oct(file_stats.st_mode)[-3:],
                "is_executable": os.access(file_path, os.X_OK),
                "file_type": self._get_file_type(file_path)
            }
        }
    
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