# Security Policy

## Supported Versions

SuperNova is currently in alpha development. Security updates are provided for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.0.48-alpha | :white_check_mark: |
| < 0.0.48  | :x:                |

As this is a pre-release project, we recommend always using the latest version.

## Security Considerations

SuperNova is an AI-powered terminal assistant that:

1. Executes commands in your terminal with your permission
2. Analyzes your codebase for context
3. Communicates with external LLM providers (unless using local models)

Please be aware of the following security implications:

- **Command Execution**: Always review commands before allowing SuperNova to execute them
- **API Keys**: Keep your LLM provider API keys secure
- **Sensitive Code**: Consider using local models via LM Studio for sensitive projects
- **Network Access**: When using remote LLM providers, code context is sent to their APIs

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please:

1. **Do Not** disclose the vulnerability publicly until it has been addressed
2. Email the security vulnerability to [nikhil.j2se@gmail.com](mailto:nikhil.j2se@gmail.com) with:
   - A description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any proposed mitigations if you have them

### What to Expect

- **Acknowledgment**: We will acknowledge your report within 48 hours
- **Updates**: We will provide updates on the progress of addressing the vulnerability at least every 7 days
- **Disclosure**: Once the vulnerability is fixed, we will coordinate with you on the disclosure timeline
- **Credit**: With your permission, we will acknowledge your contribution in the release notes

### Security Response Process

1. **Triage**: We will evaluate the vulnerability and determine its impact
2. **Fix**: We will develop and test a fix for the vulnerability
3. **Release**: We will release a patched version and notify users
4. **Disclosure**: We will publish details about the vulnerability after users have had time to update

## Security Best Practices for Users

When using SuperNova, we recommend:

1. **Review Commands**: Always review suggested commands before execution
2. **Use Environment Variables**: Store API keys in environment variables instead of directly in config files
3. **Regular Updates**: Keep SuperNova updated to the latest version
4. **Limited Scope**: Initialize SuperNova in project-specific directories rather than system-wide directories
5. **Sensitive Data**: Avoid using SuperNova in repositories containing sensitive credentials or personal data

## Security Features

SuperNova includes the following security features:

- Command execution requires explicit user confirmation
- Configuration files are stored locally in the project directory
- API keys can be set via environment variables
- Support for local LLM execution via LM Studio
- Chat history is stored locally in your user directory 
