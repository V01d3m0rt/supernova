"""
SuperNova - AI-powered development assistant within the terminal.

This module serves as a facade for the refactored chat session implementation.
It maintains the original interface for backward compatibility.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from supernova.cli.chat.session.chat_session import ChatSession as RefactoredChatSession

def start_chat_sync(chat_dir: Optional[Union[str, Path]] = None) -> None:
    """
    Start a synchronous chat session.
    
    Args:
        chat_dir: Optional directory to start the chat in
    """
    # Create a chat session and run it
    chat_session = ChatSession(initial_directory=chat_dir)
    chat_session.run_chat_loop()

# Create an alias to maintain backward compatibility
class ChatSession(RefactoredChatSession):
    """
    Facade class that maintains the original ChatSession interface
    but delegates to the refactored implementation.
    """
    pass
