"""
Configuration manager for chat sessions.

This module provides a configuration manager for chat sessions, including default settings,
loading configuration from files, and validating configuration values.
"""

import os
import yaml
from typing import Any, Dict, List, Optional, Union
import logging


class ConfigManager:
    """
    Configuration manager for chat sessions.
    
    This class handles loading, validating, and providing access to configuration 
    settings for chat sessions.
    """
    
    DEFAULT_CONFIG = {
        "model": {
            "provider": "openai",
            "name": "gpt-4-turbo",
            "temperature": 0.7,
            "max_tokens": 4096,
        },
        "system_prompt": {
            "token_allocation": {
                "core_instructions": 0.3,
                "tools": 0.3,
                "context": 0.4,
            }
        },
        "ui": {
            "theme": "dark",
            "animation_speed": 0.01,
            "show_loading": True,
        },
        "tools": {
            "enabled": True,
            "max_iterations": 5,
        },
        "memory": {
            "enabled": True,
            "paths": [
                ".supernova",
                "memory-bank",
            ],
            "priority_files": [
                "projectbrief.md",
                "activeContext.md",
                "progress.md",
            ],
        },
    }
    
    def __init__(self, logger: logging.Logger, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            logger: Logger instance
            config_path: Path to the configuration file (optional)
        """
        self.logger = logger
        self.config = self.DEFAULT_CONFIG.copy()
        
        if config_path and os.path.exists(config_path):
            self.load_config(config_path)
    
    def load_config(self, config_path: str) -> None:
        """
        Load configuration from a file.
        
        Args:
            config_path: Path to the configuration file
        """
        try:
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                
            if user_config and isinstance(user_config, dict):
                # Recursively update default config with user config
                self._deep_update(self.config, user_config)
                self.logger.info(f"Loaded configuration from {config_path}")
            else:
                self.logger.warning(f"Invalid configuration format in {config_path}, using defaults")
        except Exception as e:
            self.logger.error(f"Error loading configuration from {config_path}: {str(e)}")
            self.logger.info("Using default configuration")
    
    def _deep_update(self, d: Dict[str, Any], u: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively update a dictionary with another dictionary.
        
        Args:
            d: The dictionary to update
            u: The dictionary with updates
            
        Returns:
            The updated dictionary
        """
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                d[k] = self._deep_update(d[k], v)
            else:
                d[k] = v
        return d
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: The configuration key (dot-separated for nested keys)
            default: Default value if the key doesn't exist
            
        Returns:
            The configuration value or default
        """
        try:
            if '.' in key:
                # Handle nested keys
                parts = key.split('.')
                value = self.config
                for part in parts:
                    value = value.get(part, {})
                
                # If we reached the end and have a non-dict value, return it
                if value == {} or isinstance(value, dict) and not value:
                    return default
                return value
            else:
                return self.config.get(key, default)
        except Exception:
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: The configuration key (dot-separated for nested keys)
            value: The value to set
        """
        if '.' in key:
            # Handle nested keys
            parts = key.split('.')
            current = self.config
            
            # Navigate to the innermost dictionary
            for part in parts[:-1]:
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]
            
            # Set the value
            current[parts[-1]] = value
        else:
            self.config[key] = value
    
    def save(self, config_path: str) -> bool:
        """
        Save the current configuration to a file.
        
        Args:
            config_path: Path to save the configuration to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
            with open(config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
            self.logger.info(f"Saved configuration to {config_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving configuration to {config_path}: {str(e)}")
            return False 