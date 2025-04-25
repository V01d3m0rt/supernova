#!/usr/bin/env python3
"""
Test script for the refactored chat session.
"""

import os
from pathlib import Path

from supernova.cli.chat_session import start_chat_sync

if __name__ == "__main__":
    # Get the current directory
    current_dir = Path(os.getcwd())
    
    # Start a chat session
    start_chat_sync(current_dir)