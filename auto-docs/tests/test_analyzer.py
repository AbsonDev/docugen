"""
Tests for the analyzer module.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analyzer import RepoAnalyzer, FunctionInfo, ClassInfo, ModuleInfo


class TestRepoAnalyzer:
    """Test cases for RepoAnalyzer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)
        
        # Create a simple Python file for testing
        self.test_file = self.repo_path / "test_module.py"
        self.test_file.write_text('''
"""Test module docstring."""

import os
import sys
from pathlib import Path

CONSTANT_VALUE = "test"
MAX_RETRIES = 3

def simple_function(arg1, arg2="default"):
    """A simple function."""
    return arg1 + arg2

async def async_function(data: str) -> str:
    """An async function."""
    return data.upper()

@property
def decorated_function():
    """A decorated function."""
    pass

class TestClass:
    """A test class."""
    
    def __init__(self, name: str):
        self.name = name
        
    def method(self, value: int) -> int:
        """A method."""
        return value * 2
        
    @classmethod
    def class_method(cls):
        """A class method."""
        return cls()

class InheritedClass(TestClass):
    """An inherited class."""
    pass
''')
        
        # Initialize analyzer
        self.analyzer = RepoAnalyzer(str(self.repo_path))
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_init(self):
        """Test RepoAnalyzer initialization."""
        assert self.analyzer.repo_path == self.repo_path
        assert '__pycache__' in self.analyzer.ignore_patterns
        assert '.git' in self.analyzer.ignore_patterns
    
    def test_should_ignore_file(self):
        """Test file ignoring logic."""
        # Should ignore
        assert self.analyzer.should_ignore_file(Path("test/__pycache__/file.pyc"))
        assert self.analyzer.should_ignore_file(Path("test/.git/config"))
        assert self.analyzer.should_ignore_file(Path("venv/lib/python3.11/site-packages/test.py"))
        
        # Should not ignore
        assert not self.analyzer.should_ignore_file(Path("src/main.py"))
        assert not self.analyzer.should_ignore_file(Path("test_file.py"))
    
    def test_analyze_python_file(self):
        """Test Python file analysis."""
        module_info = self.analyzer.analyze_python_file(self.test_file)
        
        assert module_info is not None
        assert module_info.file_path == str(self.test_file)
        assert module_info.docstring == "Test module docstring."
        
        # Check functions
        assert len(module_info.functions) == 3
        function_names = [f.name for f in module_info.functions]
        assert "simple_function" in function_names
        assert "async_function" in function_names
        assert "decorated_function" in function_names
        
        # Check classes
        assert len(module_info.classes) == 2
        class_names = [c.name for c in module_info.classes]
        assert "TestClass" in class_names
        assert "InheritedClass" in class_names
        
        # Check imports
        assert "import os" in module_info.imports
        assert "import sys" in module_info.imports
        assert "from pathlib import Path" in module_info.imports
        
        # Check constants
        assert "CONSTANT_VALUE" in module_info.constants
        assert "MAX_RETRIES" in module_info.constants
    
    def test_analyze_nonexistent_file(self):
        """Test analysis of non-existent file."""
        result = self.analyzer.analyze_python_file("/nonexistent/file.py")
        assert result is None
    
    def test_analyze_non_python_file(self):
        """Test analysis of non-Python file."""
        text_file = self.repo_path / "test.txt"
        text_file.write_text("Not a Python file")
        
        result = self.analyzer.analyze_python_file(text_file)
        assert result is None
    
    def test_extract_function_info(self):
        """Test function information extraction."""
        module_info = self.analyzer.analyze_python_file(self.test_file)
        
        # Test simple function
        simple_func = next(f for f in module_info.functions if f.name == "simple_function")
        assert simple_func.name == "simple_function"
        assert simple_func.args == ["arg1", "arg2"]
        assert simple_func.defaults == ['"default"']
        assert simple_func.docstring == "A simple function."
        assert not simple_func.is_async
        
        # Test async function
        async_func = next(f for f in module_info.functions if f.name == "async_function")
        assert async_func.name == "async_function"
        assert async_func.is_async
        assert async_func.type_hints == {"data": "str"}
        assert async_func.return_annotation == "str"
        
        # Test decorated function
        decorated_func = next(f for f in module_info.functions if f.name == "decorated_function")
        assert decorated_func.name == "decorated_function"
        assert "property" in decorated_func.decorators
    
    def test_extract_class_info(self):
        """Test class information extraction."""
        module_info = self.analyzer.analyze_python_file(self.test_file)
        
        # Test base class
        test_class = next(c for c in module_info.classes if c.name == "TestClass")
        assert test_class.name == "TestClass"
        assert test_class.docstring == "A test class."
        assert len(test_class.methods) == 3  # __init__, method, class_method
        assert test_class.bases == []
        
        method_names = [m.name for m in test_class.methods]
        assert "__init__" in method_names
        assert "method" in method_names
        assert "class_method" in method_names
        
        # Test inherited class
        inherited_class = next(c for c in module_info.classes if c.name == "InheritedClass")
        assert inherited_class.name == "InheritedClass"
        assert inherited_class.bases == ["TestClass"]
    
    def test_scan_project(self):
        """Test project scanning."""
        # Create additional files
        (self.repo_path / "subdir").mkdir()
        (self.repo_path / "subdir" / "another.py").write_text('def func(): pass')
        (self.repo_path / "ignored.txt").write_text("ignored")
        
        modules = self.analyzer.scan_project()
        
        assert len(modules) == 2  # test_module.py and subdir/another.py
        assert str(self.test_file) in modules
        assert str(self.repo_path / "subdir" / "another.py") in modules
    
    def test_get_file_complexity(self):
        """Test file complexity calculation."""
        complexity = self.analyzer.get_file_complexity(str(self.test_file))
        
        assert "lines_of_code" in complexity
        assert "functions" in complexity
        assert "classes" in complexity
        assert "cyclomatic_complexity" in complexity
        
        assert complexity["functions"] == 3
        assert complexity["classes"] == 2
        assert complexity["lines_of_code"] > 0
    
    @patch('git.Repo')
    def test_get_changed_files_with_git(self, mock_repo):
        """Test getting changed files with git."""
        mock_git = MagicMock()
        mock_git.diff.return_value = "file1.py\nfile2.py\nfile3.txt"
        mock_repo.return_value.git = mock_git
        
        # Create the files
        (self.repo_path / "file1.py").write_text("# file1")
        (self.repo_path / "file2.py").write_text("# file2")
        (self.repo_path / "file3.txt").write_text("# file3")
        
        analyzer = RepoAnalyzer(str(self.repo_path))
        analyzer.repo = mock_repo.return_value
        
        changed_files = analyzer.get_changed_files()
        
        # Should only include Python files that exist
        assert len(changed_files) == 2
        assert str(self.repo_path / "file1.py") in changed_files
        assert str(self.repo_path / "file2.py") in changed_files
    
    def test_get_changed_files_no_git(self):
        """Test getting changed files without git."""
        analyzer = RepoAnalyzer(str(self.repo_path))
        analyzer.repo = None
        
        changed_files = analyzer.get_changed_files()
        assert changed_files == []


