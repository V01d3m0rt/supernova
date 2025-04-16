import os
import sqlite3
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from supernova.persistence.db_manager import DatabaseManager


@pytest.fixture
def mock_connection():
    """Create a mock database connection."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = []
    return conn


@pytest.fixture
def db_manager(mock_connection):
    """Create a DatabaseManager with a mock connection."""
    with patch("supernova.persistence.db_manager.sqlite3.connect", return_value=mock_connection):
        with patch("supernova.persistence.db_manager.loader.load_config") as mock_config:
            # Create a mock config with persistence enabled
            mock_config.return_value = MagicMock()
            mock_config.return_value.persistence.enabled = True
            mock_config.return_value.persistence.db_path = ":memory:"
            mock_config.return_value.chat.history_limit = 50
            
            manager = DatabaseManager(":memory:")
            manager.conn = mock_connection  # Attach the connection for testing
            yield manager


@pytest.mark.asyncio
async def test_init_db(db_manager, mock_connection):
    """Test initializing the database."""
    # Initialize the database
    db_manager._init_db()
    
    # Verify that execute was called with CREATE TABLE statements
    execute_calls = mock_connection.cursor.return_value.execute.call_args_list
    
    # Check that at least one CREATE TABLE statement was executed
    assert any("CREATE TABLE IF NOT EXISTS" in str(call) for call in execute_calls)
    
    # Verify commit was called at least once
    assert mock_connection.commit.call_count >= 1


@pytest.mark.asyncio
async def test_add_message(db_manager, mock_connection):
    """Test saving a message to the database."""
    # Create a test message and chat ID
    chat_id = 1
    role = "user"
    content = "Test message"
    
    # Mock cursor.lastrowid to return a message ID
    cursor = mock_connection.cursor.return_value
    cursor.lastrowid = 1
    
    # Save the message
    message_id = db_manager.add_message(chat_id, role, content)
    
    # Verify that execute was called with INSERT
    cursor.execute.assert_called()
    execute_call = cursor.execute.call_args_list[-1][0][0]
    assert "INSERT INTO messages" in execute_call
    
    # Verify commit was called
    mock_connection.commit.assert_called()
    
    # Verify that the message ID was returned
    assert message_id == 1


@pytest.mark.asyncio
async def test_add_message_with_metadata(db_manager, mock_connection):
    """Test saving a message with metadata to the database."""
    # Create a test message and chat ID
    chat_id = 1
    role = "user"
    content = "Test message"
    metadata = {"test_key": "test_value"}
    
    # Save the message
    db_manager.add_message(chat_id, role, content, metadata)
    
    # Verify that execute was called with INSERT and metadata JSON
    cursor = mock_connection.cursor.return_value
    cursor.execute.assert_called()
    
    # Check the metadata was passed as JSON
    args = cursor.execute.call_args_list[-1][0][1]
    assert json.loads(args[-1]) == metadata


@pytest.mark.asyncio
async def test_add_message_with_persistence_disabled(mock_connection):
    """Test saving a message when persistence is disabled."""
    with patch("supernova.persistence.db_manager.loader.load_config") as mock_config:
        # Create a mock config with persistence disabled
        mock_config.return_value = MagicMock()
        mock_config.return_value.persistence.enabled = False
        
        manager = DatabaseManager(":memory:")
        
        # Try to save a message
        message_id = manager.add_message(1, "user", "Test message")
        
        # Should return None and not perform any database operations
        assert message_id is None
        mock_connection.cursor.assert_not_called()


@pytest.mark.asyncio
async def test_get_chat_history(db_manager, mock_connection):
    """Test retrieving messages from the database."""
    # Mock cursor.fetchall to return messages
    cursor = mock_connection.cursor.return_value
    cursor.fetchall.return_value = [
        {"id": 1, "role": "user", "content": "Test message 1", "timestamp": 1234567890.0, "metadata": None},
        {"id": 2, "role": "assistant", "content": "Test response 1", "timestamp": 1234567900.0, "metadata": None}
    ]
    
    # Get messages
    messages = db_manager.get_chat_history(1)
    
    # Verify that execute was called with SELECT
    cursor.execute.assert_called()
    execute_call = cursor.execute.call_args[0][0]
    assert "SELECT" in execute_call
    assert "FROM messages" in execute_call
    
    # Verify that messages were returned in the correct format
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Test message 1"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Test response 1"


@pytest.mark.asyncio
async def test_get_chat_history_with_limit(db_manager, mock_connection):
    """Test retrieving messages with a custom limit."""
    # Mock cursor.fetchall to return messages
    cursor = mock_connection.cursor.return_value
    cursor.fetchall.return_value = [
        {"id": 1, "role": "user", "content": "Test message 1", "timestamp": 1234567890.0, "metadata": None}
    ]
    
    # Get messages with a limit
    messages = db_manager.get_chat_history(1, limit=1)
    
    # Verify that execute was called with the correct limit
    cursor.execute.assert_called()
    execute_args = cursor.execute.call_args[0][1]
    assert execute_args[1] == 1  # Second parameter should be the limit
    
    # Verify that messages were returned
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_get_chat_history_empty(db_manager, mock_connection):
    """Test retrieving messages when there are none."""
    # Mock cursor.fetchall to return empty list
    cursor = mock_connection.cursor.return_value
    cursor.fetchall.return_value = []
    
    # Get messages
    messages = db_manager.get_chat_history(1)
    
    # Verify that execute was called
    cursor.execute.assert_called()
    
    # Verify that an empty list was returned
    assert messages == []


@pytest.mark.asyncio
async def test_get_chat_history_with_persistence_disabled(mock_connection):
    """Test retrieving messages when persistence is disabled."""
    with patch("supernova.persistence.db_manager.loader.load_config") as mock_config:
        # Create a mock config with persistence disabled
        mock_config.return_value = MagicMock()
        mock_config.return_value.persistence.enabled = False
        
        manager = DatabaseManager(":memory:")
        
        # Try to get messages
        messages = manager.get_chat_history(1)
        
        # Should return an empty list and not perform any database operations
        assert messages == []
        mock_connection.cursor.assert_not_called()


@pytest.mark.asyncio
async def test_create_chat(db_manager, mock_connection):
    """Test creating a new chat."""
    # Mock cursor.lastrowid to return a chat ID
    cursor = mock_connection.cursor.return_value
    cursor.lastrowid = 1
    
    # Create a chat
    chat_id = db_manager.create_chat("/test/project")
    
    # Verify that execute was called with INSERT
    cursor.execute.assert_called()
    execute_call = cursor.execute.call_args[0][0]
    assert "INSERT INTO chats" in execute_call
    
    # Verify commit was called
    mock_connection.commit.assert_called()
    
    # Verify that a chat ID was returned
    assert chat_id == 1


@pytest.mark.asyncio
async def test_create_chat_with_persistence_disabled(mock_connection):
    """Test creating a chat when persistence is disabled."""
    with patch("supernova.persistence.db_manager.loader.load_config") as mock_config:
        # Create a mock config with persistence disabled
        mock_config.return_value = MagicMock()
        mock_config.return_value.persistence.enabled = False
        
        manager = DatabaseManager(":memory:")
        
        # Try to create a chat
        chat_id = manager.create_chat("/test/project")
        
        # Should return None and not perform any database operations
        assert chat_id is None
        mock_connection.cursor.assert_not_called()


@pytest.mark.asyncio
async def test_get_latest_chat_for_project(db_manager, mock_connection):
    """Test getting the latest chat for a project."""
    # Create a mock Row object that can be accessed with string keys
    class MockRow(dict):
        def __getitem__(self, key):
            return super().__getitem__(key)
    
    # Create a mock row with id = 1
    mock_row = MockRow(id=1)
    
    # Mock cursor.fetchone to return our mock row
    cursor = mock_connection.cursor.return_value
    cursor.fetchone.return_value = mock_row
    
    # Get the latest chat
    chat_id = db_manager.get_latest_chat_for_project("/test/project")
    
    # Verify that execute was called with the correct query
    cursor.execute.assert_called()
    execute_call = cursor.execute.call_args[0][0]
    # Check for partial query to avoid whitespace issues
    assert "SELECT id" in execute_call
    assert "FROM chats" in execute_call
    assert "WHERE project_path = ?" in execute_call
    assert "ORDER BY updated_at DESC" in execute_call
    
    # Verify that the chat ID was returned
    assert chat_id == 1


@pytest.mark.asyncio
async def test_get_latest_chat_for_project_no_chats(db_manager, mock_connection):
    """Test getting the latest chat when there are none."""
    # Mock cursor.fetchone to return None
    cursor = mock_connection.cursor.return_value
    cursor.fetchone.return_value = None
    
    # Get the latest chat
    chat_id = db_manager.get_latest_chat_for_project("/test/project")
    
    # Verify that execute was called
    cursor.execute.assert_called()
    
    # Verify that None was returned
    assert chat_id is None


@pytest.mark.asyncio
async def test_get_latest_chat_for_project_with_persistence_disabled(mock_connection):
    """Test getting the latest chat when persistence is disabled."""
    with patch("supernova.persistence.db_manager.loader.load_config") as mock_config:
        # Create a mock config with persistence disabled
        mock_config.return_value = MagicMock()
        mock_config.return_value.persistence.enabled = False
        
        manager = DatabaseManager(":memory:")
        
        # Try to get the latest chat
        chat_id = manager.get_latest_chat_for_project("/test/project")
        
        # Should return None and not perform any database operations
        assert chat_id is None
        mock_connection.cursor.assert_not_called()


@pytest.mark.asyncio
async def test_list_project_chats(db_manager, mock_connection):
    """Test listing all chats for a project."""
    # Mock cursor.fetchall to return chats
    cursor = mock_connection.cursor.return_value
    cursor.fetchall.return_value = [
        {"id": 1, "created_at": 1234567890.0, "updated_at": 1234567900.0},
        {"id": 2, "created_at": 1234567910.0, "updated_at": 1234567920.0}
    ]
    
    # List chats
    chats = db_manager.list_project_chats("/test/project")
    
    # Verify that execute was called with the correct query
    cursor.execute.assert_called()
    execute_call = cursor.execute.call_args[0][0]
    # Check for partial query to avoid whitespace issues
    assert "SELECT id, created_at, updated_at" in execute_call
    assert "FROM chats" in execute_call
    assert "WHERE project_path = ?" in execute_call
    
    # Verify that chats were returned in the correct format
    assert len(chats) == 2
    assert chats[0]["id"] == 1
    assert chats[0]["created_at"] == 1234567890.0
    assert chats[1]["id"] == 2


@pytest.mark.asyncio
async def test_list_project_chats_with_persistence_disabled(mock_connection):
    """Test listing chats when persistence is disabled."""
    with patch("supernova.persistence.db_manager.loader.load_config") as mock_config:
        # Create a mock config with persistence disabled
        mock_config.return_value = MagicMock()
        mock_config.return_value.persistence.enabled = False
        
        manager = DatabaseManager(":memory:")
        
        # Try to list chats
        chats = manager.list_project_chats("/test/project")
        
        # Should return an empty list and not perform any database operations
        assert chats == []
        mock_connection.cursor.assert_not_called()


@pytest.mark.asyncio
async def test_db_manager_init_with_path_creation(mock_connection):
    """Test DatabaseManager initialization with path creation."""
    with patch("supernova.persistence.db_manager.loader.load_config") as mock_config:
        # Create a mock config with persistence enabled
        mock_config.return_value = MagicMock()
        mock_config.return_value.persistence.enabled = True
        mock_config.return_value.persistence.db_path = "/test/path/db.sqlite"
        
        # Mock Path operations
        with patch("pathlib.Path.parent", create=True) as mock_parent:
            with patch("pathlib.Path.mkdir") as mock_mkdir:
                mock_parent.mkdir = mock_mkdir
                
                # Initialize the DatabaseManager
                manager = DatabaseManager("/test/path/db.sqlite")
                
                # Verify that mkdir was called with the correct arguments
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True) 