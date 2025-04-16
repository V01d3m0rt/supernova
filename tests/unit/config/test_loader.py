import os
import json
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

import pytest
import yaml
from pydantic import ValidationError

from supernova.config.loader import (
    load_config, 
    _process_config_dict,
    _expand_env_vars,
    _find_config_file,
    get_config_value,
    set_config_value,
    save_config
)
from supernova.config.schema import SuperNovaConfig


def test_expand_env_vars():
    """Test expanding environment variables in strings."""
    # Test with ${VAR} format
    with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
        result = _expand_env_vars("Value is ${TEST_VAR}")
        assert result == "Value is test_value"
    
    # Test with $VAR format
    with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
        result = _expand_env_vars("Value is $TEST_VAR")
        assert result == "Value is test_value"
    
    # Test with non-existent variable
    result = _expand_env_vars("Value is ${NON_EXISTENT_VAR}")
    assert result == "Value is "
    
    # Test with no environment variables
    result = _expand_env_vars("Plain value")
    assert result == "Plain value"
    
    # Test with non-string input
    result = _expand_env_vars(123)
    assert result == 123


def test_process_config_dict():
    """Test processing a configuration dictionary to expand environment variables."""
    with patch.dict(os.environ, {"API_KEY": "test_key", "MODEL": "test-model"}):
        config_dict = {
            "llm_providers": {
                "test_provider": {
                    "api_key": "${API_KEY}",
                    "model": "$MODEL",
                    "temperature": 0.7
                }
            },
            "debug": True,
            "limits": [1, 2, 3]
        }
        
        processed = _process_config_dict(config_dict)
        
        # Check that environment variables were expanded
        assert processed["llm_providers"]["test_provider"]["api_key"] == "test_key"
        assert processed["llm_providers"]["test_provider"]["model"] == "test-model"
        
        # Check that non-string values were preserved
        assert processed["llm_providers"]["test_provider"]["temperature"] == 0.7
        assert processed["debug"] is True
        assert processed["limits"] == [1, 2, 3]


def test_process_config_dict_with_nested_lists():
    """Test processing a configuration with lists containing dictionaries."""
    with patch.dict(os.environ, {"API_KEY": "test_key"}):
        config_dict = {
            "providers": [
                {
                    "name": "provider1",
                    "api_key": "${API_KEY}",
                },
                {
                    "name": "provider2",
                    "api_key": "static_key",
                }
            ]
        }
        
        processed = _process_config_dict(config_dict)
        
        # Check that environment variables in lists of dicts were expanded
        assert processed["providers"][0]["api_key"] == "test_key"
        assert processed["providers"][1]["api_key"] == "static_key"


def test_find_config_file():
    """Test finding the configuration file in various locations."""
    # Mock the Path.exists method
    mock_exists = MagicMock()
    
    # Mock Path.cwd() to return a controlled path
    with patch("pathlib.Path.cwd") as mock_cwd:
        mock_cwd.return_value = Path("/cwd")
        
        # Create the expected path
        expected_path = Path("/cwd/.supernova/config.yaml")
        
        # Mock exists to return True only for the expected path
        def custom_exists(self):
            return str(self) == str(expected_path)
        
        # Apply the patch
        with patch.object(Path, "exists", custom_exists):
            # Should find local config
            config_path = _find_config_file()
            
            # Check the path is what we expect
            assert str(config_path) == str(expected_path)


def test_find_config_file_user_home():
    """Test finding the configuration file in user home directory."""
    # Mock Path.cwd() and Path.home()
    with patch("pathlib.Path.cwd") as mock_cwd:
        mock_cwd.return_value = Path("/cwd")
        
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = Path("/home/user")
            
            # Create the expected paths
            local_config_path = Path("/cwd/.supernova/config.yaml")
            user_config_path = Path("/home/user/.supernova/config.yaml")
            
            # Mock exists to return False for local config, True for user config
            def custom_exists(self):
                if str(self) == str(local_config_path):
                    return False
                if str(self) == str(user_config_path):
                    return True
                return False
            
            # Set up USER_CONFIG_PATH constant
            with patch("supernova.config.loader.USER_CONFIG_PATH", user_config_path):
                # Apply the patch
                with patch.object(Path, "exists", custom_exists):
                    # Should find user home config
                    config_path = _find_config_file()
                    
                    # Check the path is what we expect
                    assert str(config_path) == str(user_config_path)


