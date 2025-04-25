"""
SuperNova - AI-powered development assistant within the terminal.

Chat session for interactive AI assistance.
"""

from pathlib import Path
from typing import Optional, Union

# Import the refactored ChatSession class
from supernova.cli.chat.session.chat_session import ChatSession

def start_chat_sync(chat_dir: Optional[Union[str, Path]] = None) -> None:
    """
    Start a synchronous chat session.
    
    Args:
        chat_dir: Optional directory to start the chat in
    """
    # Create a chat session and run it
    chat_session = ChatSession(initial_directory=chat_dir)
    chat_session.run_chat_loop()

# Re-export the ChatSession class
__all__ = ["ChatSession", "start_chat_sync"]