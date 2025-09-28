# Changelog

All notable changes to SentientResearchAgent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Professional documentation structure with comprehensive README
- CONTRIBUTING.md with detailed contribution guidelines
- SECURITY.md for security policies
- CODE_OF_CONDUCT.md for community standards
- GitHub issue and PR templates
- Example scripts directory
- API documentation

### Changed
- Improved README with better visual hierarchy and professional badges
- Reorganized documentation for better accessibility

### Fixed
- Updated broken links and placeholder URLs
- Corrected repository references

## [0.1.0] - 2024-08-18

### Added
- Initial release of SentientResearchAgent framework
- Hierarchical task decomposition using MECE principle
- Three fundamental operations: Think, Write, Search
- Support for multiple LLM providers via LiteLLM
- Human-in-the-Loop (HITL) system with WebSocket integration
- Real-time task visualization in React frontend
- Stage tracing for complete transparency
- Configurable agent profiles
- Caching system for improved performance
- Emergency backup system for crash recovery
- Evaluation framework for benchmarking
- Docker support for containerized deployment
- Comprehensive logging system
- Project management with session persistence

### Features
- **Core Framework**
  - SystemManager for centralized orchestration
  - ExecutionEngine for task flow management
  - TaskGraph for hierarchical task representation
  - NodeProcessor for individual task execution
  - HITLCoordinator for human intervention

- **Agent System**
  - Pre-built agent profiles (deep_research, general)
  - Custom agent creation support
  - Tool-augmented agents with Exa search
  - Parallel and sequential task execution

- **Frontend**
  - Interactive task graph visualization
  - Real-time execution monitoring
  - Project switching and management
  - Dark/light theme support
  - Export functionality for results

- **Developer Tools**
  - PDM for Python dependency management
  - TypeScript support for frontend
  - Comprehensive configuration system
  - Emergency backup recovery
  - Detailed execution tracing

### Dependencies
- Python 3.12+
- Node.js 18+
- React 18
- Flask with SocketIO
- NetworkX for graph operations
- Pydantic for data validation
- LiteLLM for LLM integration
- Agno for agent framework

## [0.0.1-alpha] - 2024-07-01

### Added
- Initial proof of concept
- Basic hierarchical task decomposition
- Simple agent framework
- Command-line interface

---

## Version History Guidelines

### Version Numbering
- **Major (X.0.0)**: Breaking changes to API or framework architecture
- **Minor (0.X.0)**: New features, backwards compatible
- **Patch (0.0.X)**: Bug fixes and minor improvements

### Categories
- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security vulnerability fixes

[Unreleased]: https://github.com/salzubi401/SentientResearchAgent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/salzubi401/SentientResearchAgent/releases/tag/v0.1.0
[0.0.1-alpha]: https://github.com/salzubi401/SentientResearchAgent/releases/tag/v0.0.1-alpha