"""
Unit tests for the ChatSession's file reference processing.
"""

import os
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from supernova.cli.chat_session import ChatSession
from supernova.tools.file_reference_tool import FileReferenceTool


class TestChatSessionFileReferences:
    """Test the file reference processing in ChatSession."""
    
    def setup_method(self):
        """Set up the test environment."""
        # Mock config and dependencies
        self.config = MagicMock()
        self.db = MagicMock()
        
        # Create a temporary directory for the tests
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        
        # Initialize the chat session with the test directory
        self.session = ChatSession(
            config=self.config,
            db=self.db,
            initial_directory=self.test_dir
        )
    
    def teardown_method(self):
        """Clean up after the tests."""
        self.temp_dir.cleanup()
    
    def test_process_message_no_references(self):
        """Test that a message with no references is unchanged."""
        message = "This is a message with no file references."
        processed_message, context = self.session.process_message_references(message)
        
        # The message should be unchanged
        assert processed_message == message
        # No context should be added
        assert context == ""
    
    def test_process_message_with_references_tool_fails(self):
        """Test handling when the file reference tool fails."""
        # Mock the file reference tool to return a failure
        self.session.file_reference_tool.execute = MagicMock(
            return_value={"success": False, "error": "Tool failed"}
        )
        
        message = "Check this file @File /path/to/file.txt"
        processed_message, context = self.session.process_message_references(message)
        
        # The message should be unchanged when the tool fails
        assert processed_message == message
        # No context should be added
        assert context == ""
        
        # The tool should have been called with the right arguments
        self.session.file_reference_tool.execute.assert_called_once_with({
            "message": message,
            "working_dir": str(self.test_dir)
        })
    
    def test_process_message_no_references_found(self):
        """Test handling when no references are found in the message."""
        # Mock the file reference tool to return success but no references
        self.session.file_reference_tool.execute = MagicMock(
            return_value={"success": True, "references_found": False}
        )
        
        message = "This message has @File syntax but the tool couldn't parse it"
        processed_message, context = self.session.process_message_references(message)
        
        # The message should be unchanged when no references are found
        assert processed_message == message
        # No context should be added
        assert context == ""
    
    def test_process_message_with_file_references(self):
        """Test processing a message with file references."""
        # Create a test file
        test_file = self.test_dir / "test_file.txt"
        test_file.write_text("This is test content")
        
        # Mock the file reference tool to return success with file data
        self.session.file_reference_tool.execute = MagicMock(
            return_value={
                "success": True,
                "references_found": True,
                "file_references": [
                    {
                        "path": str(test_file),
                        "exists": True,
                        "type": "file",
                        "size": 20,
                        "content": "This is test content"
                    }
                ],
                "folder_references": []
            }
        )
        
        message = f"Check this file @File {test_file}"
        processed_message, context = self.session.process_message_references(message)
        
        # The processed message should include the file content
        assert message in processed_message
        assert "processed the file and folder references" in processed_message
        assert "1 file references" in processed_message
        assert "0 folder references" in processed_message
        
        # The context should include the file content
        assert str(test_file) in context
        assert "This is test content" in context
    
    def test_process_message_with_folder_references(self):
        """Test processing a message with folder references."""
        # Create test directory structure
        test_subdir = self.test_dir / "test_subdir"
        test_subdir.mkdir()
        (test_subdir / "file1.txt").write_text("File 1 content")
        (test_subdir / "file2.txt").write_text("File 2 content")
        
        # Mock the file reference tool to return success with folder data
        self.session.file_reference_tool.execute = MagicMock(
            return_value={
                "success": True,
                "references_found": True,
                "file_references": [],
                "folder_references": [
                    {
                        "path": str(test_subdir),
                        "exists": True,
                        "type": "folder",
                        "file_count": 2,
                        "folder_count": 0,
                        "files": ["file1.txt", "file2.txt"],
                        "folders": []
                    }
                ]
            }
        )
        
        message = f"List files in @Folder {test_subdir}"
        processed_message, context = self.session.process_message_references(message)
        
        # The processed message should include the folder info
        assert message in processed_message
        assert "processed the file and folder references" in processed_message
        assert "0 file references" in processed_message
        assert "1 folder references" in processed_message
        
        # The context should include the folder structure
        assert str(test_subdir) in context
        assert "Files (2)" in context
        assert "file1.txt" in context
        assert "file2.txt" in context
    
    def test_process_message_with_both_references(self):
        """Test processing a message with both file and folder references."""
        # Create test file and directory structure
        test_file = self.test_dir / "test_file.txt"
        test_file.write_text("This is test content")
        
        test_subdir = self.test_dir / "test_subdir"
        test_subdir.mkdir()
        (test_subdir / "file1.txt").write_text("File 1 content")
        
        # Mock the file reference tool to return success with both file and folder data
        self.session.file_reference_tool.execute = MagicMock(
            return_value={
                "success": True,
                "references_found": True,
                "file_references": [
                    {
                        "path": str(test_file),
                        "exists": True,
                        "type": "file",
                        "size": 20,
                        "content": "This is test content"
                    }
                ],
                "folder_references": [
                    {
                        "path": str(test_subdir),
                        "exists": True,
                        "type": "folder",
                        "file_count": 1,
                        "folder_count": 0,
                        "files": ["file1.txt"],
                        "folders": []
                    }
                ]
            }
        )
        
        message = f"Check @File {test_file} and @Folder {test_subdir}"
        processed_message, context = self.session.process_message_references(message)
        
        # The processed message should include both file and folder info
        assert message in processed_message
        assert "processed the file and folder references" in processed_message
        assert "1 file references" in processed_message
        assert "1 folder references" in processed_message
        
        # The context should include both file content and folder structure
        assert str(test_file) in context
        assert "This is test content" in context
        assert str(test_subdir) in context
        assert "Files (1)" in context
        assert "file1.txt" in context 