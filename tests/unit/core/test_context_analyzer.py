import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from supernova.core.context_analyzer import (
    analyze_project,
    _check_git_repository,
    _find_key_files,
    _determine_project_type
)


@pytest.fixture
def mock_repo():
    """Create a mock Git repository for testing."""
    repo = MagicMock()
    repo.git.log.return_value = "commit abc123\nAuthor: Test User\nDate: 2023-01-01\n\n    Test commit"
    repo.working_dir = "/test/repo"
    return repo


@pytest.mark.asyncio
async def test_check_git_repository_success():
    """Test successful repository info retrieval."""
    # Mock git_utils.get_repository_info
    with patch("supernova.integrations.git_utils.get_repository_info", new_callable=AsyncMock) as mock_git:
        mock_git.return_value = (True, {"branch": "main", "recent_commits": "commit1\ncommit2"})
        
        # Call _check_git_repository
        is_git_repo, repo_info = await _check_git_repository(Path("/test/repo"))
        
        # Verify git_utils.get_repository_info was called with the correct path
        mock_git.assert_called_once_with(Path("/test/repo"))
        
        # Check that repo_info contains the expected data
        assert is_git_repo is True
        assert repo_info["branch"] == "main"
        assert "commit1" in repo_info["recent_commits"]


@pytest.mark.asyncio
async def test_check_git_repository_failure():
    """Test repository info retrieval when not in a Git repository."""
    # Mock git_utils.get_repository_info to raise an exception
    with patch("supernova.integrations.git_utils.get_repository_info", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = Exception("Not a Git repository")
        
        # Call _check_git_repository
        is_git_repo, repo_info = await _check_git_repository(Path("/not/a/repo"))
        
        # Verify git_utils.get_repository_info was called with the correct path
        mock_git.assert_called_once_with(Path("/not/a/repo"))
        
        # Check that the function handled the exception properly
        assert is_git_repo is False
        assert repo_info == {}


@pytest.mark.asyncio
async def test_find_key_files(temp_dir):
    """Test finding key files in a directory."""
    # Create some test files
    readme_path = temp_dir / "README.md"
    gitignore_path = temp_dir / ".gitignore"
    package_json_path = temp_dir / "package.json"
    
    readme_path.write_text("# Test Project")
    gitignore_path.write_text("node_modules\n*.log")
    package_json_path.write_text('{"name": "test-project", "version": "1.0.0"}')
    
    # Define key file patterns
    key_file_patterns = ["README.md", ".gitignore", "package.json"]
    
    # Call _find_key_files
    key_files = await _find_key_files(temp_dir, key_file_patterns)
    
    # Check that the key files were found
    found_names = [f.name for f in key_files]
    assert "README.md" in found_names
    assert ".gitignore" in found_names
    assert "package.json" in found_names
    
    # Check the number of files found
    assert len(key_files) == 3


def test_determine_project_type():
    """Test determining project type based on key files."""
    # Test Python project
    python_files = [Path("pyproject.toml"), Path("requirements.txt")]
    assert _determine_project_type(python_files) == "Python"
    
    # Test JavaScript/Node.js project
    node_files = [Path("package.json"), Path("index.js")]
    assert _determine_project_type(node_files) == "JavaScript/Node.js"
    
    # Test Java/Maven project
    maven_files = [Path("pom.xml"), Path("src/main/java/App.java")]
    assert _determine_project_type(maven_files) == "Java/Maven"
    
    # Test Docker project
    docker_files = [Path("Dockerfile"), Path("docker-compose.yml")]
    assert _determine_project_type(docker_files) == "Docker"
    
    # Test generic project (no specific identifiers)
    generic_files = [Path("some-file.txt"), Path("another-file.md")]
    assert _determine_project_type(generic_files) == "Generic"


@pytest.mark.asyncio
async def test_analyze_project():
    """Test analyzing a project directory."""
    # Create mock async functions
    with patch("supernova.core.context_analyzer._check_git_repository", new_callable=AsyncMock) as mock_git:
        with patch("supernova.core.context_analyzer._find_key_files", new_callable=AsyncMock) as mock_find:
            with patch("supernova.core.context_analyzer._determine_project_type") as mock_determine:
                with patch("supernova.config.loader.load_config") as mock_config:
                    with patch("pathlib.Path.exists", return_value=True):
                        with patch("pathlib.Path.is_dir", return_value=True):
                            with patch("pathlib.Path.resolve", return_value=Path("/test/project")):
                                with patch("pathlib.Path.__str__", return_value="/test/project"):
                                    # Set up mocks
                                    mock_git.return_value = (True, {"branch": "main", "recent_commits": "commit1\ncommit2"})
                                    
                                    # Mock finding key files
                                    key_files = [Path("README.md"), Path("package.json")]
                                    mock_find.return_value = key_files
                                    
                                    # Mock project type determination
                                    mock_determine.return_value = "JavaScript/Node.js"
                                    
                                    # Mock config
                                    config = MagicMock()
                                    config.project_context.key_files = ["README.md", "package.json"]
                                    mock_config.return_value = config
                                    
                                    # Call analyze_project
                                    summary = await analyze_project(Path("/test/project"))
                                    
                                    # Verify results
                                    assert "JavaScript/Node.js" in summary
                                    assert "main" in summary
                                    assert "README.md" in summary 