def test_find_config_file_default():
    """Test finding the default configuration file."""
    # Mock Path.cwd() and Path.home()
    with patch("pathlib.Path.cwd") as mock_cwd:
        mock_cwd.return_value = Path("/cwd")
        
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = Path("/home/user")
            
            # Create the expected paths
            local_config_path = Path("/cwd/.supernova/config.yaml")
            user_config_path = Path("/home/user/.supernova/config.yaml")
            default_config_path = Path("/default/config.yaml")
            
            # Mock exists to return False for local and user config, True for default
            def custom_exists(self):
                if str(self) == str(local_config_path) or str(self) == str(user_config_path):
                    return False
                if str(self) == str(default_config_path):
                    return True
                return False
            
            # Set up constants
            with patch("supernova.config.loader.DEFAULT_CONFIG_PATH", default_config_path):
                with patch("supernova.config.loader.USER_CONFIG_PATH", user_config_path):
                    # Apply the patch
                    with patch.object(Path, "exists", custom_exists):
                        # Should find default config
                        config_path = _find_config_file()
                        
                        # Check the path is what we expect
                        assert str(config_path) == str(default_config_path)

@patch("pathlib.Path.exists")
def test_find_config_file_not_found(mock_exists):
    """Test behavior when no configuration file is found."""
    # Mock Path.exists to always return False
    mock_exists.return_value = False
    
    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        _find_config_file()


def test_load_config_with_valid_path(temp_dir):
    """Test loading config from a valid file path."""
    config_path = temp_dir / "test_config.yaml"
    test_config = {
        "llm_providers": {
            "test_provider": {
                "name": "test_provider",
                "api_base": "https://api.test.com",
                "api_key": "test_key",
                "model": "test-model",
                "provider_type": "openai",
                "provider": "openai"
            }
        },
        "project_context": {
            "key_files": ["README.md", "pyproject.toml"]
        }
    }
    
    with open(config_path, "w") as f:
        yaml.dump(test_config, f)
    
    # Patch the environment variable processing to avoid side effects
    with patch("supernova.config.loader._process_config_dict", return_value=test_config):
        config = load_config(config_path)
        
        # Verify config was loaded correctly
        assert "llm_providers" in config.model_dump()
        assert "test_provider" in config.model_dump()["llm_providers"]
        assert config.model_dump()["llm_providers"]["test_provider"]["api_key"] == "test_key"


@patch("supernova.config.loader._find_config_file")
def test_load_config_default_path(mock_find_config):
    """Test loading config from the default path."""
    # Mock finding a config file
    test_config_path = Path("/mock/path/config.yaml")
    mock_find_config.return_value = test_config_path
    
    # Mock opening and reading the config file
    test_config = {
        "llm_providers": {
            "test_provider": {
                "name": "test_provider",
                "api_base": "https://api.test.com",
                "api_key": "test_key",
                "model": "test-model",
                "provider_type": "openai",
                "provider": "openai"
            }
        },
        "project_context": {
            "key_files": ["README.md", "pyproject.toml"]
        }
    }
    
    m = mock_open(read_data=yaml.dump(test_config))
    
    with patch("builtins.open", m):
        with patch("supernova.config.loader._process_config_dict", return_value=test_config):
            config = load_config()
            
            # Verify _find_config_file was called
            mock_find_config.assert_called_once()
            
            # Verify config was loaded correctly
            assert "llm_providers" in config.model_dump()
            assert "test_provider" in config.model_dump()["llm_providers"]


@patch("supernova.config.loader._find_config_file")
def test_load_config_file_not_found(mock_find_config):
    """Test loading config when no file is found."""
    # Mock _find_config_file to raise FileNotFoundError
    mock_find_config.side_effect = FileNotFoundError("Could not find a configuration file")
    
    # Should return a default config
    config = load_config()
    
    # Verify default config was returned
    assert "llm_providers" in config.model_dump()
    assert "default" in config.model_dump()["llm_providers"]


@patch("supernova.config.loader._find_config_file")
def test_load_config_invalid_yaml(mock_find_config):
    """Test loading config with invalid YAML."""
    # Mock finding a config file
    test_config_path = Path("/mock/path/config.yaml")
    mock_find_config.return_value = test_config_path
    
    # Mock opening and reading an invalid YAML file
    invalid_yaml = "llm_providers: - invalid: yaml"
    
    with patch("builtins.open", mock_open(read_data=invalid_yaml)):
        # Should raise YAMLError
        with pytest.raises(yaml.YAMLError):
            load_config()


