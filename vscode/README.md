# SuperNova for VS Code

**Note: This extension is currently in development and not yet available on the VS Code Marketplace.**

## Overview

SuperNova is an AI-powered development assistant that integrates directly with VS Code, providing contextual assistance for your codebase.

## Features (Planned)

- Interactive chat panel within VS Code
- Context-aware code suggestions
- Execution of commands with confirmation
- Project analysis and navigation
- File and symbol navigation
- Integration with multiple LLM providers

## Development Setup

This extension is currently in development. To set up the development environment:

1. Install the SuperNova Python package:
   ```bash
   pip install supernova
   ```

2. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/supernova.git
   cd supernova/vscode
   ```

3. Install dependencies:
   ```bash
   npm install
   ```

4. Open the project in VS Code:
   ```bash
   code .
   ```

5. Press F5 to start debugging the extension in a new VS Code window.

## Extension Settings

The extension will provide the following settings:

* `supernova.llmProvider`: LLM provider to use (openai, anthropic, lmstudio, ollama)
* `supernova.llmModel`: Model to use for the selected provider
* `supernova.pythonPath`: Path to Python executable with SuperNova installed

## Commands

* `SuperNova: Start Chat`: Open the SuperNova chat interface
* `SuperNova: Analyze Project`: Analyze the current project
* `SuperNova: Execute Command`: Execute a command through SuperNova

## Known Issues

- This extension is currently in development and not fully functional
- Integration with the SuperNova Python package is still being implemented
- UI components are placeholders for future development

## Release Notes

### 0.1.0 (Development)

Initial development version with:
- Basic command registration
- Placeholder UI components
- Integration points for SuperNova Python package

## Contributing

To contribute to the SuperNova VS Code extension:

1. Review the TODOs in the code
2. Check the `supernova/integrations/vscode_integration.py` file for integration points
3. Follow the development setup steps above
4. Submit a pull request with your changes

## License

MIT 