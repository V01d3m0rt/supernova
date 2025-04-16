"""
SuperNova - AI-powered development assistant within the terminal.

Database manager for chat history persistence.
"""

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from rich.console import Console

from supernova.config import loader

console = Console()


class DatabaseManager:
    """Database manager for SuperNova chat history persistence."""
    
    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database (default: from config)
        """
        self.config = loader.load_config()
        
        if not self.config.persistence.enabled:
            console.print("[yellow]Warning:[/yellow] Persistence is disabled in configuration")
            self.enabled = False
            return
        
        self.enabled = True
        
        # Use provided db_path directly, without using config path
        if db_path is None:
            # Only use config path as fallback if no path provided
            db_path = self.config.persistence.db_path
            # Expand environment variables in the path
            db_path = loader._expand_env_vars(db_path)
        
        # Ensure the directory exists
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path
        
        # Initialize database
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema if it doesn't exist."""
        if not self.enabled:
            return
        
        try:
            # Use existing connection if provided (useful for testing)
            if hasattr(self, "conn") and self.conn is not None:
                conn = self.conn
            else:
                conn = sqlite3.connect(self.db_path)
            
            cursor = conn.cursor()
            
            # Create chats table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_path TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')
            
            # Create messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()
            
            # Don't close if it's a persistent connection for testing
            if not hasattr(self, "conn"):
                conn.close()
        
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to initialize database: {str(e)}")
            self.enabled = False
    
    def create_chat(self, project_path: Union[str, Path]) -> Optional[int]:
        """
        Create a new chat session.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            Chat ID or None if persistence is disabled
        """
        if not self.enabled:
            return None
        
        try:
            project_path = str(Path(project_path).resolve())
            # Use floating-point time to include microseconds
            timestamp = time.time()
            
            # Use existing connection if available
            if hasattr(self, "conn") and self.conn is not None:
                conn = self.conn
            else:
                conn = sqlite3.connect(self.db_path)
            
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO chats (project_path, created_at, updated_at) VALUES (?, ?, ?)",
                (project_path, timestamp, timestamp)
            )
            
            chat_id = cursor.lastrowid
            conn.commit()
            
            # Don't close if it's a persistent connection for testing
            if not hasattr(self, "conn"):
                conn.close()
            
            return chat_id
        
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to create chat: {str(e)}")
            return None
    
    def add_message(
        self,
        chat_id: int,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Optional[int]:
        """
        Add a message to a chat session.
        
        Args:
            chat_id: ID of the chat session
            role: Role of the message sender (user, assistant, system)
            content: Content of the message
            metadata: Optional metadata for the message
            
        Returns:
            Message ID or None if persistence is disabled
        """
        if not self.enabled or chat_id is None:
            return None
        
        try:
            # Use floating-point time to include microseconds
            timestamp = time.time()
            metadata_json = json.dumps(metadata) if metadata else None
            
            # Use existing connection if available
            if hasattr(self, "conn") and self.conn is not None:
                conn = self.conn
            else:
                conn = sqlite3.connect(self.db_path)
            
            cursor = conn.cursor()
            
            # Update chat's updated_at timestamp
            cursor.execute(
                "UPDATE chats SET updated_at = ? WHERE id = ?",
                (timestamp, chat_id)
            )
            
            # Insert the message
            cursor.execute(
                "INSERT INTO messages (chat_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
                (chat_id, role, content, timestamp, metadata_json)
            )
            
            message_id = cursor.lastrowid
            conn.commit()
            
            # Don't close if it's a persistent connection for testing
            if not hasattr(self, "conn"):
                conn.close()
            
            return message_id
        
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to add message: {str(e)}")
            return None
    
    def get_chat_history(
        self,
        chat_id: int,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get the history of a chat session.
        
        Args:
            chat_id: ID of the chat session
            limit: Maximum number of messages to retrieve (default: from config)
            
        Returns:
            List of message dictionaries
        """
        if not self.enabled or chat_id is None:
            return []
        
        try:
            if limit is None:
                limit = self.config.chat.history_limit
            
            # Use existing connection if available
            if hasattr(self, "conn") and self.conn is not None:
                conn = self.conn
            else:
                conn = sqlite3.connect(self.db_path)
            
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT id, role, content, timestamp, metadata
                FROM messages
                WHERE chat_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (chat_id, limit)
            )
            
            messages = []
            for row in cursor.fetchall():
                message = {
                    "id": row["id"],
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": row["timestamp"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else None
                }
                messages.append(message)
            
            # Don't close if it's a persistent connection for testing
            if not hasattr(self, "conn"):
                conn.close()
            
            return messages
        
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to get chat history: {str(e)}")
            return []
    
    def get_latest_chat_for_project(self, project_path: Union[str, Path]) -> Optional[int]:
        """
        Get the ID of the latest chat session for a project.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            Chat ID or None if not found or persistence is disabled
        """
        if not self.enabled:
            return None
        
        try:
            project_path = str(Path(project_path).resolve())
            
            # Use existing connection if available
            if hasattr(self, "conn") and self.conn is not None:
                conn = self.conn
            else:
                conn = sqlite3.connect(self.db_path)
            
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT id
                FROM chats
                WHERE project_path = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (project_path,)
            )
            
            row = cursor.fetchone()
            
            # Don't close if it's a persistent connection for testing
            if not hasattr(self, "conn"):
                conn.close()
            
            return row["id"] if row else None
        
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to get latest chat: {str(e)}")
            return None
    
    def list_project_chats(self, project_path: Union[str, Path]) -> List[Dict]:
        """
        List all chat sessions for a project.
        
        Args:
            project_path: Path to the project directory
            
        Returns:
            List of chat dictionaries
        """
        if not self.enabled:
            return []
        
        try:
            project_path = str(Path(project_path).resolve())
            
            # Use existing connection if available
            if hasattr(self, "conn") and self.conn is not None:
                conn = self.conn
            else:
                conn = sqlite3.connect(self.db_path)
            
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT id, created_at, updated_at
                FROM chats
                WHERE project_path = ?
                ORDER BY updated_at DESC
                """,
                (project_path,)
            )
            
            chats = []
            for row in cursor.fetchall():
                chat = {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
                chats.append(chat)
            
            # Don't close if it's a persistent connection for testing
            if not hasattr(self, "conn"):
                conn.close()
            
            return chats
        
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to list project chats: {str(e)}")
            return [] 