@patch("supernova.config.loader._find_config_file")
def test_load_config_validation_error(mock_find_config):
    """Test loading config with a valid YAML but invalid schema."""
    # Mock finding a config file
    test_config_path = Path("/mock/path/config.yaml")
    mock_find_config.return_value = test_config_path
    
    # Mock opening and reading a valid YAML file but with invalid schema
    invalid_config = {
        "llm_providers": {
            "test_provider": {
                # Missing required fields like "provider"
                "api_key": "test_key"
            }
        }
    }
    
    with patch("builtins.open", mock_open(read_data=yaml.dump(invalid_config))):
        with patch("supernova.config.loader._process_config_dict", return_value=invalid_config):
            # Should raise ValidationError
            with pytest.raises(Exception):
                load_config()



def test_get_config_value():
    """Test getting a configuration value by dot-notation path."""
    # Create a test config with the correct structure
    config_dict = {
        "llm_providers": {
            "test_provider": {
                "api_key": "test_key",
                "model": "test-model",
                "temperature": 0.7,
                "provider": "openai",  # Required field
                "provider_type": "openai"  # Optional but expected
            }
        },
        "debugging": {
            "show_session_state": False,
            "show_traceback": False
        },
        "project_context": {
            "key_files": ["README.md", "pyproject.toml"]
        }
    }
    
    # Create a SuperNovaConfig object
    config = SuperNovaConfig(**config_dict)
    
    # Test getting a nested value from llm_providers
    value, type_name = get_config_value(config, "llm_providers.test_provider.api_key")
    assert value == "test_key"
    assert type_name == "str"
    
    # Test getting a boolean value from debugging
    value, type_name = get_config_value(config, "debugging.show_session_state")
    assert value is False
    assert type_name == "bool"
    
    # Test getting a list value from project_context
    value, type_name = get_config_value(config, "project_context.key_files")
    assert value == ["README.md", "pyproject.toml"]
    assert type_name == "list"

def test_get_config_value_not_found():
    """Test getting a non-existent configuration value."""
    # Create a test config
    config_dict = {
        "llm_providers": {
            "test_provider": {
                "api_key": "test_key",
                "model": "test-model",  # Required field
                "provider": "openai"  # Required field
            }
        }
    }
    
    # Create a SuperNovaConfig object
    config = SuperNovaConfig(**config_dict)
    
    # Test getting a non-existent value
    with pytest.raises(KeyError):
        get_config_value(config, "non_existent_key")
    
    # Test getting a non-existent nested value
    with pytest.raises(KeyError):
        get_config_value(config, "llm_providers.test_provider.non_existent")


def test_set_config_value():
    """Test setting a configuration value by dot-notation path."""
    # Create a test config
    config_dict = {
        "llm_providers": {
            "test_provider": {
                "api_key": "test_key",
                "model": "test-model",
                "temperature": 0.7
            }
        },
        "debug": True,
        "limits": [1, 2, 3]
    }
    
    # Test setting a string value
    updated = set_config_value(config_dict, "llm_providers.test_provider.api_key", "new_key")
    assert updated["llm_providers"]["test_provider"]["api_key"] == "new_key"
    
    # Test setting a boolean value
    updated = set_config_value(config_dict, "debug", "false")
    assert updated["debug"] is False
    
    # Test setting a numeric value
    updated = set_config_value(config_dict, "llm_providers.test_provider.temperature", "0.5")
    assert updated["llm_providers"]["test_provider"]["temperature"] == 0.5
    
    # Test setting a list value
    updated = set_config_value(config_dict, "limits", "4,5,6")
    assert updated["limits"] == ["4", "5", "6"]


def test_set_config_value_create_path():
    """Test setting a configuration value for a path that doesn't exist."""
    # Create a test config
    config_dict = {
        "llm_providers": {}
    }
    
    # Test setting a value for a path that doesn't exist
    updated = set_config_value(config_dict, "llm_providers.new_provider.api_key", "new_key")
    assert updated["llm_providers"]["new_provider"]["api_key"] == "new_key"


def test_set_config_value_invalid_conversion():
    """Test setting a value with an invalid type conversion."""
    # Create a test config
    config_dict = {
        "debug": True
    }
    
    # Test setting an invalid boolean value
    with pytest.raises(ValueError):
        set_config_value(config_dict, "debug", "invalid_boolean")



