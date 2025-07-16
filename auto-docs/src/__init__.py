"""
Auto-Docs: Automated Documentation Generator for Python Projects

A comprehensive tool that automatically generates documentation for Python repositories
using AI-powered analysis and intelligent code parsing.
"""

__version__ = "1.0.0"
__author__ = "Auto-Docs Team"
__email__ = "contact@auto-docs.dev"

from .analyzer import RepoAnalyzer
from .ai_generator import DocGenerator
from .git_watcher import GitWatcher

__all__ = ["RepoAnalyzer", "DocGenerator", "GitWatcher"]