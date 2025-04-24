"""
SuperNova - AI-powered development assistant within the terminal.

Tool Base - Base class for all tools in the SuperNova ecosystem.
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class SupernovaTool(ABC):
    """
    Base class for all SuperNova tools.
    
    All tools in the SuperNova ecosystem must inherit from this class
    and implement its abstract methods.
    """
    
    # These properties should be set by all subclasses
    name: str = ""
    description: str = ""
    
    def __init__(
        self,
        name: str,
        description: str,
        required_args: Dict[str, str] = None,
        optional_args: Dict[str, str] = None
    ):
        """
        Initialize a tool.
        
        Args:
            name: Name of the tool
            description: Description of the tool
            required_args: Dictionary of required arguments {name: description}
            optional_args: Dictionary of optional arguments {name: description}
        """
        self.name = name
        self.description = description
        self.required_args = required_args or {}
        self.optional_args = optional_args or {}
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the schema for this tool.
        
        Returns:
            Tool schema dictionary
        """
        # Build properties from required and optional args
        properties = {}
        required = []
        
        # Add required arguments
        for arg_name, arg_desc in self.required_args.items():
            properties[arg_name] = {
                "type": "string",
                "description": arg_desc
            }
            required.append(arg_name)
        
        # Add optional arguments
        for arg_name, arg_desc in self.optional_args.items():
            properties[arg_name] = {
                "type": "string",
                "description": arg_desc
            }
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    
    def get_arguments_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for the tool's arguments.
        
        Returns:
            JSON schema for the tool's arguments
        """
        # Build properties from required and optional args
        properties = {}
        required = []
        
        # Add required arguments
        for arg_name, arg_desc in self.required_args.items():
            properties[arg_name] = {
                "type": "string",
                "description": arg_desc
            }
            required.append(arg_name)
        
        # Add optional arguments
        for arg_name, arg_desc in self.optional_args.items():
            properties[arg_name] = {
                "type": "string",
                "description": arg_desc
            }
        
        return {
            "type": "object",
            "properties": properties,
            "required": required
        }
    
    @abstractmethod
    async def execute_async(
        self, 
        args: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None, 
        working_dir: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Execute the tool asynchronously.
        
        Args:
            args: Tool arguments
            context: Execution context
            working_dir: Working directory (can be string or Path)
            
        Returns:
            Execution result
        """
        pass
    
    def execute(
        self, 
        args: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None, 
        working_dir: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Execute the tool synchronously.
        
        Args:
            args: Tool arguments
            context: Execution context
            working_dir: Working directory (can be string or Path)
            
        Returns:
            Execution result
        """
        # Default implementation calls the async version
        # This should be overridden for better performance
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.execute_async(args, context, working_dir)
            )
        finally:
            loop.close()
    
    # Helper methods for compatibility with old code
    def get_name(self) -> str:
        """Legacy method to get the tool name."""
        return self.name
    
    def get_description(self) -> str:
        """Legacy method to get the tool description."""
        return self.description
    
    def get_required_args(self) -> Dict[str, str]:
        """Legacy method to get required arguments from the schema."""
        schema = self.get_arguments_schema()
        required_args = {}
        
        if "required" in schema and "properties" in schema:
            for arg_name in schema.get("required", []):
                if arg_name in schema["properties"]:
                    prop = schema["properties"][arg_name]
                    required_args[arg_name] = prop.get("type", "string")
        
        return required_args
    
    def to_openai_schema(self) -> Dict[str, Any]:
        """
        Convert the tool to OpenAI function calling format.
        
        Returns:
            Dictionary in OpenAI function calling format
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_arguments_schema()
            }
        }
    
    def to_anthropic_schema(self) -> Dict[str, Any]:
        """
        Convert the tool to Anthropic tool calling format.
        
        Returns:
            Dictionary in Anthropic tool calling format
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.get_arguments_schema()
        }
    
    def validate_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that all required arguments are provided.
        
        Args:
            args: Dictionary of arguments to validate
            
        Returns:
            Dictionary with validation results containing:
            - 'valid' (bool): Whether all required arguments are present
            - 'missing' (list): List of missing argument names if any
        """
        if not isinstance(args, dict):
            return {
                'valid': False,
                'missing': ['arguments must be a dictionary'],
                'error': 'Arguments must be a dictionary'
            }
            
        schema = self.get_arguments_schema()
        required_args = schema.get("required", [])
        missing_args = [arg for arg in required_args if arg not in args]
        
        result = {
            'valid': len(missing_args) == 0,
            'missing': missing_args
        }
        
        if not result['valid']:
            result['error'] = f"Missing required arguments: {', '.join(missing_args)}"
        
        return result
    
    def _create_standard_response(self, success: bool, **kwargs) -> Dict[str, Any]:
        """
        Create a standardized response dictionary.
        
        Args:
            success: Whether the operation was successful
            **kwargs: Additional key-value pairs to include in the response
            
        Returns:
            Standardized response dictionary
        """
        response = {'success': success}
        
        # Add error message if provided and success is False
        if not success and 'error' in kwargs:
            response['error'] = kwargs.pop('error')
            
        # Add any other provided values
        response.update(kwargs)
        
        return response

    def _resolve_path(self, path: Union[str, Path], base_dir: Optional[Union[str, Path]] = None) -> Path:
        """
        Resolve a path relative to a base directory.
        
        Args:
            path: Path to resolve (can be string or Path)
            base_dir: Base directory to resolve relative to (can be string or Path)
            
        Returns:
            Resolved Path object
        """
        # Check for empty path
        if not path:
            raise ValueError("Path cannot be empty")
        
        # Convert to Path if it's a string
        path_obj = Path(path) if isinstance(path, str) else path
        
        # If it's already absolute, return it
        if path_obj.is_absolute():
            return path_obj
        
        # If there's a base_dir, make it relative to that
        if base_dir:
            # Convert base_dir to Path if it's a string
            base_path = Path(base_dir) if isinstance(base_dir, str) else base_dir
            # Return the resolved path
            return (base_path / path_obj).resolve()
        
        # Otherwise, make it relative to current working directory
        return (Path.cwd() / path_obj).resolve()


