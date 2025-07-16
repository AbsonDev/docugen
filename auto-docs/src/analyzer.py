"""
Code analyzer module for auto-docs.

This module provides functionality to analyze Python repositories using AST parsing
and extract metadata about functions, classes, and modules for documentation generation.
"""

import ast
import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from datetime import datetime
import git
import logging
import time

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
    """Information about a Python module or C# file."""
    file_path: str
    docstring: Optional[str]
    functions: List[FunctionInfo]
    classes: List[ClassInfo]
    imports: List[str]
    constants: List[str]
    last_modified: datetime
    file_type: str = "python"  # "python" or "csharp"
    namespace: Optional[str] = None  # For C# files
    classification: Optional[str] = None  # File classification (controller, service, entity, etc.)


class RepoAnalyzer:
    """Analyzes Python repositories to extract code structure and metadata."""
    
    # Compiled regex patterns for performance
    COMPILED_PATTERNS = {
        'namespace': re.compile(r'namespace\s+([^\s{]+)'),
        'class_simple': re.compile(r'(?:public\s+|private\s+|internal\s+|protected\s+)*(?:abstract\s+|sealed\s+|static\s+)*class\s+(\w+)', re.MULTILINE),
        'controller': re.compile(r'class\s+\w*Controller\b'),
        'service': re.compile(r'class\s+\w*Service\b'),
        'repository': re.compile(r'class\s+\w*Repository\b'),
        'using_statements': re.compile(r'using\s+([^;]+);'),
        'method_simple': re.compile(r'(?:public\s+|private\s+|protected\s+|internal\s+)[\w\s]*\s+(\w+)\s*\([^)]*\)\s*[{;]', re.MULTILINE),
        'xml_doc': re.compile(r'///\s*<summary>\s*(.*?)\s*</summary>', re.DOTALL)
    }
    
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
        Scan the entire project for Python and C# files and analyze them.
        
        Returns:
            Dictionary mapping file paths to ModuleInfo objects
        """
        modules = {}
        
        # Scan Python files
        for py_file in self.repo_path.rglob("*.py"):
            if self.should_ignore_file(py_file):
                continue
                
            try:
                module_info = self.analyze_python_file(py_file)
                if module_info:
                    modules[str(py_file)] = module_info
            except Exception as e:
                logger.error(f"Error analyzing {py_file}: {e}")
        
        # Scan C# files
        for cs_file in self.repo_path.rglob("*.cs"):
            if self.should_ignore_file(cs_file):
                continue
                
            try:
                module_info = self.analyze_csharp_file(cs_file)
                if module_info:
                    modules[str(cs_file)] = module_info
            except Exception as e:
                logger.error(f"Error analyzing {cs_file}: {e}")
        
        return modules
    
    def fast_scan_project_structure(self) -> Dict[str, Any]:
        """
        Fast scan to get project structure without full analysis.
        
        Returns:
            Dictionary with project structure info
        """
        structure = {
            'python_files': [],
            'csharp_files': [],
            'directories': set(),
            'file_count_by_type': {},
            'priority_files': {
                'high': [],    # Controllers, Main services
                'medium': [],  # Services, Repositories
                'low': []      # DTOs, Configurations, etc.
            }
        }
        
        logger.info("🔍 Fast scanning project structure...")
        
        # Fast scan for Python files
        for py_file in self.repo_path.rglob("*.py"):
            if self.should_ignore_file(py_file):
                continue
            structure['python_files'].append(str(py_file))
            structure['directories'].add(str(py_file.parent))
        
        # Fast scan for C# files with priority classification
        for cs_file in self.repo_path.rglob("*.cs"):
            if self.should_ignore_file(cs_file):
                continue
            
            file_path = str(cs_file)
            structure['csharp_files'].append(file_path)
            structure['directories'].add(str(cs_file.parent))
            
            # Quick priority classification based on file name and path
            priority = self._classify_file_priority(cs_file)
            structure['priority_files'][priority].append(file_path)
        
        # Count files by type
        structure['file_count_by_type'] = {
            'python': len(structure['python_files']),
            'csharp': len(structure['csharp_files']),
            'total': len(structure['python_files']) + len(structure['csharp_files'])
        }
        
        # Convert directories set to sorted list
        structure['directories'] = sorted(list(structure['directories']))
        
        logger.info(f"📊 Found {structure['file_count_by_type']['total']} files "
                   f"({structure['file_count_by_type']['csharp']} C#, "
                   f"{structure['file_count_by_type']['python']} Python)")
        
        return structure
    
    def scan_project_chunked(self, chunk_size: int = 15, priority_only: bool = False) -> Dict[str, ModuleInfo]:
        """
        Scan project in chunks for better performance and memory management.
        
        Args:
            chunk_size: Number of files to process per chunk
            priority_only: If True, only process high priority files
            
        Returns:
            Dictionary mapping file paths to ModuleInfo objects
        """
        # First, fast scan to get structure
        structure = self.fast_scan_project_structure()
        
        modules = {}
        all_files = []
        
        # Determine which files to process
        if priority_only:
            all_files = structure['priority_files']['high']
            logger.info(f"🎯 Processing only {len(all_files)} high priority files")
        else:
            # Process in priority order: high → medium → low
            all_files = (
                structure['priority_files']['high'] + 
                structure['priority_files']['medium'] + 
                structure['priority_files']['low'] +
                structure['python_files']
            )
            logger.info(f"📝 Processing {len(all_files)} files in priority order")
        
        # Process files in chunks
        total_chunks = (len(all_files) + chunk_size - 1) // chunk_size
        
        for chunk_idx in range(total_chunks):
            start_idx = chunk_idx * chunk_size
            end_idx = min(start_idx + chunk_size, len(all_files))
            chunk_files = all_files[start_idx:end_idx]
            
            logger.info(f"🔄 Processing chunk {chunk_idx + 1}/{total_chunks} "
                       f"({len(chunk_files)} files)")
            
            # Process current chunk
            chunk_modules = self._process_file_chunk(chunk_files)
            modules.update(chunk_modules)
            
            logger.info(f"✅ Completed chunk {chunk_idx + 1}/{total_chunks} "
                       f"({len(chunk_modules)} files analyzed)")
        
        logger.info(f"🎉 Analysis complete! Processed {len(modules)} files total")
        return modules
    
    def _classify_file_priority(self, file_path: Path) -> str:
        """
        Classify file priority based on path and name patterns.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Priority level: 'high', 'medium', or 'low'
        """
        file_name = file_path.name
        path_parts = file_path.parts
        
        # High priority: Controllers, Main Program files, Important Services
        if (file_name.endswith('Controller.cs') or 
            file_name == 'Program.cs' or 
            file_name == 'Startup.cs' or
            'Controllers' in path_parts):
            return 'high'
        
        # Medium priority: Services, Repositories, Handlers, Entities
        if (file_name.endswith('Service.cs') or 
            file_name.endswith('Repository.cs') or
            file_name.endswith('Handler.cs') or
            'Services' in path_parts or
            'Repositories' in path_parts or
            'Repository' in path_parts or
            'Entities' in path_parts or
            'Domain' in path_parts):
            return 'medium'
        
        # Low priority: DTOs, Configurations, Extensions, Migrations
        return 'low'
    
    def _process_file_chunk(self, file_paths: List[str]) -> Dict[str, ModuleInfo]:
        """
        Process a chunk of files and return their analysis.
        
        Args:
            file_paths: List of file paths to process
            
        Returns:
            Dictionary mapping file paths to ModuleInfo objects
        """
        chunk_modules = {}
        
        for file_path in file_paths:
            try:
                path_obj = Path(file_path)
                
                if path_obj.suffix == '.py':
                    module_info = self.analyze_python_file(path_obj)
                elif path_obj.suffix == '.cs':
                    module_info = self.analyze_csharp_file(path_obj)
                else:
                    continue
                
                if module_info:
                    chunk_modules[file_path] = module_info
                    
            except Exception as e:
                logger.error(f"❌ Error analyzing {file_path}: {e}")
        
        return chunk_modules
    
    def analyze_csharp_file(self, file_path: Union[str, Path], level: str = 'auto') -> Optional[ModuleInfo]:
        """
        Analyze a single C# file using regex parsing.
        
        Args:
            file_path: Path to the C# file to analyze
            level: Analysis level - 'basic', 'medium', 'full', or 'auto'
            
        Returns:
            ModuleInfo object containing the file's metadata
        """
        file_path = Path(file_path)
        
        if not file_path.exists() or not file_path.suffix == '.cs':
            return None
        
        # Determine analysis level based on file size if auto
        if level == 'auto':
            file_size = file_path.stat().st_size
            if file_size > 50000:  # 50KB - large file
                level = 'basic'
            elif file_size > 20000:  # 20KB - medium file
                level = 'medium'
            else:
                level = 'full'
        
        try:
            start_time = time.time()
            with open(file_path, 'r', encoding='utf-8') as f:
                if level == 'basic':
                    # Read only first 200 lines for basic analysis
                    lines = []
                    for i, line in enumerate(f):
                        if i >= 200:
                            break
                        lines.append(line)
                    content = ''.join(lines)
                else:
                    content = f.read()
            
            # Timeout protection
            if time.time() - start_time > 5:  # 5 second timeout for reading
                logger.warning(f"Timeout reading {file_path}, using basic analysis")
                level = 'basic'
                
        except UnicodeDecodeError:
            logger.warning(f"Could not decode {file_path}")
            return None
        
        # Use fast analysis methods
        return self._analyze_csharp_content(file_path, content, level)
    
    def _analyze_csharp_content(self, file_path: Path, content: str, level: str) -> Optional[ModuleInfo]:
        """
        Analyze C# content with specified detail level.
        
        Args:
            file_path: Path to the file
            content: File content (may be partial for basic level)
            level: Analysis level ('basic', 'medium', 'full')
            
        Returns:
            ModuleInfo object
        """
        start_time = time.time()
        
        # Extract namespace (always fast)
        namespace_match = self.COMPILED_PATTERNS['namespace'].search(content)
        namespace = namespace_match.group(1) if namespace_match else None
        
        # Extract using statements (always fast)
        using_statements = [match.group(1) for match in self.COMPILED_PATTERNS['using_statements'].finditer(content)]
        
        # Quick classification first
        file_classification = self._quick_classify_csharp_file(file_path, content)
        
        if level == 'basic':
            # Minimal analysis - just structure
            classes = self._extract_csharp_classes_fast(content)
            functions = []
            constants = []
            docstring = self._extract_file_comment_fast(content)
            
        elif level == 'medium':
            # Medium analysis - classes and main methods
            classes = self._extract_csharp_classes_medium(content)
            functions = []  # Skip standalone functions for medium
            constants = self._extract_csharp_constants_fast(content)
            docstring = self._extract_file_comment_fast(content)
            
        else:  # full
            # Full analysis (original method)
            classes = self._extract_csharp_classes(content)
            functions = self._extract_csharp_functions(content)
            constants = self._extract_csharp_constants(content)
            docstring = self._extract_csharp_file_comment(content)
        
        # Timeout check
        if time.time() - start_time > 10:  # 10 second timeout per file
            logger.warning(f"Analysis timeout for {file_path}, returning partial results")
        
        module_info = ModuleInfo(
            file_path=str(file_path),
            docstring=docstring,
            functions=functions,
            classes=classes,
            imports=using_statements,
            constants=constants,
            last_modified=datetime.fromtimestamp(file_path.stat().st_mtime),
            file_type="csharp",
            namespace=namespace
        )
        
        # Add classification info
        module_info.classification = file_classification
        
        return module_info
    
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
    
    def _extract_csharp_classes(self, content: str) -> List[ClassInfo]:
        """Extract class information from C# code."""
        classes = []
        
        # Pattern to match class declarations with XML docs
        class_pattern = r'(?:///\s*<summary>\s*(.*?)\s*</summary>\s*(?:.*?\n)*?)?(?:public\s+|private\s+|internal\s+|protected\s+)*(?:abstract\s+|sealed\s+|static\s+)*class\s+(\w+)(?:\s*:\s*([^{]+))?'
        
        matches = re.finditer(class_pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            xml_doc = match.group(1) if match.group(1) else None
            class_name = match.group(2)
            inheritance = match.group(3) if match.group(3) else ""
            
            # Extract base classes
            bases = []
            if inheritance:
                bases = [base.strip() for base in inheritance.split(',')]
            
            # Extract methods from this class
            methods = self._extract_csharp_methods_from_class(content, class_name)
            
            # Extract attributes/properties
            attributes = self._extract_csharp_properties(content, class_name)
            
            class_info = ClassInfo(
                name=class_name,
                bases=bases,
                docstring=xml_doc,
                methods=methods,
                line_number=content[:match.start()].count('\n') + 1,
                decorators=[],  # C# uses attributes instead
                attributes=attributes
            )
            
            classes.append(class_info)
        
        return classes
    
    def _extract_csharp_functions(self, content: str) -> List[FunctionInfo]:
        """Extract function information from C# code (methods outside classes)."""
        functions = []
        
        # Pattern to match method declarations with XML docs
        method_pattern = r'(?:///\s*<summary>\s*(.*?)\s*</summary>\s*(?:.*?\n)*?)?(?:public\s+|private\s+|internal\s+|protected\s+)*(?:static\s+|async\s+|virtual\s+|override\s+)*(\w+)\s+(\w+)\s*\(([^)]*)\)'
        
        matches = re.finditer(method_pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            xml_doc = match.group(1) if match.group(1) else None
            return_type = match.group(2)
            method_name = match.group(3)
            parameters = match.group(4)
            
            # Skip if this is inside a class
            if self._is_method_inside_class(content, match.start()):
                continue
            
            # Extract parameters
            args = []
            if parameters.strip():
                param_list = parameters.split(',')
                for param in param_list:
                    param = param.strip()
                    if param:
                        # Extract parameter name (last word)
                        param_parts = param.split()
                        if len(param_parts) >= 2:
                            args.append(param_parts[-1])
            
            # Check if method is async
            is_async = 'async' in match.group(0)
            
            function_info = FunctionInfo(
                name=method_name,
                args=args,
                defaults=[],
                docstring=xml_doc,
                return_annotation=return_type,
                line_number=content[:match.start()].count('\n') + 1,
                decorators=[],
                is_async=is_async,
                type_hints={}
            )
            
            functions.append(function_info)
        
        return functions
    
    def _extract_csharp_methods_from_class(self, content: str, class_name: str) -> List[FunctionInfo]:
        """Extract methods from a specific C# class."""
        methods = []
        
        # Find class boundaries
        class_start = content.find(f'class {class_name}')
        if class_start == -1:
            return methods
        
        # Find class body
        brace_count = 0
        class_body_start = -1
        for i in range(class_start, len(content)):
            if content[i] == '{':
                if class_body_start == -1:
                    class_body_start = i
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    class_body_end = i
                    break
        
        if class_body_start == -1:
            return methods
        
        class_body = content[class_body_start:class_body_end]
        
        # Extract methods from class body
        method_pattern = r'(?:///\s*<summary>\s*(.*?)\s*</summary>\s*(?:.*?\n)*?)?(?:public\s+|private\s+|internal\s+|protected\s+)*(?:static\s+|async\s+|virtual\s+|override\s+)*(\w+)\s+(\w+)\s*\(([^)]*)\)'
        
        matches = re.finditer(method_pattern, class_body, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            xml_doc = match.group(1) if match.group(1) else None
            return_type = match.group(2)
            method_name = match.group(3)
            parameters = match.group(4)
            
            # Extract parameters
            args = []
            if parameters.strip():
                param_list = parameters.split(',')
                for param in param_list:
                    param = param.strip()
                    if param:
                        param_parts = param.split()
                        if len(param_parts) >= 2:
                            args.append(param_parts[-1])
            
            is_async = 'async' in match.group(0)
            
            function_info = FunctionInfo(
                name=method_name,
                args=args,
                defaults=[],
                docstring=xml_doc,
                return_annotation=return_type,
                line_number=class_body[:match.start()].count('\n') + 1,
                decorators=[],
                is_async=is_async,
                type_hints={}
            )
            
            methods.append(function_info)
        
        return methods
    
    def _extract_csharp_constants(self, content: str) -> List[str]:
        """Extract constants from C# code."""
        constants = []
        
        # Pattern for const declarations
        const_pattern = r'(?:public\s+|private\s+|internal\s+|protected\s+)*const\s+\w+\s+(\w+)'
        matches = re.finditer(const_pattern, content)
        
        for match in matches:
            constants.append(match.group(1))
        
        # Pattern for static readonly fields (treated as constants)
        static_readonly_pattern = r'(?:public\s+|private\s+|internal\s+|protected\s+)*static\s+readonly\s+\w+\s+(\w+)'
        matches = re.finditer(static_readonly_pattern, content)
        
        for match in matches:
            constants.append(match.group(1))
        
        return constants
    
    def _extract_csharp_properties(self, content: str, class_name: str) -> List[str]:
        """Extract property names from a C# class."""
        properties = []
        
        # Find class body (simplified)
        class_start = content.find(f'class {class_name}')
        if class_start == -1:
            return properties
        
        # Pattern for properties
        property_pattern = r'(?:public\s+|private\s+|internal\s+|protected\s+)*(?:static\s+)*\w+\s+(\w+)\s*\{\s*get'
        matches = re.finditer(property_pattern, content[class_start:])
        
        for match in matches:
            properties.append(match.group(1))
        
        return properties
    
    def _extract_csharp_file_comment(self, content: str) -> Optional[str]:
        """Extract file-level XML documentation comment."""
        # Look for file-level XML comments at the beginning
        file_comment_pattern = r'^\s*///\s*<summary>\s*(.*?)\s*</summary>'
        match = re.search(file_comment_pattern, content, re.MULTILINE | re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        return None
    
    def _is_method_inside_class(self, content: str, method_position: int) -> bool:
        """Check if a method is inside a class."""
        # Count braces before the method position
        before_method = content[:method_position]
        
        # Find the last class declaration before this method
        class_matches = list(re.finditer(r'class\s+\w+', before_method))
        if not class_matches:
            return False
        
        last_class_pos = class_matches[-1].start()
        
        # Count braces between class and method
        class_to_method = content[last_class_pos:method_position]
        open_braces = class_to_method.count('{')
        close_braces = class_to_method.count('}')
        
        # If more open braces than close braces, we're inside the class
        return open_braces > close_braces
    
    def _classify_csharp_file(self, file_path: Path, content: str, classes: List[ClassInfo], functions: List[FunctionInfo]) -> str:
        """Classify C# file type based on path, content, and structure."""
        file_name = file_path.name
        path_parts = file_path.parts
        
        # Classification based on file name patterns
        if file_name.endswith('Controller.cs'):
            return 'controller'
        elif file_name.endswith('Service.cs'):
            return 'service'
        elif file_name.endswith('Repository.cs'):
            return 'repository'
        elif file_name.endswith('Configuration.cs'):
            return 'configuration'
        elif file_name.endswith('Handler.cs'):
            return 'handler'
        elif file_name.endswith('Middleware.cs'):
            return 'middleware'
        elif file_name.endswith('Extensions.cs'):
            return 'extension'
        elif file_name.endswith('Validator.cs'):
            return 'validator'
        elif file_name.endswith('Dto.cs') or file_name.endswith('Request.cs') or file_name.endswith('Response.cs'):
            return 'dto'
        elif file_name.endswith('Exception.cs'):
            return 'exception'
        
        # Classification based on directory path
        if 'Controllers' in path_parts:
            return 'controller'
        elif 'Services' in path_parts:
            return 'service'
        elif 'Repositories' in path_parts or 'Repository' in path_parts:
            return 'repository'
        elif 'Entities' in path_parts or 'Domain' in path_parts:
            return 'entity'
        elif 'DTOs' in path_parts or 'Models' in path_parts or 'Views' in path_parts:
            return 'dto'
        elif 'Configurations' in path_parts or 'Configuration' in path_parts:
            return 'configuration'
        elif 'Middlewares' in path_parts or 'Middleware' in path_parts:
            return 'middleware'
        elif 'Extensions' in path_parts:
            return 'extension'
        elif 'Validators' in path_parts:
            return 'validator'
        elif 'Exceptions' in path_parts:
            return 'exception'
        elif 'Migrations' in path_parts:
            return 'migration'
        elif 'Handlers' in path_parts:
            return 'handler'
        elif 'Commands' in path_parts:
            return 'command'
        elif 'Queries' in path_parts:
            return 'query'
        elif 'ValueObjects' in path_parts:
            return 'value_object'
        elif 'Events' in path_parts:
            return 'event'
        elif 'Builders' in path_parts:
            return 'builder'
        elif 'Helpers' in path_parts or 'Utils' in path_parts:
            return 'utility'
        elif 'Interfaces' in path_parts:
            return 'interface'
        elif 'Abstractions' in path_parts:
            return 'abstraction'
        
        # Classification based on content analysis
        if 'ControllerBase' in content or 'Controller' in content:
            return 'controller'
        elif 'DbContext' in content:
            return 'db_context'
        elif 'IRepository' in content and 'class' in content:
            return 'repository'
        elif 'IService' in content and 'class' in content:
            return 'service'
        elif 'EntityTypeConfiguration' in content:
            return 'configuration'
        elif 'IRequestHandler' in content or 'INotificationHandler' in content:
            return 'handler'
        elif 'IRequest' in content or 'INotification' in content:
            if 'Command' in file_name:
                return 'command'
            elif 'Query' in file_name:
                return 'query'
            else:
                return 'request'
        elif 'Migration' in content and 'Up()' in content and 'Down()' in content:
            return 'migration'
        elif 'public class' in content and len(classes) > 0:
            # Check if it's likely an entity
            if any('public' in cls.name or 'Id' in [attr for attr in cls.attributes] for cls in classes):
                return 'entity'
        
        # Default classification
        if classes:
            return 'class'
        elif functions:
            return 'utility'
        else:
            return 'unknown'
    
    def _quick_classify_csharp_file(self, file_path: Path, content: str) -> str:
        """
        Quick classification using compiled patterns and file info.
        
        Args:
            file_path: Path to the file
            content: File content (may be partial)
            
        Returns:
            Classification string
        """
        file_name = file_path.name
        path_parts = file_path.parts
        
        # Quick file name patterns
        if file_name.endswith('Controller.cs'):
            return 'controller'
        elif file_name.endswith('Service.cs'):
            return 'service'  
        elif file_name.endswith('Repository.cs'):
            return 'repository'
        elif file_name.endswith('Configuration.cs'):
            return 'configuration'
        
        # Quick directory patterns
        if 'Controllers' in path_parts:
            return 'controller'
        elif 'Services' in path_parts:
            return 'service'
        elif 'Repositories' in path_parts or 'Repository' in path_parts:
            return 'repository'
        elif 'Entities' in path_parts or 'Domain' in path_parts:
            return 'entity'
        
        # Quick content patterns using compiled regex
        if self.COMPILED_PATTERNS['controller'].search(content):
            return 'controller'
        elif self.COMPILED_PATTERNS['service'].search(content):
            return 'service'
        elif self.COMPILED_PATTERNS['repository'].search(content):
            return 'repository'
        
        return 'unknown'
    
    def _extract_csharp_classes_fast(self, content: str) -> List[ClassInfo]:
        """
        Fast extraction of class info using compiled patterns.
        
        Args:
            content: File content
            
        Returns:
            List of ClassInfo objects with minimal info
        """
        classes = []
        
        # Use compiled pattern for faster matching
        for match in self.COMPILED_PATTERNS['class_simple'].finditer(content):
            class_name = match.group(1)
            
            class_info = ClassInfo(
                name=class_name,
                bases=[],
                docstring=None,
                methods=[],  # Empty for fast analysis
                line_number=content[:match.start()].count('\n') + 1,
                decorators=[],
                attributes=[]
            )
            
            classes.append(class_info)
        
        return classes
    
    def _extract_csharp_classes_medium(self, content: str) -> List[ClassInfo]:
        """
        Medium-detail extraction of class info.
        
        Args:
            content: File content
            
        Returns:
            List of ClassInfo objects with some method info
        """
        classes = []
        
        # Use compiled pattern
        for match in self.COMPILED_PATTERNS['class_simple'].finditer(content):
            class_name = match.group(1)
            
            # Extract a few methods using simple pattern
            methods = []
            method_matches = list(self.COMPILED_PATTERNS['method_simple'].finditer(content))
            
            # Limit to first 5 methods for medium analysis
            for method_match in method_matches[:5]:
                method_name = method_match.group(1)
                
                function_info = FunctionInfo(
                    name=method_name,
                    args=[],
                    defaults=[],
                    docstring=None,
                    return_annotation=None,
                    line_number=content[:method_match.start()].count('\n') + 1,
                    decorators=[],
                    is_async=False,
                    type_hints={}
                )
                methods.append(function_info)
            
            class_info = ClassInfo(
                name=class_name,
                bases=[],
                docstring=None,
                methods=methods,
                line_number=content[:match.start()].count('\n') + 1,
                decorators=[],
                attributes=[]
            )
            
            classes.append(class_info)
        
        return classes
    
    def _extract_file_comment_fast(self, content: str) -> Optional[str]:
        """
        Fast extraction of file-level documentation.
        
        Args:
            content: File content
            
        Returns:
            File comment if found
        """
        # Look for first XML doc comment using compiled pattern
        match = self.COMPILED_PATTERNS['xml_doc'].search(content)
        if match:
            return match.group(1).strip()
        
        # Fallback to first few comment lines
        lines = content.split('\n')[:10]  # Only check first 10 lines
        comments = []
        for line in lines:
            line = line.strip()
            if line.startswith('//'):
                comments.append(line[2:].strip())
            elif comments:  # Stop at first non-comment after finding comments
                break
        
        return ' '.join(comments) if comments else None
    
    def _extract_csharp_constants_fast(self, content: str) -> List[str]:
        """
        Fast extraction of constants using simple patterns.
        
        Args:
            content: File content
            
        Returns:
            List of constant names
        """
        constants = []
        
        # Simple pattern for const declarations
        const_matches = re.finditer(r'\bconst\s+\w+\s+(\w+)', content)
        for match in const_matches:
            constants.append(match.group(1))
        
        # Limit to prevent slowdown
        return constants[:20]