"""
SuperNova - AI-powered development assistant within the terminal.

File Stats - A tool to gather statistics about files.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from supernova.core.tool_base import SupernovaTool, FileToolMixin


class FileStatsTool(SupernovaTool, FileToolMixin):
    """
    Tool for gathering statistics about files in a project.
    
    This tool can analyze individual files or entire directories
    to provide information like line counts, file sizes, etc.
    """
    
    def get_name(self) -> str:
        """Get the tool name."""
        return "file_stats"
    
    def get_description(self) -> str:
        """Get the tool description."""
        return "Gather statistics about files in the project, such as line counts and file sizes."
    
    def get_usage_examples(self) -> List[str]:
        """Get examples of how to use this tool."""
        return [
            "file_stats --path src/main.py",
            "file_stats --path src --extensions py,md",
            "file_stats --path . --extensions py,js,ts --recursive"
        ]
    
    def get_required_args(self) -> Dict[str, str]:
        """Get required arguments for this tool."""
        return {
            "path": "Path to a file or directory to analyze"
        }
    
    def execute(self, args: Dict[str, Any], context: Dict[str, Any], 
                working_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Execute the file stats tool.
        
        Args:
            args: Tool arguments including:
                - path: Path to file or directory
                - extensions: Optional comma-separated list of extensions to filter by
                - recursive: Optional boolean flag for recursive directory scanning
            context: Current context
            working_dir: Working directory
            
        Returns:
            Dictionary containing file statistics
        """
        path = args["path"]
        extensions = args.get("extensions", "").split(",") if "extensions" in args else None
        recursive = args.get("recursive", "").lower() in ("true", "yes", "1") if "recursive" in args else False
        
        # Resolve the path
        full_path = self._resolve_path(path, working_dir)
        
        # Check if path exists
        if not full_path.exists():
            return {
                "success": False,
                "error": f"Path does not exist: {full_path}"
            }
        
        # Get statistics
        if full_path.is_file():
            return {
                "success": True,
                "stats": self._get_file_stats(full_path)
            }
        else:  # Directory
            return {
                "success": True,
                "stats": self._get_directory_stats(full_path, extensions, recursive)
            }
    
    def _get_file_stats(self, file_path: Path) -> Dict[str, Any]:
        """
        Get statistics for a single file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file statistics
        """
        stats = {
            "name": file_path.name,
            "path": str(file_path),
            "size_bytes": file_path.stat().st_size,
            "extension": file_path.suffix.lstrip("."),
            "last_modified": file_path.stat().st_mtime
        }
        
        # Count lines for text files
        if self._is_text_file(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    stats.update({
                        "lines_total": len(lines),
                        "lines_code": sum(1 for line in lines if line.strip() and not line.strip().startswith('#')),
                        "lines_blank": sum(1 for line in lines if not line.strip()),
                        "lines_comment": sum(1 for line in lines if line.strip().startswith('#'))
                    })
            except Exception as e:
                stats["error_reading"] = str(e)
        
        return stats
    
    def _get_directory_stats(self, dir_path: Path, extensions: Optional[List[str]] = None, 
                             recursive: bool = False) -> Dict[str, Any]:
        """
        Get statistics for a directory.
        
        Args:
            dir_path: Path to the directory
            extensions: List of file extensions to include (without dot)
            recursive: Whether to scan subdirectories
            
        Returns:
            Dictionary with directory statistics
        """
        stats = {
            "name": dir_path.name,
            "path": str(dir_path),
            "file_count": 0,
            "total_size_bytes": 0,
            "files": []
        }
        
        # Function to check if a file should be included based on its extension
        def should_include(path: Path) -> bool:
            if not path.is_file():
                return False
            if not extensions:
                return True
            return path.suffix.lstrip(".").lower() in (ext.lower() for ext in extensions)
        
        # Collect files
        if recursive:
            for root, _, files in os.walk(dir_path):
                for file in files:
                    file_path = Path(root) / file
                    if should_include(file_path):
                        file_stat = self._get_file_stats(file_path)
                        stats["files"].append(file_stat)
                        stats["file_count"] += 1
                        stats["total_size_bytes"] += file_stat["size_bytes"]
        else:
            for item in dir_path.iterdir():
                if should_include(item):
                    file_stat = self._get_file_stats(item)
                    stats["files"].append(file_stat)
                    stats["file_count"] += 1
                    stats["total_size_bytes"] += file_stat["size_bytes"]
        
        # Add summary statistics for text files
        text_files = [f for f in stats["files"] if "lines_total" in f]
        if text_files:
            stats.update({
                "total_lines": sum(f["lines_total"] for f in text_files),
                "total_code_lines": sum(f.get("lines_code", 0) for f in text_files),
                "total_blank_lines": sum(f.get("lines_blank", 0) for f in text_files),
                "total_comment_lines": sum(f.get("lines_comment", 0) for f in text_files)
            })
        
        return stats
    
    def _is_text_file(self, file_path: Path) -> bool:
        """
        Determine if a file is a text file based on extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Boolean indicating if it's likely a text file
        """
        text_extensions = {
            'txt', 'py', 'js', 'ts', 'html', 'css', 'md', 'rst', 'json', 'xml',
            'yaml', 'yml', 'toml', 'sh', 'bash', 'c', 'cpp', 'h', 'hpp', 'java',
            'go', 'rs', 'rb', 'php', 'pl', 'kt', 'swift', 'cs', 'fs', 'hs'
        }
        
        return file_path.suffix.lstrip('.').lower() in text_extensions 