class TestDataClasses:
    """Test data classes."""
    
    def test_function_info(self):
        """Test FunctionInfo dataclass."""
        func_info = FunctionInfo(
            name="test_func",
            args=["arg1", "arg2"],
            defaults=["default"],
            docstring="Test function",
            return_annotation="str",
            line_number=10,
            decorators=["@decorator"],
            is_async=False,
            type_hints={"arg1": "str"}
        )
        
        assert func_info.name == "test_func"
        assert func_info.args == ["arg1", "arg2"]
        assert func_info.type_hints == {"arg1": "str"}
        assert not func_info.is_async
    
    def test_class_info(self):
        """Test ClassInfo dataclass."""
        class_info = ClassInfo(
            name="TestClass",
            bases=["BaseClass"],
            docstring="Test class",
            methods=[],
            line_number=20,
            decorators=[],
            attributes=["attr1", "attr2"]
        )
        
        assert class_info.name == "TestClass"
        assert class_info.bases == ["BaseClass"]
        assert class_info.attributes == ["attr1", "attr2"]
    
    def test_module_info(self):
        """Test ModuleInfo dataclass."""
        from datetime import datetime
        
        module_info = ModuleInfo(
            file_path="/path/to/module.py",
            docstring="Module docstring",
            functions=[],
            classes=[],
            imports=["import os"],
            constants=["CONST"],
            last_modified=datetime.now()
        )
        
        assert module_info.file_path == "/path/to/module.py"
        assert module_info.docstring == "Module docstring"
        assert module_info.imports == ["import os"]
        assert module_info.constants == ["CONST"]