class FileToolMixin:
    """
    Mixin for tools that operate on files.
    
    This mixin provides common functionality for tools that need to:
    - Resolve file paths (absolute or relative)
    - Check if files or directories exist
    - Safely read from or write to files
    - Handle file system errors consistently
    - Process file content
    - Manage file metadata
    
    Tools that deal with file operations should incorporate this mixin
    to ensure consistent and safe file handling behavior.
    """
    
    def normalize_path(self, path: Union[str, Path], working_dir: Optional[Union[str, Path]] = None) -> Path:
        """
        Normalize a path, resolving it relative to working_dir if provided.
        This is the recommended method for path resolution in file tools.
        
        Args:
            path: Path to normalize (can be string or Path)
            working_dir: Working directory to resolve relative to (can be string or Path)
            
        Returns:
            Normalized Path object
            
        Raises:
            ValueError: If the path is empty
        """
        return self._resolve_path(path, working_dir)
    
    def _file_exists(self, file_path: Union[str, Path], working_dir: Optional[Path] = None) -> bool:
        """
        Check if a file exists.
        
        Safely verifies if a file exists at the specified path.
        The path is first resolved using _resolve_path().
        
        Args:
            file_path: Path to check (absolute or relative)
            working_dir: Working directory to resolve relative paths from
            
        Returns:
            True if the file exists, False otherwise
            
        Raises:
            ValueError: If the file_path is empty
            PermissionError: If the file cannot be accessed due to permissions
        """
        try:
            path = self._resolve_path(file_path, working_dir)
            return path.exists() and path.is_file()
        except PermissionError:
            raise PermissionError(f"Permission denied when accessing file: {file_path}")
        except Exception as e:
            # Log but don't raise other exceptions, just return False
            print(f"Error checking if file exists: {str(e)}")
            return False
    
    def _dir_exists(self, dir_path: Union[str, Path], working_dir: Optional[Path] = None) -> bool:
        """
        Check if a directory exists.
        
        Safely verifies if a directory exists at the specified path.
        The path is first resolved using _resolve_path().
        
        Args:
            dir_path: Path to check (absolute or relative)
            working_dir: Working directory to resolve relative paths from
            
        Returns:
            True if the directory exists, False otherwise
            
        Raises:
            ValueError: If the dir_path is empty
            PermissionError: If the directory cannot be accessed due to permissions
        """
        try:
            path = self._resolve_path(dir_path, working_dir)
            return path.exists() and path.is_dir()
        except PermissionError:
            raise PermissionError(f"Permission denied when accessing directory: {dir_path}")
        except Exception as e:
            # Log but don't raise other exceptions, just return False
            print(f"Error checking if directory exists: {str(e)}")
            return False
            
    def _read_file(self, file_path: Union[str, Path], working_dir: Optional[Path] = None, 
                  encoding: str = 'utf-8') -> str:
        """
        Read the contents of a file.
        
        Safely reads a file's contents, handling common errors.
        
        Args:
            file_path: Path to the file to read
            working_dir: Working directory to resolve relative paths from
            encoding: File encoding (default: utf-8)
            
        Returns:
            Contents of the file as a string
            
        Raises:
            FileNotFoundError: If the file does not exist
            PermissionError: If the file cannot be accessed due to permissions
            UnicodeDecodeError: If the file cannot be decoded with the specified encoding
            IOError: If an I/O error occurs during reading
        """
        path = self._resolve_path(file_path, working_dir)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")
            
        try:
            with open(path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            raise UnicodeDecodeError(encoding, b"", 0, 1, f"File is not valid {encoding} text")
        except IOError as e:
            raise IOError(f"Error reading file {path}: {str(e)}")
            
    def _write_file(self, file_path: Union[str, Path], content: str, working_dir: Optional[Path] = None, 
                   create_dirs: bool = False, encoding: str = 'utf-8', mode: str = 'w') -> bool:
        """
        Write content to a file.
        
        Safely writes content to a file, optionally creating parent directories.
        
        Args:
            file_path: Path to the file to write
            content: Content to write to the file
            working_dir: Working directory to resolve relative paths from
            create_dirs: Whether to create parent directories if they don't exist
            encoding: File encoding (default: utf-8)
            mode: File opening mode ('w' for write, 'a' for append, etc.)
            
        Returns:
            True if the file was written successfully, False otherwise
            
        Raises:
            PermissionError: If the file cannot be written due to permissions
            IOError: If an I/O error occurs during writing
        """
        path = self._resolve_path(file_path, working_dir)
        
        # Create parent directories if requested
        if create_dirs and not path.parent.exists():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                raise PermissionError(f"Permission denied when creating directories for: {path}")
            except Exception as e:
                raise IOError(f"Error creating directories for {path}: {str(e)}")
        
        try:
            with open(path, mode, encoding=encoding) as f:
                f.write(content)
            return True
        except PermissionError:
            raise PermissionError(f"Permission denied when writing to file: {path}")
        except IOError as e:
            raise IOError(f"Error writing to file {path}: {str(e)}")
        except Exception as e:
            raise IOError(f"Unexpected error writing to file {path}: {str(e)}")
    
    def _append_to_file(self, file_path: Union[str, Path], content: str, 
                       working_dir: Optional[Path] = None, 
                       create_dirs: bool = False, 
                       encoding: str = 'utf-8') -> bool:
        """
        Append content to a file.
        
        A convenience method that calls _write_file with mode='a'.
        
        Args:
            file_path: Path to the file to append to
            content: Content to append to the file
            working_dir: Working directory to resolve relative paths from
            create_dirs: Whether to create parent directories if they don't exist
            encoding: File encoding (default: utf-8)
            
        Returns:
            True if the content was appended successfully, False otherwise
            
        Raises:
            PermissionError: If the file cannot be written due to permissions
            IOError: If an I/O error occurs during writing
        """
        return self._write_file(
            file_path=file_path,
            content=content,
            working_dir=working_dir,
            create_dirs=create_dirs,
            encoding=encoding,
            mode='a'
        )
    
    def _get_file_info(self, file_path: Union[str, Path], working_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Get information about a file.
        
        Args:
            file_path: Path to the file
            working_dir: Working directory to resolve relative paths from
            
        Returns:
            Dictionary with file information including:
                - name: File name
                - path: Full path
                - size: Size in bytes
                - modified: Last modified timestamp
                - extension: File extension
                - exists: Whether the file exists
                - is_file: Whether it's a file (not a directory)
                
        Raises:
            PermissionError: If the file cannot be accessed due to permissions
        """
        try:
            path = self._resolve_path(file_path, working_dir)
            exists = path.exists()
            
            info = {
                "name": path.name,
                "path": str(path),
                "exists": exists,
                "is_file": exists and path.is_file(),
                "is_dir": exists and path.is_dir(),
                "extension": path.suffix.lstrip(".") if path.suffix else "",
                "parent": str(path.parent)
            }
            
            if exists:
                try:
                    stat = path.stat()
                    info.update({
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "created": stat.st_ctime,
                        "permissions": oct(stat.st_mode)[-3:]
                    })
                except PermissionError:
                    raise PermissionError(f"Permission denied when accessing file stats: {path}")
            
            return info
            
        except PermissionError as e:
            raise e
        except Exception as e:
            return {
                "name": str(file_path),
                "path": str(file_path),
                "exists": False,
                "error": str(e)
            }
    
    def _is_text_file(self, file_path: Union[str, Path], working_dir: Optional[Path] = None) -> bool:
        """
        Check if a file is likely a text file based on extension.
        
        Args:
            file_path: Path to the file
            working_dir: Working directory to resolve relative paths from
            
        Returns:
            True if the file is likely a text file, False otherwise
        """
        text_extensions = {
            'txt', 'py', 'js', 'ts', 'html', 'css', 'md', 'rst', 'json', 'xml',
            'yaml', 'yml', 'toml', 'sh', 'bash', 'c', 'cpp', 'h', 'hpp', 'java',
            'go', 'rs', 'rb', 'php', 'pl', 'kt', 'swift', 'cs', 'fs', 'hs',
            'sql', 'csv', 'log', 'ini', 'conf', 'cfg', 'properties'
        }
        
        path = self._resolve_path(file_path, working_dir)
        return path.suffix.lstrip('.').lower() in text_extensions
    
    def _list_dir(self, dir_path: Union[str, Path], working_dir: Optional[Path] = None, 
                pattern: str = "*", recursive: bool = False) -> List[Path]:
        """
        List files in a directory, optionally filtering by pattern.
        
        Args:
            dir_path: Path to the directory
            working_dir: Working directory to resolve relative paths from
            pattern: Glob pattern to filter files by (default: "*")
            recursive: Whether to search recursively (default: False)
            
        Returns:
            List of Path objects for the matched files
            
        Raises:
            FileNotFoundError: If the directory does not exist
            NotADirectoryError: If the path exists but is not a directory
            PermissionError: If the directory cannot be accessed due to permissions
        """
        path = self._resolve_path(dir_path, working_dir)
        
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
        
        if not path.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")
        
        try:
            if recursive:
                return list(path.glob(f"**/{pattern}"))
            else:
                return list(path.glob(pattern))
        except PermissionError:
            raise PermissionError(f"Permission denied when accessing directory: {path}") 

# For backward compatibility, create an alias for the SupernovaTool class
BaseTool = SupernovaTool 