"""
Tests for the ai_generator module.
"""

import os
import sys
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_generator import DocGenerator, DocGenerationConfig, RateLimiter
from analyzer import ModuleInfo, FunctionInfo, ClassInfo

from pathlib import Path


class TestRateLimiter:
    """Test cases for RateLimiter class."""
    
    def test_init(self):
        """Test RateLimiter initialization."""
        limiter = RateLimiter(max_requests=10, time_window=60)
        assert limiter.max_requests == 10
        assert limiter.time_window == 60
        assert limiter.requests == []
    
    def test_no_wait_needed(self):
        """Test when no wait is needed."""
        limiter = RateLimiter(max_requests=10, time_window=60)
        
        # Should not wait when under limit
        start_time = time.time()
        limiter.wait_if_needed()
        end_time = time.time()
        
        assert end_time - start_time < 0.1  # Should be almost instant
        assert len(limiter.requests) == 1
    
    def test_wait_when_limit_reached(self):
        """Test waiting when rate limit is reached."""
        limiter = RateLimiter(max_requests=2, time_window=1)
        
        # Fill up the rate limit
        limiter.wait_if_needed()
        limiter.wait_if_needed()
        
        # This should cause a wait
        start_time = time.time()
        limiter.wait_if_needed()
        end_time = time.time()
        
        # Should have waited at least a bit
        assert end_time - start_time > 0.5
    
    def test_old_requests_cleaned_up(self):
        """Test that old requests are cleaned up."""
        limiter = RateLimiter(max_requests=5, time_window=1)
        
        # Add some old requests
        old_time = datetime.now() - timedelta(seconds=2)
        limiter.requests = [old_time, old_time, old_time]
        
        # Make a new request
        limiter.wait_if_needed()
        
        # Old requests should be cleaned up
        assert len(limiter.requests) == 1


