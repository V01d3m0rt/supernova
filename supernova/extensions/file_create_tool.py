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
    
    def __init__(self):
        """Initialize the file create tool."""
        super().__init__(
            name="file_create",
            description="Create a new file with the specified content",
            required_args={
                "path": "The path where the file should be created",
                "content": "The content to write to the file"
            },
            optional_args={
                "overwrite": "Whether to overwrite existing files (default: false)",
                "create_dirs": "Whether to create parent directories if they don't exist (default: true)",
                "encoding": "File encoding to use (default: utf-8)"
            }
        )
    
    def get_usage_examples(self) -> List[str]:
        """Get examples of how to use the tool."""
        return [
            "file_create path=src/main/java/com/example/App.java content='public class App { ... }'",
            "file_create path=README.md content='# Project Title\\n\\nDescription' overwrite=true"
        ]
    
    def execute(self, args: Dict[str, Any], context: Dict[str, Any], 
                working_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Execute the tool to create a file.
        
        Args:
            args: Tool arguments
                path: Path to the file to create
                content: Content to write to the file
                overwrite: Whether to overwrite existing files
                create_dirs: Whether to create parent directories if they don't exist
                encoding: File encoding to use
            context: Execution context
            working_dir: Working directory
            
        Returns:
            Result of the file creation operation
        """
        # Validate arguments
        validation = self.validate_args(args)
        if not validation["valid"]:
            return self._create_standard_response(
                success=False,
                error=validation.get("error", "Missing required arguments")
            )
        
        # Get arguments
        file_path = args["path"]
        content = args["content"]
        overwrite = args.get("overwrite", "false").lower() in ["true", "yes", "1"]
        create_dirs = args.get("create_dirs", "true").lower() in ["true", "yes", "1"]
        encoding = args.get("encoding", "utf-8")
        
        # Normalize path
        try:
            norm_path = self.normalize_path(file_path, working_dir)
        except ValueError as e:
            return self._create_standard_response(
                success=False,
                error=str(e)
            )
        
        try:
            # Check if file exists and handle overwrite
            if norm_path.exists() and not overwrite:
                return self._create_standard_response(
                    success=False,
                    error=f"File already exists: {file_path}. Use overwrite=true to replace it.",
                    path=str(norm_path)
                )
            
            # Write content to file
            success = self._write_file(
                file_path=norm_path,
                content=content,
                working_dir=None,  # Already normalized
                create_dirs=create_dirs,
                encoding=encoding
            )
            
            console.print(f"[green]Successfully created file:[/green] {norm_path}")
            
            return self._create_standard_response(
                success=True,
                path=str(norm_path),
                absolute_path=str(norm_path.resolve()),
                message=f"File created: {file_path}"
            )
            
        except PermissionError as e:
            console.print(f"[red]Permission error creating file {file_path}:[/red] {str(e)}")
            return self._create_standard_response(
                success=False,
                error=f"Permission denied: {str(e)}",
                path=str(norm_path)
            )
        except IOError as e:
            console.print(f"[red]I/O error creating file {file_path}:[/red] {str(e)}")
            return self._create_standard_response(
                success=False,
                error=f"I/O error: {str(e)}",
                path=str(norm_path)
            )
        except Exception as e:
            console.print(f"[red]Error creating file {file_path}:[/red] {str(e)}")
            return self._create_standard_response(
                success=False,
                error=str(e),
                path=str(norm_path)
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
            Result of the file creation operation
        """
        # Default implementation runs synchronous version
        return self.execute(args, context or {}, working_dir) 