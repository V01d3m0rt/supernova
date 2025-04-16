import pytest
from pydantic import ValidationError

from supernova.config.schema import SuperNovaConfig, LLMProviderConfig


def test_llm_provider_config_valid():
    """Test that valid LLMProviderConfig is created correctly."""
    config = LLMProviderConfig(
        provider="openai",
        base_url="https://api.test.com",
        api_key="test_key",
        model="test-model",
        is_default=True,
        temperature=0.7,
        max_tokens=1000
    )
    
    assert config.provider == "openai"
    assert config.base_url == "https://api.test.com"
    assert config.api_key == "test_key"
    assert config.model == "test-model"
    assert config.is_default is True
    assert config.temperature == 0.7
    assert config.max_tokens == 1000


def test_llm_provider_config_defaults():
    """Test that LLMProviderConfig defaults are set correctly."""
    config = LLMProviderConfig(
        provider="openai",
        api_key="test_key",
        model="test-model"
    )
    
    assert config.is_default is False  # Default value
    assert config.temperature == 0.7   # Default value
    assert config.timeout == 60        # Default value instead of testing max_tokens


def test_llm_provider_config_invalid_provider():
    """Test that missing required fields raises ValidationError."""
    with pytest.raises(ValidationError):
        # Missing required 'model' field
        LLMProviderConfig(
            provider="openai",
            api_key="test_key"
        )


def test_supernova_config_valid():
    """Test that valid SuperNovaConfig is created correctly."""
    provider_config = LLMProviderConfig(
        provider="openai",
        base_url="https://api.test.com",
        api_key="test_key",
        model="test-model"
    )
    
    config = SuperNovaConfig(
        llm_providers={"test": provider_config},
        debugging={"show_traceback": True},
        chat={"history_limit": 20, "max_tool_iterations": 10},
        extensions={"enabled": True},
        project_context={"key_files": ["README.md", "pyproject.toml"]}
    )
    
    assert "test" in config.llm_providers
    assert config.debugging.show_traceback is True
    assert config.chat.history_limit == 20
    assert config.chat.max_tool_iterations == 10
    assert config.extensions.enabled is True
    assert "README.md" in config.project_context.key_files


def test_supernova_config_defaults():
    """Test that SuperNovaConfig defaults are set correctly."""
    provider_config = LLMProviderConfig(
        provider="openai",
        base_url="https://api.test.com",
        api_key="test_key",
        model="test-model"
    )
    
    config = SuperNovaConfig(
        llm_providers={"test": provider_config},
        project_context={"key_files": ["README.md"]}
    )
    
    # Check default values
    assert config.debugging.show_traceback is False
    assert config.chat.history_limit == 50  # Updated default value
    assert config.chat.max_tool_iterations == 5
    assert config.extensions.enabled is True 