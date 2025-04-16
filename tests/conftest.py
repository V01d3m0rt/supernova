import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from supernova.config.schema import SuperNovaConfig, LLMProviderConfig
from supernova.core.llm_provider import LLMProvider
from supernova.core.tool_manager import ToolManager


@pytest.fixture
def cli_runner():
    """Fixture for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        yield Path(tmpdir)
        os.chdir(old_cwd)


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    provider_config = LLMProviderConfig(
        provider="openai",
        base_url="https://api.test.com",
        api_key="test_key",
        model="test-model",
        is_default=True,
        temperature=0.7,
        max_tokens=1000
    )
    
    return SuperNovaConfig(
        llm_providers={"test_provider": provider_config},
        debugging={"show_traceback": False},
        chat={"history_limit": 10, "max_tool_iterations": 5},
        tools={"enabled": True},
        project_context={"key_files": ["README.md"]}
    )


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider for testing."""
    provider = MagicMock(spec=LLMProvider)
    provider.get_completion = MagicMock()
    provider.get_completion.return_value = {"choices": [{"message": {"content": "Test response"}}]}
    return provider


@pytest.fixture
def mock_tool_manager():
    """Create a mock tool manager for testing."""
    with patch.object(ToolManager, 'load_tools') as mock_load:
        mock_tool = MagicMock()
        mock_tool.get_name.return_value = "test_tool"
        mock_tool.get_description.return_value = "Test tool for testing"
        mock_tool.get_required_args.return_value = {"arg1": "string"}
        mock_tool.execute.return_value = "Tool executed successfully"
        
        mock_load.return_value = {"test_tool": mock_tool}
        yield ToolManager 