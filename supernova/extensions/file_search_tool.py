"""
SuperNova - AI-powered development assistant within the terminal.

File Search Tool - Search inside files for specific patterns.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from supernova.core.tool_base import SupernovaTool, FileToolMixin


class FileSearchTool(SupernovaTool, FileToolMixin):
    """
    A tool that searches inside files for specific patterns.
    """
    
    name = "file_search"
    description = "Search inside files for specific patterns using regular expressions."
    
    def get_arguments_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for the tool's arguments."""
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The pattern to search for (regular expression)"
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths or directories to search in"
                },
                "path": {
                    "type": "string",
                    "description": "Single file path or directory to search in (alternative to paths)"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File pattern to match (e.g., '*.py' for Python files)",
                    "default": "*"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 50
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "Whether to ignore case when matching",
                    "default": False
                }
            },
            "required": ["pattern"]
        }
    
    def get_usage_examples(self) -> List[Dict[str, Any]]:
        """Get examples of how to use this tool."""
        return [
            {
                "description": "Search for a pattern in a specific file",
                "arguments": {
                    "pattern": "def get_name",
                    "path": "supernova/core/tool_base.py"
                }
            },
            {
                "description": "Search for a pattern in all Python files",
                "arguments": {
                    "pattern": "class SupernovaTool",
                    "path": "supernova",
                    "file_pattern": "*.py"
                }
            },
            {
                "description": "Search for a pattern in multiple files",
                "arguments": {
                    "pattern": "import os",
                    "paths": ["supernova/core", "supernova/tools"],
                    "file_pattern": "*.py"
                }
            }
        ]
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Search inside files for specific patterns.
        
        Args:
            pattern: The pattern to search for (regular expression)
            paths: List of file paths or directories to search in
            path: Single file path or directory to search in (alternative to paths)
            file_pattern: File pattern to match (e.g., '*.py' for Python files)
            max_results: Maximum number of results to return
            ignore_case: Whether to ignore case when matching
            working_dir: Optional working directory

        Returns:
            Dictionary with the search results
        """
        # Extract arguments
        pattern = kwargs.get("pattern")
        paths = kwargs.get("paths", [])
        path = kwargs.get("path")
        file_pattern = kwargs.get("file_pattern", "*")
        max_results = kwargs.get("max_results", 50)
        ignore_case = kwargs.get("ignore_case", False)
        working_dir = kwargs.get("working_dir")
        
        if not pattern:
            return {
                "success": False,
                "error": "Missing required argument: pattern must be provided"
            }
        
        # Handle both path and paths
        if path and not paths:
            paths = [path]
        elif not paths:
            # Default to current directory if neither is provided
            paths = ["."]
        
        try:
            # Compile the regular expression
            flags = re.IGNORECASE if ignore_case else 0
            regex = re.compile(pattern, flags)
            
            # Resolve all paths
            resolved_paths = [self._resolve_path(p, working_dir) for p in paths]
            
            # Initialize results
            results = []
            files_searched = 0
            
            # Process each path
            for base_path in resolved_paths:
                if base_path.is_file():
                    # If the path is a file, search directly
                    files_searched += 1
                    self._search_file(base_path, regex, results, max_results)
                elif base_path.is_dir():
                    # If the path is a directory, find matching files and search them
                    for file_path in base_path.rglob(file_pattern):
                        if file_path.is_file():
                            files_searched += 1
                            if self._search_file(file_path, regex, results, max_results):
                                # If we've reached the maximum results, stop searching
                                break
                    
                # If we've reached the maximum results, stop searching
                if len(results) >= max_results:
                    break
            
            return {
                "success": True,
                "result": {
                    "matches": results[:max_results],
                    "total_matches": len(results),
                    "files_searched": files_searched,
                    "pattern": pattern,
                    "truncated": len(results) > max_results
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error searching files: {str(e)}"
            }
    
    def _search_file(self, file_path: Path, regex: re.Pattern, results: List[Dict[str, Any]], max_results: int) -> bool:
        """
        Search a single file for the pattern.
        
        Args:
            file_path: Path to the file to search
            regex: Compiled regular expression to search for
            results: List to append results to
            max_results: Maximum number of results to gather
            
        Returns:
            True if max_results reached, False otherwise
        """
        try:
            # Skip binary files and very large files
            if self._is_binary(file_path) or file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB limit
                return False
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f, 1):
                    for match in regex.finditer(line):
                        results.append({
                            "file": str(file_path),
                            "line_number": i,
                            "line": line.rstrip(),
                            "start": match.start(),
                            "end": match.end(),
                            "match": match.group(0)
                        })
                        
                        if len(results) >= max_results:
                            return True
        except Exception as e:
            # If there's an error reading the file, just skip it
            pass
            
        return False
    
    def _is_binary(self, file_path: Path) -> bool:
        """
        Check if a file is binary (non-text).
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if the file appears to be binary, False otherwise
        """
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk  # If null bytes are present, likely binary
        except Exception:
            return False
    
    # Legacy method implementations for backward compatibility
    def get_name(self) -> str:
        return self.name
        
    def get_description(self) -> str:
        return self.description
        
    def get_required_args(self) -> Dict[str, str]:
        return {
            "pattern": "The pattern to search for (regular expression)"
        } 