class TestDocGenerationConfig:
    """Test cases for DocGenerationConfig class."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = DocGenerationConfig()
        
        assert config.model == "llama3-8b-8192"
        assert config.max_tokens == 1000
        assert config.temperature == 0.3
        assert config.max_requests_per_minute == 100
        assert config.output_format == "markdown"
        assert config.include_examples is True
        assert config.include_type_hints is True
        assert config.include_complexity is False
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = DocGenerationConfig(
            model="custom-model",
            max_tokens=2000,
            temperature=0.5,
            include_examples=False
        )
        
        assert config.model == "custom-model"
        assert config.max_tokens == 2000
        assert config.temperature == 0.5
        assert config.include_examples is False


class TestDocGenerator:
    """Test cases for DocGenerator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = DocGenerationConfig()
        self.mock_client = MagicMock()
        
        # Create sample module info
        self.sample_function = FunctionInfo(
            name="sample_function",
            args=["arg1", "arg2"],
            defaults=["default"],
            docstring="A sample function.",
            return_annotation="str",
            line_number=10,
            decorators=[],
            is_async=False,
            type_hints={"arg1": "str"}
        )
        
        self.sample_class = ClassInfo(
            name="SampleClass",
            bases=["BaseClass"],
            docstring="A sample class.",
            methods=[self.sample_function],
            line_number=20,
            decorators=[],
            attributes=["attr1"]
        )
        
        self.sample_module = ModuleInfo(
            file_path="/path/to/module.py",
            docstring="Sample module docstring.",
            functions=[self.sample_function],
            classes=[self.sample_class],
            imports=["import os", "from pathlib import Path"],
            constants=["CONST_VALUE"],
            last_modified=datetime.now()
        )
    
    @patch('groq.Groq')
    def test_init(self, mock_groq):
        """Test DocGenerator initialization."""
        generator = DocGenerator("test_api_key", self.config)
        
        mock_groq.assert_called_once_with(api_key="test_api_key")
        assert generator.config == self.config
        assert isinstance(generator.rate_limiter, RateLimiter)
        assert generator.doc_cache == {}
    
    @patch('groq.Groq')
    def test_generate_file_docs(self, mock_groq):
        """Test file documentation generation."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "# Generated Documentation\n\nThis is test documentation."
        
        mock_groq.return_value.chat.completions.create.return_value = mock_response
        
        generator = DocGenerator("test_api_key", self.config)
        generator.client = mock_groq.return_value
        
        result = generator.generate_file_docs(self.sample_module)
        
        assert result == "# Generated Documentation\n\nThis is test documentation."
        mock_groq.return_value.chat.completions.create.assert_called_once()
        
        # Check that cache was populated
        cache_key = f"{self.sample_module.file_path}_{self.sample_module.last_modified}"
        assert cache_key in generator.doc_cache
    
    @patch('groq.Groq')
    def test_generate_file_docs_from_cache(self, mock_groq):
        """Test file documentation generation from cache."""
        generator = DocGenerator("test_api_key", self.config)
        generator.client = mock_groq.return_value
        
        # Pre-populate cache
        cache_key = f"{self.sample_module.file_path}_{self.sample_module.last_modified}"
        generator.doc_cache[cache_key] = "Cached documentation"
        
        result = generator.generate_file_docs(self.sample_module)
        
        assert result == "Cached documentation"
        # Should not call API when using cache
        mock_groq.return_value.chat.completions.create.assert_not_called()
    
    @patch('groq.Groq')
    def test_generate_function_docs(self, mock_groq):
        """Test function documentation generation."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Function documentation"
        
        mock_groq.return_value.chat.completions.create.return_value = mock_response
        
        generator = DocGenerator("test_api_key", self.config)
        generator.client = mock_groq.return_value
        
        result = generator.generate_function_docs(self.sample_function, "test context")
        
        assert result == "Function documentation"
        mock_groq.return_value.chat.completions.create.assert_called_once()
    
    @patch('groq.Groq')
    def test_generate_class_docs(self, mock_groq):
        """Test class documentation generation."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Class documentation"
        
        mock_groq.return_value.chat.completions.create.return_value = mock_response
        
        generator = DocGenerator("test_api_key", self.config)
        generator.client = mock_groq.return_value
        
        result = generator.generate_class_docs(self.sample_class, "test context")
        
        assert result == "Class documentation"
        mock_groq.return_value.chat.completions.create.assert_called_once()
    
    @patch('groq.Groq')
    def test_generate_project_overview(self, mock_groq):
        """Test project overview generation."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Project overview"
        
        mock_groq.return_value.chat.completions.create.return_value = mock_response
        
        generator = DocGenerator("test_api_key", self.config)
        generator.client = mock_groq.return_value
        
        modules = {"/path/to/module.py": self.sample_module}
        result = generator.generate_project_overview(modules, "test-project")
        
        assert result == "Project overview"
        mock_groq.return_value.chat.completions.create.assert_called_once()
    
    @patch('groq.Groq')
    def test_api_error_fallback(self, mock_groq):
        """Test fallback when API call fails."""
        mock_groq.return_value.chat.completions.create.side_effect = Exception("API Error")
        
        generator = DocGenerator("test_api_key", self.config)
        generator.client = mock_groq.return_value
        
        result = generator.generate_file_docs(self.sample_module)
        
        # Should return fallback documentation
        assert "module.py" in result
        assert "sample_function" in result
        assert "SampleClass" in result
    
    @patch('groq.Groq')
    def test_fallback_function_docs(self, mock_groq):
        """Test fallback function documentation."""
        generator = DocGenerator("test_api_key", self.config)
        
        result = generator._generate_fallback_function_docs(self.sample_function)
        
        assert "sample_function" in result
        assert "A sample function." in result
    
    @patch('groq.Groq')
    def test_fallback_class_docs(self, mock_groq):
        """Test fallback class documentation."""
        generator = DocGenerator("test_api_key", self.config)
        
        result = generator._generate_fallback_class_docs(self.sample_class)
        
        assert "SampleClass" in result
        assert "A sample class." in result
        assert "BaseClass" in result
    
    @patch('groq.Groq')
    def test_fallback_project_overview(self, mock_groq):
        """Test fallback project overview."""
        generator = DocGenerator("test_api_key", self.config)
        
        modules = {"/path/to/module.py": self.sample_module}
        result = generator._generate_fallback_project_overview(modules, "test-project")
        
        assert "test-project" in result
        assert "module.py" in result
        assert "1 functions, 1 classes" in result
    
    @patch('groq.Groq')
    def test_clear_cache(self, mock_groq):
        """Test cache clearing."""
        generator = DocGenerator("test_api_key", self.config)
        generator.doc_cache["test_key"] = "test_value"
        
        generator.clear_cache()
        
        assert generator.doc_cache == {}
    
    @patch('groq.Groq')
    def test_get_cache_stats(self, mock_groq):
        """Test cache statistics."""
        generator = DocGenerator("test_api_key", self.config)
        generator.doc_cache["key1"] = "value1"
        generator.doc_cache["key2"] = "value2"
        
        stats = generator.get_cache_stats()
        
        assert stats["cache_size"] == 2
        assert "key1" in stats["cache_keys"]
        assert "key2" in stats["cache_keys"]
    
    @patch('groq.Groq')
    def test_create_file_documentation_prompt(self, mock_groq):
        """Test file documentation prompt creation."""
        generator = DocGenerator("test_api_key", self.config)
        
        prompt = generator._create_file_documentation_prompt(self.sample_module)
        
        assert "module.py" in prompt
        assert "sample_function" in prompt
        assert "SampleClass" in prompt
        assert "Sample module docstring." in prompt
        assert "import os" in prompt
        assert "CONST_VALUE" in prompt
    
    @patch('groq.Groq')
    def test_create_function_documentation_prompt(self, mock_groq):
        """Test function documentation prompt creation."""
        generator = DocGenerator("test_api_key", self.config)
        
        prompt = generator._create_function_documentation_prompt(
            self.sample_function, "test context"
        )
        
        assert "sample_function" in prompt
        assert "arg1, arg2" in prompt
        assert "A sample function." in prompt
        assert "test context" in prompt
        assert "str" in prompt  # type hints
    
    @patch('groq.Groq')
    def test_create_class_documentation_prompt(self, mock_groq):
        """Test class documentation prompt creation."""
        generator = DocGenerator("test_api_key", self.config)
        
        prompt = generator._create_class_documentation_prompt(
            self.sample_class, "test context"
        )
        
        assert "SampleClass" in prompt
        assert "BaseClass" in prompt
        assert "A sample class." in prompt
        assert "test context" in prompt
        assert "sample_function" in prompt
        assert "attr1" in prompt
    
    @patch('groq.Groq')
    def test_create_project_overview_prompt(self, mock_groq):
        """Test project overview prompt creation."""
        generator = DocGenerator("test_api_key", self.config)
        
        modules = {"/path/to/module.py": self.sample_module}
        prompt = generator._create_project_overview_prompt(modules, "test-project")
        
        assert "test-project" in prompt
        assert "module.py" in prompt
        assert "1 functions, 1 classes" in prompt