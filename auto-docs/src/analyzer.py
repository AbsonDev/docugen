"""
Code analyzer module for auto-docs.

This module provides functionality to analyze Python repositories using AST parsing
and extract metadata about functions, classes, and modules for documentation generation.
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from datetime import datetime
import git
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    """Information about a Python function."""
    name: str
    args: List[str]
    defaults: List[str]
    docstring: Optional[str]
    return_annotation: Optional[str]
    line_number: int
    decorators: List[str]
    is_async: bool
    type_hints: Dict[str, str]


@dataclass
class ClassInfo:
    """Information about a Python class."""
    name: str
    bases: List[str]
    docstring: Optional[str]
    methods: List[FunctionInfo]
    line_number: int
    decorators: List[str]
    attributes: List[str]


@dataclass
class ModuleInfo:
    """Information about a Python module."""
    file_path: str
    docstring: Optional[str]
    functions: List[FunctionInfo]
    classes: List[ClassInfo]
    imports: List[str]
    constants: List[str]
    last_modified: datetime


class RepoAnalyzer:
    """Analyzes Python repositories to extract code structure and metadata."""
    
    def __init__(self, repo_path: str):
        """
        Initialize the repository analyzer.
        
        Args:
            repo_path: Path to the repository to analyze
        """
        self.repo_path = Path(repo_path).resolve()
        self.ignore_patterns = {
            '__pycache__', '.git', '.pytest_cache', 'venv', 'env', 
            '.venv', '.env', 'node_modules', '.idea', '.vscode',
            'dist', 'build', '*.egg-info', '.tox', 'htmlcov'
        }
        
        try:
            self.repo = git.Repo(repo_path)
        except git.InvalidGitRepositoryError:
            logger.warning(f"Not a git repository: {repo_path}")
            self.repo = None
    
    def should_ignore_file(self, file_path: Path) -> bool:
        """Check if a file should be ignored based on patterns."""
        path_parts = file_path.parts
        for pattern in self.ignore_patterns:
            if any(pattern in part for part in path_parts):
                return True
        return False
    
    def scan_project(self) -> Dict[str, ModuleInfo]:
        """
        Scan the entire project for Python files and analyze them.
        
        Returns:
            Dictionary mapping file paths to ModuleInfo objects
        """
        modules = {}
        
        for py_file in self.repo_path.rglob("*.py"):
            if self.should_ignore_file(py_file):
                continue
                
            try:
                module_info = self.analyze_python_file(py_file)
                if module_info:
                    modules[str(py_file)] = module_info
            except Exception as e:
                logger.error(f"Error analyzing {py_file}: {e}")
        
        return modules
    
    def analyze_python_file(self, file_path: Union[str, Path]) -> Optional[ModuleInfo]:
        """
        Analyze a single Python file using AST parsing.
        
        Args:
            file_path: Path to the Python file to analyze
            
        Returns:
            ModuleInfo object containing the file's metadata
        """
        file_path = Path(file_path)
        
        if not file_path.exists() or not file_path.suffix == '.py':
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            logger.warning(f"Could not decode {file_path}")
            return None
        
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            return None
        
        module_info = ModuleInfo(
            file_path=str(file_path),
            docstring=ast.get_docstring(tree),
            functions=[],
            classes=[],
            imports=[],
            constants=[],
            last_modified=datetime.fromtimestamp(file_path.stat().st_mtime)
        )
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if self._is_top_level_function(node, tree):
                    func_info = self._extract_function_info(node)
                    module_info.functions.append(func_info)
            
            elif isinstance(node, ast.AsyncFunctionDef):
                if self._is_top_level_function(node, tree):
                    func_info = self._extract_function_info(node)
                    module_info.functions.append(func_info)
            
            elif isinstance(node, ast.ClassDef):
                if self._is_top_level_class(node, tree):
                    class_info = self._extract_class_info(node)
                    module_info.classes.append(class_info)
            
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                import_info = self._extract_import_info(node)
                module_info.imports.extend(import_info)
            
            elif isinstance(node, ast.Assign):
                constants = self._extract_constants(node)
                module_info.constants.extend(constants)
        
        return module_info
    
    def get_changed_files(self, since_commit: Optional[str] = None) -> List[str]:
        """
        Get list of Python files that have changed since a specific commit.
        
        Args:
            since_commit: Commit hash to compare against (defaults to HEAD~1)
            
        Returns:
            List of changed Python file paths
        """
        if not self.repo:
            return []
        
        try:
            if since_commit is None:
                # Get files changed since last commit
                changed_files = self.repo.git.diff('--name-only', 'HEAD~1', 'HEAD').split('\n')
            else:
                changed_files = self.repo.git.diff('--name-only', since_commit, 'HEAD').split('\n')
            
            # Filter for Python files that exist
            python_files = []
            for file in changed_files:
                if file.endswith('.py') and Path(self.repo_path / file).exists():
                    python_files.append(str(self.repo_path / file))
            
            return python_files
        except Exception as e:
            logger.error(f"Error getting changed files: {e}")
            return []
    
    def _is_top_level_function(self, node: ast.AST, tree: ast.AST) -> bool:
        """Check if a function is at the top level of the module."""
        for parent in ast.walk(tree):
            if hasattr(parent, 'body') and node in parent.body:
                return isinstance(parent, ast.Module)
        return False
    
    def _is_top_level_class(self, node: ast.AST, tree: ast.AST) -> bool:
        """Check if a class is at the top level of the module."""
        for parent in ast.walk(tree):
            if hasattr(parent, 'body') and node in parent.body:
                return isinstance(parent, ast.Module)
        return False
    
    def _extract_function_info(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> FunctionInfo:
        """Extract information from a function node."""
        args = []
        defaults = []
        type_hints = {}
        
        # Extract arguments
        for arg in node.args.args:
            args.append(arg.arg)
            if arg.annotation:
                type_hints[arg.arg] = ast.unparse(arg.annotation)
        
        # Extract default values
        if node.args.defaults:
            for default in node.args.defaults:
                defaults.append(ast.unparse(default))
        
        # Extract return annotation
        return_annotation = None
        if node.returns:
            return_annotation = ast.unparse(node.returns)
        
        # Extract decorators
        decorators = []
        for decorator in node.decorator_list:
            decorators.append(ast.unparse(decorator))
        
        return FunctionInfo(
            name=node.name,
            args=args,
            defaults=defaults,
            docstring=ast.get_docstring(node),
            return_annotation=return_annotation,
            line_number=node.lineno,
            decorators=decorators,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            type_hints=type_hints
        )
    
    def _extract_class_info(self, node: ast.ClassDef) -> ClassInfo:
        """Extract information from a class node."""
        bases = []
        for base in node.bases:
            bases.append(ast.unparse(base))
        
        decorators = []
        for decorator in node.decorator_list:
            decorators.append(ast.unparse(decorator))
        
        methods = []
        attributes = []
        
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_info = self._extract_function_info(item)
                methods.append(method_info)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attributes.append(target.id)
        
        return ClassInfo(
            name=node.name,
            bases=bases,
            docstring=ast.get_docstring(node),
            methods=methods,
            line_number=node.lineno,
            decorators=decorators,
            attributes=attributes
        )
    
    def _extract_import_info(self, node: Union[ast.Import, ast.ImportFrom]) -> List[str]:
        """Extract import information from import nodes."""
        imports = []
        
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"from {module} import {alias.name}")
        
        return imports
    
    def _extract_constants(self, node: ast.Assign) -> List[str]:
        """Extract constants from assignment nodes."""
        constants = []
        
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                constants.append(target.id)
        
        return constants
    
    def get_file_complexity(self, file_path: str) -> Dict[str, int]:
        """
        Calculate complexity metrics for a Python file.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            Dictionary with complexity metrics
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            metrics = {
                'lines_of_code': len(content.splitlines()),
                'functions': len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]),
                'classes': len([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]),
                'cyclomatic_complexity': self._calculate_cyclomatic_complexity(tree)
            }
            
            return metrics
        except Exception as e:
            logger.error(f"Error calculating complexity for {file_path}: {e}")
            return {}
    
    def _calculate_cyclomatic_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity of an AST tree."""
        complexity = 1  # Base complexity
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1
            elif isinstance(node, (ast.And, ast.Or)):
                complexity += 1
        
        return complexity