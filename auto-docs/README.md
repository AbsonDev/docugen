# Auto-Docs

🤖 **Automated Documentation Generator for Python Projects**

Auto-Docs is a comprehensive tool that automatically generates professional documentation for Python repositories using AI-powered analysis and intelligent code parsing. It integrates seamlessly with git workflows to keep your documentation up-to-date with every commit.

## ✨ Features

- **🔍 AST-based Code Analysis**: Deep parsing of Python code to extract functions, classes, and modules
- **🤖 AI-Powered Documentation**: Uses Groq API with llama3-8b-8192 model for intelligent documentation generation
- **🔄 Git Integration**: Automatic documentation updates via git hooks
- **📋 CLI Interface**: Comprehensive command-line interface for all operations
- **💾 Backup System**: Automatic backup of previous documentation versions
- **⚡ Rate Limiting**: Smart API usage to stay within free tier limits
- **🎯 Incremental Updates**: Only processes changed files for efficiency
- **🔧 Highly Configurable**: Customizable templates, patterns, and settings

## 🚀 Quick Start

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd auto-docs
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Get your free Groq API key from [Groq Console](https://console.groq.com/)

### Basic Usage

1. **Initialize auto-docs in your project:**
```bash
python -m src.main init --repo /path/to/your/project
```

2. **Generate documentation:**
```bash
python -m src.main analyze --repo /path/to/your/project
```

3. **Install git hooks for automatic updates:**
```bash
python -m src.main install-hook --repo /path/to/your/project
```

4. **Check status:**
```bash
python -m src.main status --repo /path/to/your/project
```

## 📖 Commands

### `init`
Initialize auto-docs configuration for a repository.
```bash
python -m src.main init --repo .
```

### `analyze`
Analyze repository and generate documentation.
```bash
python -m src.main analyze --repo . --output docs --include-examples
```

Options:
- `--output, -o`: Output directory (default: docs)
- `--format, -f`: Output format (default: markdown)
- `--include-examples`: Include usage examples
- `--include-complexity`: Include complexity metrics
- `--max-files`: Maximum number of files to process

### `install-hook`
Install git hook for automatic documentation generation.
```bash
python -m src.main install-hook --repo . --hook-type post-commit
```

Options:
- `--hook-type`: Type of git hook (default: post-commit)
- `--force`: Force installation (overwrite existing hook)

### `update`
Update documentation for changed files.
```bash
python -m src.main update --repo . --since HEAD~1
```

Options:
- `--since`: Update files changed since this commit
- `--force`: Force update all files

### `readme`
Generate project README documentation.
```bash
python -m src.main readme --repo . --output README.md
```

### `status`
Show auto-docs status and configuration.
```bash
python -m src.main status --repo .
```

### `uninstall`
Uninstall git hooks and clean up auto-docs.
```bash
python -m src.main uninstall --repo .
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in your project root:

```env
GROQ_API_KEY=your_groq_api_key_here
DEFAULT_MODEL=llama3-8b-8192
MAX_TOKENS=1000
TEMPERATURE=0.3
MAX_REQUESTS_PER_MINUTE=100
OUTPUT_FORMAT=markdown
BACKUP_ENABLED=true
VERBOSE_MODE=false
```

### Project Configuration

Auto-docs creates a `.auto-docs.json` file for project-specific settings:

```json
{
  "enabled": true,
  "auto_update": true,
  "backup_enabled": true,
  "docs_directory": "docs",
  "exclude_patterns": ["__pycache__", ".git", "venv", "env"],
  "include_examples": true,
  "include_type_hints": true,
  "max_file_size": 1000000
}
```

## 🛠️ Project Structure

```
auto-docs/
├── src/
│   ├── analyzer.py      # AST-based code analysis
│   ├── ai_generator.py  # AI documentation generation
│   ├── git_watcher.py   # Git integration and hooks
│   └── main.py          # CLI interface
├── templates/
│   └── doc_template.md  # Documentation template
├── hooks/
│   ├── post-commit      # Git post-commit hook
│   └── pre-push         # Git pre-push hook
├── config/
│   └── default_config.json  # Default configuration
├── tests/               # Comprehensive test suite
└── requirements.txt     # Python dependencies
```

## 🧪 Testing

Run the test suite:

```bash
python -m pytest tests/ -v
```

Test coverage:
```bash
python -m pytest tests/ --cov=src --cov-report=html
```

## 🔧 Development

### Requirements

- Python 3.8+
- Git
- Groq API key (free tier available)

### macOS Apple Silicon Compatibility

This project is optimized for macOS with Apple Silicon (M1/M2/M3/M4) processors. All dependencies are compatible with arm64 architecture.

### Adding New Features

1. **Code Analysis**: Extend `analyzer.py` for new language features
2. **AI Generation**: Modify prompts in `ai_generator.py` for better documentation
3. **Git Integration**: Add new hook types in `git_watcher.py`
4. **CLI Commands**: Add new commands in `main.py`

## 📊 API Usage

Auto-docs is designed to work within Groq's free tier:

- **Free Tier**: 14,400 requests/day
- **Rate Limiting**: 100 requests/minute (configurable)
- **Token Optimization**: Smart context management to minimize token usage
- **Caching**: Avoids redundant API calls

## 🔒 Security

- API keys are stored in environment variables
- No sensitive data is logged or transmitted
- Git hooks are sandboxed and safe
- All file operations are validated

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Groq](https://groq.com/) for providing free AI API access
- [Click](https://click.palletsprojects.com/) for the CLI framework
- [GitPython](https://gitpython.readthedocs.io/) for git integration
- [AST](https://docs.python.org/3/library/ast.html) for Python code parsing

## 📞 Support

- **Issues**: Report bugs and feature requests on GitHub Issues
- **Documentation**: Full documentation available in the `docs/` directory
- **Examples**: Check the `examples/` directory for usage examples

---

**Made with ❤️ for Python developers who value good documentation**

*Auto-Docs: Because great code deserves great documentation, automatically.*