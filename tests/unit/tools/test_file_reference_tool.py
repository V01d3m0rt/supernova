"""
Unit tests for the FileReferenceTool.
"""

import os
import tempfile
import asyncio
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from supernova.tools.file_reference_tool import FileReferenceTool


class TestFileReferenceTool:
    """Test the FileReferenceTool."""
    
    def setup_method(self):
        """Set up the test environment."""
        self.tool = FileReferenceTool()
    
    def test_init(self):
        """Test initialization of the tool."""
        assert self.tool.name == "file_reference"
        assert "file" in self.tool.description.lower()
        assert "folder" in self.tool.description.lower()
    
    def test_schema(self):
        """Test that the schema is correctly defined."""
        schema = self.tool.get_schema()
        assert schema["name"] == "file_reference"
        assert "message" in schema["parameters"]["properties"]
        assert "working_dir" in schema["parameters"]["properties"]
        assert schema["parameters"]["required"] == ["message"]
    
    def test_file_reference_detection(self):
        """Test detection of file references in messages."""
        # Test with no references
        message = "This is a message with no file references."
        assert self.tool._find_file_references(message) == []
        
        # Test with one file reference
        message = "Please check this file @File /path/to/file.txt and tell me what's in it."
        assert self.tool._find_file_references(message) == ["/path/to/file.txt"]
        
        # Test with multiple file references
        message = "Check @File /path1.txt and @File /path2.txt for information."
        assert set(self.tool._find_file_references(message)) == {"/path1.txt", "/path2.txt"}
    
    def test_folder_reference_detection(self):
        """Test detection of folder references in messages."""
        # Test with no references
        message = "This is a message with no folder references."
        assert self.tool._find_folder_references(message) == []
        
        # Test with one folder reference
        message = "List all the files in this folder @Folder /path/to/folder and tell me what's there."
        assert self.tool._find_folder_references(message) == ["/path/to/folder"]
        
        # Test with multiple folder references
        message = "Compare @Folder /path1 and @Folder /path2 contents."
        assert set(self.tool._find_folder_references(message)) == {"/path1", "/path2"}
    
    def test_process_file_references_no_references(self):
        """Test processing a message with no references."""
        message = "This is a message with no references."
        result = self.tool.process_file_references(message, Path.cwd())
        
        assert result["success"] is True
        assert result["references_found"] is False
    
    def test_process_file_references_missing_file(self):
        """Test processing a message with references to non-existent files."""
        message = "Check this file @File /this/file/does/not/exist.txt"
        result = self.tool.process_file_references(message, Path.cwd())
        
        assert result["success"] is True
        assert result["references_found"] is True
        assert len(result["file_references"]) == 1
        assert result["file_references"][0]["exists"] is False
        assert "error" in result["file_references"][0]
    
    def test_process_file_references_with_real_files(self):
        """Test processing a message with references to real files."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
            temp_file.write("Test content")
            temp_file_path = temp_file.name
        
        try:
            # Create message with reference to the temporary file
            message = f"Check this file @File {temp_file_path}"
            result = self.tool.process_file_references(message, Path.cwd())
            
            assert result["success"] is True
            assert result["references_found"] is True
            assert len(result["file_references"]) == 1
            assert result["file_references"][0]["exists"] is True
            assert result["file_references"][0]["content"] == "Test content"
        finally:
            # Clean up
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    def test_process_folder_references_with_real_folder(self):
        """Test processing a message with references to real folders."""
        # Create a temporary directory with some files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some files in the directory
            (Path(temp_dir) / "file1.txt").write_text("Test content 1")
            (Path(temp_dir) / "file2.txt").write_text("Test content 2")
            # Create a subdirectory
            subdir = Path(temp_dir) / "subdir"
            subdir.mkdir()
            
            # Create message with reference to the temporary directory
            message = f"List files in @Folder {temp_dir}"
            result = self.tool.process_file_references(message, Path.cwd())
            
            assert result["success"] is True
            assert result["references_found"] is True
            assert len(result["folder_references"]) == 1
            assert result["folder_references"][0]["exists"] is True
            assert result["folder_references"][0]["file_count"] == 2
            assert result["folder_references"][0]["folder_count"] == 1
            assert "file1.txt" in result["folder_references"][0]["files"]
            assert "file2.txt" in result["folder_references"][0]["files"]
            assert "subdir" in result["folder_references"][0]["folders"]
    
    def test_execute(self):
        """Test the execute method."""
        with patch.object(FileReferenceTool, 'process_file_references') as mock_process:
            mock_process.return_value = {"success": True, "message": "Test result"}
            
            # Call execute with mock arguments
            result = self.tool.execute({
                "message": "Test message with @File /path/to/file.txt",
                "working_dir": "/tmp"
            })
            
            # Verify process_file_references was called with expected arguments
            mock_process.assert_called_once()
            args = mock_process.call_args[0]
            assert args[0] == "Test message with @File /path/to/file.txt"
            assert isinstance(args[1], Path)
            assert str(args[1]) == "/tmp"
            
            # Verify the result is passed through
            assert result == {"success": True, "message": "Test result"}
    
    @pytest.mark.asyncio
    async def test_execute_async(self):
        """Test the execute_async method."""
        with patch.object(FileReferenceTool, 'execute') as mock_execute:
            mock_execute.return_value = {"success": True, "message": "Test result"}
            
            # Call execute_async with mock arguments
            result = await self.tool.execute_async({
                "message": "Test message with @File /path/to/file.txt",
                "working_dir": "/tmp"
            })
            
            # Verify execute was called with expected arguments
            mock_execute.assert_called_once_with(
                {
                    "message": "Test message with @File /path/to/file.txt",
                    "working_dir": "/tmp"
                },
                None,  # context
                None   # working_dir
            )
            
            # Verify the result is passed through
            assert result == {"success": True, "message": "Test result"} 