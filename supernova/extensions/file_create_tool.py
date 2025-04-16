"""
SuperNova - AI-powered development assistant within the terminal.

File Create Tool - Creates files with specified content.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rich.console import Console

from supernova.core.tool_base import SupernovaTool, FileToolMixin

console = Console()


class FileCreateTool(SupernovaTool, FileToolMixin):
    """
    A tool for creating files with specified content.
    """
    
    def get_name(self) -> str:
        """Get the name of the tool."""
        return "file_create"
    
    def get_description(self) -> str:
        """Get a description of what the tool does."""
        return "Create a new file with the specified content"
    
    def get_usage_examples(self) -> List[str]:
        """Get examples of how to use the tool."""
        return [
            "file_create path=src/main/java/com/example/App.java content='public class App { ... }'",
            "file_create path=README.md content='# Project Title\\n\\nDescription'"
        ]
    
    def get_required_args(self) -> Dict[str, str]:
        """Get the required arguments for this tool."""
        return {
            "path": "The path where the file should be created",
            "content": "The content to write to the file"
        }
    
    def get_optional_args(self) -> Dict[str, str]:
        """Get optional arguments for the tool."""
        return {
            "overwrite": "Whether to overwrite existing files (default: false)"
        }
    
    def validate_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that all required arguments are present.
        
        Args:
            args: Arguments to validate
            
        Returns:
            Dict with validation result
        """
        required_args = self.get_required_args()
        missing_args = [arg for arg in required_args if arg not in args]
        
        return {
            "valid": len(missing_args) == 0,
            "missing": missing_args
        }
    
    def execute(self, args: Dict[str, Any], context: Dict[str, Any], 
                working_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Execute the tool to create a file.
        
        Args:
            args: Tool arguments
                path: Path to the file to create
                content: Content to write to the file
                overwrite: Whether to overwrite existing files
            context: Execution context
            working_dir: Working directory
            
        Returns:
            Result of the file creation operation
        """
        # Validate arguments
        validation = self.validate_args(args)
        if not validation["valid"]:
            return {
                "success": False,
                "error": f"Missing required arguments: {', '.join(validation['missing'])}"
            }
        
        # Get arguments
        file_path = args["path"]
        content = args["content"]
        overwrite = args.get("overwrite", "false").lower() in ["true", "yes", "1"]
        
        # Normalize path
        norm_path = self.normalize_path(file_path, working_dir)
        
        try:
            # Check if file exists and handle overwrite
            if norm_path.exists() and not overwrite:
                return {
                    "success": False,
                    "error": f"File already exists: {file_path}. Use overwrite=true to replace it."
                }
            
            # Create parent directories if needed
            norm_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content to file
            norm_path.write_text(content)
            
            console.print(f"[green]Successfully created file:[/green] {norm_path}")
            
            return {
                "success": True,
                "path": str(norm_path),
                "absolute_path": str(norm_path.resolve()),
                "message": f"File created: {file_path}"
            }
            
        except Exception as e:
            console.print(f"[red]Error creating file {file_path}:[/red] {str(e)}")
            
            return {
                "success": False,
                "path": str(norm_path),
                "error": str(e)
            } 