def test_save_config():
    """Test saving a configuration to a file."""
    # Create a test config
    config_dict = {
        "llm_providers": {
            "test_provider": {
                "api_key": "test_key",
                "model": "test-model"
            }
        },
        "debugging": {"show_session_state": False, "show_traceback": False}
    }
    
    # Create a test path
    config_path = Path("/test/path/config.yaml")
    
    # Setup mocks with mock_open
    mo = mock_open()
    
    with patch("builtins.open", mo), \
         patch("pathlib.Path.parent") as mock_parent, \
         patch("yaml.dump") as mock_yaml_dump:
        
        # Mock parent.mkdir to avoid calls to filesystem
        mock_parent.return_value.mkdir = MagicMock()
        
        # Call the function
        saved_path = save_config(config_dict, config_path)
        
        # Verify open was called correctly
        mo.assert_called_once_with(config_path, "w")
        
        # Verify yaml.dump was called with correct arguments
        mock_yaml_dump.assert_called_once()
        args, kwargs = mock_yaml_dump.call_args
        assert args[0] == config_dict  # First arg should be the config dict
        assert args[1] == mo.return_value  # Second arg should be the file handle
        assert kwargs.get('default_flow_style') is False
        assert kwargs.get('sort_keys') is False
        
        # Assert the returned path is correct
        assert saved_path == config_path


def test_save_config_with_default_path():
    """Test saving a configuration with the default path."""
    # Create a test config
    config_dict = {
        "llm_providers": {
            "test_provider": {
                "api_key": "test_key",
                "model": "test-model"
            }
        }
    }
    
    # Default config path
    default_config_path = Path("/default/path/config.yaml")
    
    # Setup mocks with mock_open
    mo = mock_open()
    
    # Mock _find_config_file to return a default path
    with patch("supernova.config.loader._find_config_file", return_value=default_config_path), \
         patch("builtins.open", mo), \
         patch("pathlib.Path.parent") as mock_parent, \
         patch("yaml.dump") as mock_yaml_dump:
        
        # Mock parent.mkdir to avoid calls to filesystem
        mock_parent.return_value.mkdir = MagicMock()
        
        # Call the function
        saved_path = save_config(config_dict)
        
        # Verify open was called correctly
        mo.assert_called_once_with(default_config_path, "w")
        
        # Verify yaml.dump was called with correct arguments
        mock_yaml_dump.assert_called_once()
        args, kwargs = mock_yaml_dump.call_args
        assert args[0] == config_dict  # First arg should be the config dict
        assert args[1] == mo.return_value  # Second arg should be the file handle
        assert kwargs.get('default_flow_style') is False
        assert kwargs.get('sort_keys') is False
        
        # Assert the returned path is correct
        assert saved_path == default_config_path


def test_save_config_with_pydantic_model():
    """Test saving a configuration with a Pydantic model."""
    # Create a test config with proper structure
    config_dict = {
        "llm_providers": {
            "test_provider": {
                "api_key": "test_key",
                "model": "test-model",
                "provider": "openai",
            }
        },
        "project_context": {
            "key_files": ["README.md"]
        }
    }
    
    # Create a SuperNovaConfig object
    config = SuperNovaConfig(**config_dict)
    
    # Create a test path
    test_path = Path("/test/path/config.yaml")
    
    # Setup mocks with mock_open
    mo = mock_open()
    
    with patch("builtins.open", mo), \
         patch("pathlib.Path.parent") as mock_parent, \
         patch("yaml.dump") as mock_yaml_dump:
        
        # Mock parent.mkdir to avoid calls to filesystem
        mock_parent.return_value.mkdir = MagicMock()
        
        # Call the function
        saved_path = save_config(config, test_path)
        
        # Verify open was called correctly
        mo.assert_called_once_with(test_path, "w")
        
        # Verify yaml.dump was called with correct arguments
        mock_yaml_dump.assert_called_once()
        args, kwargs = mock_yaml_dump.call_args
        assert args[0] == config.model_dump(exclude_none=True)  # First arg should be the config dict
        assert args[1] == mo.return_value  # Second arg should be the file handle
        assert kwargs.get('default_flow_style') is False
        assert kwargs.get('sort_keys') is False
        
        # Assert the returned path is correct
        assert saved_path == test_path
