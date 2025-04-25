"""
Tests for the ConfigManager class.
"""

import os
import tempfile
import logging
import yaml
import unittest
from unittest.mock import MagicMock, patch

from supernova.cli.chat.config.config_manager import ConfigManager


class TestConfigManager(unittest.TestCase):
    """Test suite for the ConfigManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.logger = MagicMock(spec=logging.Logger)
        self.manager = ConfigManager(self.logger)
        
        # Create a temporary file for config tests
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "config.yaml")

    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()

    def test_default_config(self):
        """Test that default configuration is loaded correctly."""
        self.assertEqual(self.manager.get("model.provider"), "openai")
        self.assertEqual(self.manager.get("model.name"), "gpt-4-turbo")
        self.assertEqual(self.manager.get("model.temperature"), 0.7)
        self.assertEqual(self.manager.get("ui.theme"), "dark")
        self.assertTrue(self.manager.get("tools.enabled"))

    def test_get_nested_config(self):
        """Test getting nested configuration values."""
        self.assertEqual(self.manager.get("model.provider"), "openai")
        self.assertEqual(self.manager.get("memory.paths")[0], ".supernova")
        
        # Test getting entire sections
        model_config = self.manager.get("model")
        self.assertIsInstance(model_config, dict)
        self.assertEqual(model_config["provider"], "openai")
        self.assertEqual(model_config["name"], "gpt-4-turbo")

    def test_get_with_default(self):
        """Test getting values with defaults for missing keys."""
        self.assertEqual(self.manager.get("nonexistent.key", "default_value"), "default_value")
        self.assertEqual(self.manager.get("model.nonexistent", 42), 42)

    def test_set_config_value(self):
        """Test setting configuration values."""
        # Set a top-level key
        self.manager.set("new_key", "new_value")
        self.assertEqual(self.manager.get("new_key"), "new_value")
        
        # Set a nested key
        self.manager.set("model.provider", "anthropic")
        self.assertEqual(self.manager.get("model.provider"), "anthropic")
        
        # Set a deeply nested key that doesn't exist yet
        self.manager.set("a.b.c.d", "deep_value")
        self.assertEqual(self.manager.get("a.b.c.d"), "deep_value")

    def test_load_config(self):
        """Test loading configuration from a file."""
        test_config = {
            "model": {
                "provider": "anthropic",
                "name": "claude-3-opus",
            },
            "ui": {
                "theme": "light",
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        self.manager.load_config(self.config_path)
        
        # Check that values were updated
        self.assertEqual(self.manager.get("model.provider"), "anthropic")
        self.assertEqual(self.manager.get("model.name"), "claude-3-opus")
        self.assertEqual(self.manager.get("ui.theme"), "light")
        
        # Check that non-updated values remain at defaults
        self.assertEqual(self.manager.get("model.temperature"), 0.7)
        self.assertTrue(self.manager.get("tools.enabled"))

    def test_load_invalid_config(self):
        """Test loading invalid configuration."""
        # Create an invalid config file
        with open(self.config_path, 'w') as f:
            f.write("This is not valid YAML")
        
        self.manager.load_config(self.config_path)
        
        # Ensure we're still using default values
        self.assertEqual(self.manager.get("model.provider"), "openai")
        self.assertTrue(self.logger.error.called)

    def test_save_config(self):
        """Test saving configuration to a file."""
        # Modify some settings
        self.manager.set("model.provider", "anthropic")
        self.manager.set("ui.theme", "light")
        
        # Save the configuration
        success = self.manager.save(self.config_path)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.config_path))
        
        # Load the configuration in a new manager to verify
        new_manager = ConfigManager(self.logger, self.config_path)
        self.assertEqual(new_manager.get("model.provider"), "anthropic")
        self.assertEqual(new_manager.get("ui.theme"), "light")

    @patch('builtins.open', side_effect=IOError("Test error"))
    def test_save_error_handling(self, mock_open):
        """Test error handling when saving fails."""
        success = self.manager.save("/nonexistent/path/config.yaml")
        self.assertFalse(success)
        self.assertTrue(self.logger.error.called)


if __name__ == '__main__':
    unittest.main() 