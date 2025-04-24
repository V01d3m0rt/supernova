"""
SuperNova - AI-powered development assistant within the terminal.

Session management functionality for CLI.
"""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from rich.console import Console

console = Console()

class SessionManager:
    """
    Manages chat sessions, persistence, and related operations.
    
    Responsibilities:
    - Creating and loading sessions
    - Saving session data
    - Managing session history
    - Providing session metadata
    """
    
    def __init__(self, base_dir: Path = None, logger=None):
        """
        Initialize the session manager.
        
        Args:
            base_dir: Base directory for session storage
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger("supernova.session_manager")
        self.base_dir = base_dir or Path.home() / ".supernova" / "sessions"
        
        # Ensure the sessions directory exists
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Session directory: {self.base_dir}")
        except Exception as e:
            self.logger.error(f"Error creating session directory: {str(e)}")
            # Fall back to temporary directory
            import tempfile
            self.base_dir = Path(tempfile.gettempdir()) / "supernova" / "sessions"
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Falling back to temporary session directory: {self.base_dir}")
        
        # Current active session ID
        self.active_session_id = None
        
        # Cache of loaded sessions
        self.session_cache = {}
    
    def create_session(self, session_data: Dict[str, Any] = None) -> str:
        """
        Create a new session.
        
        Args:
            session_data: Initial session data
            
        Returns:
            Session ID
        """
        # Generate a new session ID
        session_id = str(uuid.uuid4())
        
        # Create session data
        data = session_data or {}
        data.update({
            "session_id": session_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "messages": []
        })
        
        # Save the session
        self._save_session(session_id, data)
        
        # Set as active session
        self.active_session_id = session_id
        
        # Add to cache
        self.session_cache[session_id] = data
        
        self.logger.debug(f"Created new session: {session_id}")
        return session_id
    
    def load_session(self, session_id: str) -> Dict[str, Any]:
        """
        Load a session by ID.
        
        Args:
            session_id: Session ID to load
            
        Returns:
            Session data
        """
        # Check cache first
        if session_id in self.session_cache:
            self.logger.debug(f"Loaded session from cache: {session_id}")
            return self.session_cache[session_id]
        
        # Get session file path
        session_file = self._get_session_file_path(session_id)
        
        # Check if the file exists
        if not session_file.exists():
            self.logger.error(f"Session file not found: {session_file}")
            return None
        
        # Load the session file
        try:
            with open(session_file, "r") as f:
                data = json.load(f)
            
            # Add to cache
            self.session_cache[session_id] = data
            
            # Set as active session
            self.active_session_id = session_id
            
            self.logger.debug(f"Loaded session: {session_id}")
            return data
        except Exception as e:
            self.logger.error(f"Error loading session {session_id}: {str(e)}")
            return None
    
    def save_messages(self, session_id: str, messages: List[Dict[str, Any]]) -> bool:
        """
        Save messages to a session.
        
        Args:
            session_id: Session ID
            messages: List of message dictionaries
            
        Returns:
            Success status
        """
        # Get session data
        session_data = self.load_session(session_id)
        
        if not session_data:
            self.logger.error(f"Cannot save messages - session not found: {session_id}")
            return False
        
        # Update messages and timestamp
        session_data["messages"] = messages
        session_data["updated_at"] = time.time()
        
        # Save the session
        self._save_session(session_id, session_data)
        
        self.logger.debug(f"Saved {len(messages)} messages to session: {session_id}")
        return True
    
    def add_message(self, session_id: str, message: Dict[str, Any]) -> bool:
        """
        Add a message to a session.
        
        Args:
            session_id: Session ID
            message: Message dictionary
            
        Returns:
            Success status
        """
        # Get session data
        session_data = self.load_session(session_id)
        
        if not session_data:
            self.logger.error(f"Cannot add message - session not found: {session_id}")
            return False
        
        # Add message if it doesn't already exist
        if "messages" not in session_data:
            session_data["messages"] = []
        
        session_data["messages"].append(message)
        session_data["updated_at"] = time.time()
        
        # Save the session
        self._save_session(session_id, session_data)
        
        self.logger.debug(f"Added message to session: {session_id}")
        return True
    
    def get_session_list(self) -> List[Dict[str, Any]]:
        """
        Get a list of all sessions.
        
        Returns:
            List of session metadata
        """
        sessions = []
        
        # Find all session files
        try:
            for file_path in self.base_dir.glob("*.json"):
                try:
                    # Extract the session ID from the filename
                    session_id = file_path.stem
                    
                    # Load session metadata
                    with open(file_path, "r") as f:
                        data = json.load(f)
                    
                    # Add basic metadata
                    sessions.append({
                        "session_id": session_id,
                        "created_at": data.get("created_at", 0),
                        "updated_at": data.get("updated_at", 0),
                        "message_count": len(data.get("messages", [])),
                    })
                except Exception as e:
                    self.logger.error(f"Error loading session metadata from {file_path}: {str(e)}")
                    continue
        except Exception as e:
            self.logger.error(f"Error listing sessions: {str(e)}")
        
        # Sort by updated_at (most recent first)
        sessions.sort(key=lambda s: s.get("updated_at", 0), reverse=True)
        
        return sessions
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            Success status
        """
        # Get session file path
        session_file = self._get_session_file_path(session_id)
        
        # Check if the file exists
        if not session_file.exists():
            self.logger.error(f"Cannot delete - session file not found: {session_file}")
            return False
        
        # Delete the file
        try:
            session_file.unlink()
            
            # Remove from cache
            if session_id in self.session_cache:
                del self.session_cache[session_id]
            
            # Clear active session if this was it
            if self.active_session_id == session_id:
                self.active_session_id = None
            
            self.logger.debug(f"Deleted session: {session_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting session {session_id}: {str(e)}")
            return False
    
    def get_active_session_id(self) -> Optional[str]:
        """
        Get the active session ID.
        
        Returns:
            Active session ID or None
        """
        return self.active_session_id
    
    def _get_session_file_path(self, session_id: str) -> Path:
        """
        Get the file path for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Path to the session file
        """
        return self.base_dir / f"{session_id}.json"
    
    def _save_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """
        Save session data to file.
        
        Args:
            session_id: Session ID
            data: Session data
            
        Returns:
            Success status
        """
        # Get session file path
        session_file = self._get_session_file_path(session_id)
        
        # Save the file
        try:
            with open(session_file, "w") as f:
                json.dump(data, f, indent=2)
            
            # Update cache
            self.session_cache[session_id] = data
            
            self.logger.debug(f"Saved session to file: {session_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving session {session_id} to {session_file}: {str(e)}")
            return False 