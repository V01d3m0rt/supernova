"""
SuperNova - AI-powered development assistant within the terminal.

Error handling functionality for CLI.
"""

import logging
import sys
import traceback
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import time

from rich.console import Console
from rich.panel import Panel

console = Console()

class ErrorHandler:
    """
    Handles error logging and reporting in the CLI application.
    
    Responsibilities:
    - Logging errors to appropriate destinations
    - Formatting error messages for display
    - Providing error context for debugging
    - Implementing error recovery strategies
    """
    
    def __init__(self, logger=None, log_file: Path = None):
        """
        Initialize the error handler.
        
        Args:
            logger: Logger instance
            log_file: Path to log file
        """
        self.logger = logger or logging.getLogger("supernova.error_handler")
        self.log_file = log_file
        
        # Error history for the current session
        self.error_history = []
        
        # Set up log file if provided
        if self.log_file:
            try:
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Add file handler to logger
                file_handler = logging.FileHandler(self.log_file)
                file_handler.setLevel(logging.ERROR)
                
                # Create a formatter
                formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                file_handler.setFormatter(formatter)
                
                # Add the handler to the logger
                self.logger.addHandler(file_handler)
            except Exception as e:
                self.logger.error(f"Error setting up log file: {str(e)}")
    
    def log_error(self, error_message: str, error_type: str = "general", context: Dict[str, Any] = None) -> None:
        """
        Log an error to the appropriate destinations.
        
        Args:
            error_message: The error message to log
            error_type: Type of error
            context: Additional context for the error
        """
        # Add error to history
        error_record = {
            "message": error_message,
            "type": error_type,
            "context": context or {},
            "timestamp": time.time(),
            "traceback": traceback.format_exc() if traceback.format_exc() != "NoneType: None\n" else None
        }
        self.error_history.append(error_record)
        
        # Log to logger
        self.logger.error(f"{error_type} error: {error_message}")
        
        # Log context if available
        if context:
            self.logger.debug(f"Error context: {context}")
        
        # Log traceback if available
        if error_record["traceback"]:
            self.logger.debug(f"Traceback:\n{error_record['traceback']}")
    
    def display_error(self, error_message: str, error_type: str = "general") -> None:
        """
        Display an error message to the user.
        
        Args:
            error_message: The error message to display
            error_type: Type of error
        """
        # Format the error message
        panel = Panel(
            error_message,
            title=f"{error_type.capitalize()} Error",
            title_align="left",
            border_style="red"
        )
        
        # Display to console
        console.print(panel)
    
    def get_error_history(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get the error history for the current session.
        
        Args:
            limit: Maximum number of errors to return
            
        Returns:
            List of error records
        """
        if limit is None:
            return self.error_history
        else:
            return self.error_history[-limit:]
    
    def clear_error_history(self) -> None:
        """Clear the error history for the current session."""
        self.error_history = []
    
    def handle_exception(self, exc_type, exc_value, exc_traceback) -> None:
        """
        Handle an uncaught exception.
        
        Args:
            exc_type: Exception type
            exc_value: Exception value
            exc_traceback: Exception traceback
        """
        # Ignore KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # Format the error message
        error_message = f"{exc_type.__name__}: {exc_value}"
        
        # Get the traceback
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # Log the error
        self.log_error(error_message, error_type="uncaught_exception", context={"traceback": tb_str})
        
        # Display the error
        self.display_error(f"{error_message}\n\nPlease check the logs for more details.", error_type="uncaught_exception")
    
    def set_global_exception_handler(self) -> None:
        """Set this handler as the global exception handler."""
        sys.excepthook = self.handle_exception 