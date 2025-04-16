"""
SuperNova - AI-powered development assistant within the terminal.

Folder Search Tool - Search for folders in the project.
"""

import os
import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from supernova.core.tool_base import SupernovaTool, FileToolMixin


class FolderSearchTool(SupernovaTool, FileToolMixin):
    """
    A tool that searches for folders within the project.
    """
    
    name = "folder_search"
    description = "Search for folders in the project based on name patterns."
    
    def get_arguments_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for the tool's arguments."""
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The pattern to match folder names against (supports glob patterns)"
                },
                "base_path": {
                    "type": "string",
                    "description": "Base directory to start search from",
                    "default": "."
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum depth to search (0 for unlimited)",
                    "default": 0
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 50
                },
                "follow_symlinks": {
                    "type": "boolean",
                    "description": "Whether to follow symbolic links",
                    "default": False
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Whether to include hidden folders (starting with .)",
                    "default": False
                }
            },
            "required": ["pattern"]
        }
    
    def get_usage_examples(self) -> List[Dict[str, Any]]:
        """Get examples of how to use this tool."""
        return [
            {
                "description": "Find all folders named 'tests' in the project",
                "arguments": {
                    "pattern": "tests",
                    "base_path": "."
                }
            },
            {
                "description": "Find all folders that start with 'super' up to 2 levels deep",
                "arguments": {
                    "pattern": "super*",
                    "base_path": ".",
                    "max_depth": 2
                }
            },
            {
                "description": "Find all folders that contain 'extension' and include hidden folders",
                "arguments": {
                    "pattern": "*extension*",
                    "include_hidden": True
                }
            }
        ]
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Search for folders in the project.
        
        Args:
            pattern: The pattern to match folder names against (supports glob patterns)
            base_path: Base directory to start search from
            max_depth: Maximum depth to search (0 for unlimited)
            max_results: Maximum number of results to return
            follow_symlinks: Whether to follow symbolic links
            include_hidden: Whether to include hidden folders (starting with .)
            working_dir: Optional working directory

        Returns:
            Dictionary with the search results
        """
        # Extract arguments
        pattern = kwargs.get("pattern")
        base_path = kwargs.get("base_path", ".")
        max_depth = kwargs.get("max_depth", 0)
        max_results = kwargs.get("max_results", 50)
        follow_symlinks = kwargs.get("follow_symlinks", False)
        include_hidden = kwargs.get("include_hidden", False)
        working_dir = kwargs.get("working_dir")
        
        if not pattern:
            return {
                "success": False,
                "error": "Missing required argument: pattern must be provided"
            }
        
        try:
            # Resolve the base path
            resolved_base_path = self._resolve_path(base_path, working_dir)
            
            # Check if the base path exists and is a directory
            if not resolved_base_path.exists() or not resolved_base_path.is_dir():
                return {
                    "success": False,
                    "error": f"Base path does not exist or is not a directory: {resolved_base_path}"
                }
            
            # Find matching folders
            results = []
            
            # Traverse the directory tree
            def walk_dirs(current_path, current_depth=0):
                # Skip if we've reached the maximum depth
                if max_depth > 0 and current_depth >= max_depth:
                    return
                
                # Skip if we've found enough results
                if len(results) >= max_results:
                    return
                
                try:
                    # List entries in the current directory
                    entries = list(os.scandir(current_path))
                    
                    # First process directories at this level
                    for entry in entries:
                        # Skip if we've found enough results
                        if len(results) >= max_results:
                            return
                        
                        try:
                            # Skip if not a directory
                            if not entry.is_dir(follow_symlinks=follow_symlinks):
                                continue
                            
                            # Skip hidden directories if not included
                            if not include_hidden and entry.name.startswith('.'):
                                continue
                            
                            # Check if the name matches the pattern
                            if fnmatch.fnmatch(entry.name, pattern):
                                # Add to results
                                dir_path = Path(entry.path)
                                results.append({
                                    "path": str(dir_path),
                                    "name": entry.name,
                                    "depth": current_depth,
                                    "absolute_path": str(dir_path.absolute()),
                                    "parent": str(dir_path.parent),
                                    "is_symlink": entry.is_symlink()
                                })
                            
                            # Recursively search subdirectories
                            walk_dirs(entry.path, current_depth + 1)
                        except PermissionError:
                            # Skip directories we can't access
                            continue
                except PermissionError:
                    # Skip directories we can't access
                    return
            
            # Start the search
            walk_dirs(resolved_base_path)
            
            return {
                "success": True,
                "result": {
                    "folders": results[:max_results],
                    "total_found": len(results),
                    "pattern": pattern,
                    "base_path": str(resolved_base_path),
                    "truncated": len(results) > max_results
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error searching folders: {str(e)}"
            }
    
    # Legacy method implementations for backward compatibility
    def get_name(self) -> str:
        return self.name
        
    def get_description(self) -> str:
        return self.description
        
    def get_required_args(self) -> Dict[str, str]:
        return {
            "pattern": "The pattern to match folder names against (supports glob patterns)"
        } 