# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-12-20

### Added
- Initial release of Remote Executor
- SSH command execution with non-interactive mode
- SFTP file upload and download functionality
- Multi-server configuration support
- JSON and plain text output formats
- Connection testing and server info commands
- Support for both password and SSH key authentication
- Configuration file support (config.json)
- Environment variable support for credentials
- AI-friendly design for use with Claude Code and other AI assistants

### Security
- Moved sensitive credentials from code to config.json
- Added .gitignore to prevent credential leakage
- Support for SSH key authentication (recommended over passwords)
- Environment variable support for secure credential management

### Documentation
- Comprehensive README with usage examples
- Configuration examples (config.example.json)
- Apache License 2.0 (with patent protection)
- Security best practices guide
- License explanation guide (LICENSE_EXPLAINED.md)

## [Unreleased]

### Planned Features
- Batch command execution
- Session persistence and reuse
- Directory upload/download (recursive)
- Command history and logging
- Interactive shell mode (optional)
- Multiple simultaneous server connections
- Configuration encryption
- Web-based dashboard (optional)

---

## Version History

### Version 1.0.0 (2025-12-20)
First stable release with core functionality for remote server management via SSH.
