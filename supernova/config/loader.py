"""
SuperNova - AI-powered development assistant within the terminal.

Configuration loader for loading and validating config.yaml.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml
from dotenv import load_dotenv
from rich.console import Console

from supernova.config.schema import SuperNovaConfig

console = Console()

# Default paths
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"
USER_CONFIG_DIR = Path.home() / ".supernova"
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.yaml"


def _expand_env_vars(value: str) -> str:
    """
    Expand environment variables in a string.
    
    Args:
        value: String potentially containing environment variables
        
    Returns:
        String with environment variables expanded
    """
    if not isinstance(value, str):
        return value
    
    # Try to load environment variables from .env if it exists
    try:
        dotenv_path = Path.cwd() / ".env"
        if dotenv_path.exists():
            load_dotenv(dotenv_path)
    except (FileNotFoundError, OSError):
        # Gracefully handle cases where current directory doesn't exist or is inaccessible
        pass
    
    # Expand ${VAR} or $VAR style environment variables
    pattern = re.compile(r"\$\{([^}^{]+)\}|\$([a-zA-Z0-9_]+)")
    
    def _replace_var(match):
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, "")
    
    return pattern.sub(_replace_var, value)


def _process_config_dict(config_dict: Dict) -> Dict:
    """
    Process a configuration dictionary to expand environment variables.
    
    Args:
        config_dict: Dictionary containing configuration
        
    Returns:
        Processed dictionary with environment variables expanded
    """
    result = {}
    
    for key, value in config_dict.items():
        if isinstance(value, dict):
            result[key] = _process_config_dict(value)
        elif isinstance(value, list):
            result[key] = [
                _process_config_dict(item) if isinstance(item, dict) else
                _expand_env_vars(item) if isinstance(item, str) else
                item
                for item in value
            ]
        elif isinstance(value, str):
            result[key] = _expand_env_vars(value)
        else:
            result[key] = value
    
    return result


def _find_config_file() -> Path:
    """
    Find the configuration file to use.
    
    Returns:
        Path to the configuration file
    """
    # Check for .supernova/config.yaml in the current directory
    local_config = Path.cwd() / ".supernova" / "config.yaml"
    if local_config.exists():
        return local_config
    
    # Check for ~/.supernova/config.yaml
    if USER_CONFIG_PATH.exists():
        return USER_CONFIG_PATH
    
    # Fall back to the default config
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    
    raise FileNotFoundError("Could not find a configuration file")


def load_config(config_path: Optional[Union[str, Path]] = None) -> SuperNovaConfig:
    """
    Load and validate the SuperNova configuration.
    
    Args:
        config_path: Optional path to the configuration file
        
    Returns:
        Validated SuperNovaConfig object
    """
    if config_path is None:
        try:
            config_path = _find_config_file()
        except FileNotFoundError as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            console.print("Using default configuration")
            return SuperNovaConfig(llm_providers={
                "default": {
                    "provider": "openai",
                    "api_key": "dummy",
                    "model": "gpt-3.5-turbo",
                    "is_default": True
                }
            })
    else:
        config_path = Path(config_path)
    
    try:
        with open(config_path, "r") as f:
            config_dict = yaml.safe_load(f)
        
        # Process environment variables
        processed_config = _process_config_dict(config_dict)
        
        # Validate against the schema
        config = SuperNovaConfig(**processed_config)
        
        return config
    
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Configuration file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        console.print(f"[red]Error:[/red] Failed to parse YAML: {str(e)}")
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] Configuration validation failed: {str(e)}")
        raise


def get_config_value(config: SuperNovaConfig, key_path: str) -> Tuple[Any, str]:
    """
    Get a configuration value by its dot-notation path.
    
    Args:
        config: The SuperNovaConfig object
        key_path: Dot-notation path to the configuration value (e.g., "llm_providers.openai.model")
        
    Returns:
        Tuple of (value, type) where type is the string representation of the Python type
    """
    # Convert the config to a dict for easier nested access
    config_dict = config.model_dump()
    
    # Split the key path by dots
    keys = key_path.split('.')
    
    # Navigate through the config dict
    current = config_dict
    try:
        for key in keys:
            current = current[key]
    except (KeyError, TypeError):
        raise KeyError(f"Key '{key_path}' not found in configuration")
    
    # Return the value and its type
    return current, type(current).__name__


def set_config_value(config_dict: Dict, key_path: str, value: str) -> Dict:
    """
    Set a configuration value by its dot-notation path.
    
    Args:
        config_dict: The configuration dictionary
        key_path: Dot-notation path to the configuration value
        value: The string value to set (will be converted to appropriate type)
        
    Returns:
        Updated configuration dictionary
    """
    # Split the key path by dots
    keys = key_path.split('.')
    
    # Navigate to the parent of the target key
    current = config_dict
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        elif not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    
    # Get the target key (last part of the path)
    target_key = keys[-1]
    
    # Try to determine the appropriate type for the value
    if target_key in current:
        # Try to maintain the same type as the existing value
        existing_type = type(current[target_key])
        try:
            if existing_type == bool:
                # Special handling for boolean values
                if value.lower() in ('true', 'yes', '1'):
                    value_typed = True
                elif value.lower() in ('false', 'no', '0'):
                    value_typed = False
                else:
                    raise ValueError(f"Invalid boolean value: {value}")
            elif existing_type == int:
                value_typed = int(value)
            elif existing_type == float:
                value_typed = float(value)
            elif existing_type == list:
                # Parse as a comma-separated list
                value_typed = [item.strip() for item in value.split(',')]
            else:
                value_typed = value
            
            current[target_key] = value_typed
        except (ValueError, TypeError):
            raise ValueError(f"Cannot convert '{value}' to type {existing_type.__name__}")
    else:
        # If the key doesn't exist, try to guess the type
        if value.lower() in ('true', 'yes', '1', 'false', 'no', '0'):
            # Looks like a boolean
            current[target_key] = value.lower() in ('true', 'yes', '1')
        elif value.isdigit():
            # Looks like an integer
            current[target_key] = int(value)
        elif value.replace('.', '', 1).isdigit() and value.count('.') == 1:
            # Looks like a float
            current[target_key] = float(value)
        elif value.startswith('[') and value.endswith(']'):
            # Looks like a list
            try:
                # Try to parse as JSON
                import json
                current[target_key] = json.loads(value)
            except json.JSONDecodeError:
                # Fall back to comma-separated list
                stripped_value = value[1:-1].strip()
                if stripped_value:
                    current[target_key] = [item.strip() for item in stripped_value.split(',')]
                else:
                    current[target_key] = []
        else:
            # Default to string
            current[target_key] = value
    
    return config_dict


def save_config(config: Union[SuperNovaConfig, Dict], config_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Save the configuration to a file.
    
    Args:
        config: The SuperNovaConfig object or dictionary to save
        config_path: Optional path to save the configuration (default: use _find_config_file())
        
    Returns:
        Path to the saved configuration file
    """
    if config_path is None:
        try:
            config_path = _find_config_file()
        except FileNotFoundError:
            # If no config file exists, save to user config
            config_path = USER_CONFIG_PATH
            USER_CONFIG_DIR.mkdir(exist_ok=True, parents=True)
    else:
        config_path = Path(config_path)
        config_path.parent.mkdir(exist_ok=True, parents=True)
    
    # Convert config to dict if it's a Pydantic model
    if hasattr(config, 'model_dump'):
        config_dict = config.model_dump(exclude_none=True)
    else:
        config_dict = config
    
    # Save the config
    with open(config_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
    
    return config_path 