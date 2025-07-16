"""
AI-powered documentation generator using Groq API.

This module provides functionality to generate comprehensive documentation
for Python code using AI models through the Groq API.
"""

import os
import time
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import groq
from analyzer import ModuleInfo, FunctionInfo, ClassInfo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DocGenerationConfig:
    """Configuration for documentation generation."""
    model: str = "llama3-8b-8192"
    max_tokens: int = 1000
    temperature: float = 0.3
    max_requests_per_minute: int = 100
    output_format: str = "markdown"
    include_examples: bool = True
    include_type_hints: bool = True
    include_complexity: bool = False


class RateLimiter:
    """Rate limiter for API calls."""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        now = datetime.now()
        
        # Remove old requests outside time window
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < timedelta(seconds=self.time_window)]
        
        if len(self.requests) >= self.max_requests:
            sleep_time = self.time_window - (now - self.requests[0]).total_seconds()
            if sleep_time > 0:
                logger.info(f"Rate limit reached, waiting {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
        
        self.requests.append(now)


class DocGenerator:
    """AI-powered documentation generator using Groq API."""
    
    def __init__(self, api_key: str, config: Optional[DocGenerationConfig] = None):
        """
        Initialize the documentation generator.
        
        Args:
            api_key: Groq API key
            config: Configuration for documentation generation
        """
        self.client = groq.Groq(api_key=api_key)
        self.config = config or DocGenerationConfig()
        self.rate_limiter = RateLimiter(self.config.max_requests_per_minute)
        
        # Cache for generated documentation
        self.doc_cache = {}
    
    def generate_file_docs(self, module_info: ModuleInfo) -> str:
        """
        Generate comprehensive documentation for a Python module.
        
        Args:
            module_info: Information about the module to document
            
        Returns:
            Generated documentation in markdown format
        """
        try:
            # Check cache first
            cache_key = f"{module_info.file_path}_{module_info.last_modified}"
            if cache_key in self.doc_cache:
                return self.doc_cache[cache_key]
            
            prompt = self._create_file_documentation_prompt(module_info)
            
            self.rate_limiter.wait_if_needed()
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "You are a technical documentation expert. Generate clear, comprehensive documentation for Python code."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            documentation = response.choices[0].message.content
            
            # Cache the result
            self.doc_cache[cache_key] = documentation
            
            return documentation
            
        except Exception as e:
            logger.error(f"Error generating documentation for {module_info.file_path}: {e}")
            return self._generate_fallback_documentation(module_info)
    
    def generate_function_docs(self, function_info: FunctionInfo, context: str = "") -> str:
        """
        Generate documentation for a specific function.
        
        Args:
            function_info: Information about the function
            context: Additional context about the function's purpose
            
        Returns:
            Generated function documentation
        """
        try:
            prompt = self._create_function_documentation_prompt(function_info, context)
            
            self.rate_limiter.wait_if_needed()
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "You are a technical documentation expert. Generate clear, concise documentation for Python functions."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=min(500, self.config.max_tokens),
                temperature=self.config.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating documentation for function {function_info.name}: {e}")
            return self._generate_fallback_function_docs(function_info)
    
    def generate_project_overview(self, modules: Dict[str, ModuleInfo], project_name: str) -> str:
        """
        Generate a comprehensive project overview/README.
        
        Args:
            modules: Dictionary of module information
            project_name: Name of the project
            
        Returns:
            Generated project overview documentation
        """
        try:
            prompt = self._create_project_overview_prompt(modules, project_name)
            
            self.rate_limiter.wait_if_needed()
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "You are a technical documentation expert. Generate professional project documentation and README files."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_tokens * 2,  # More tokens for project overview
                temperature=self.config.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating project overview: {e}")
            return self._generate_fallback_project_overview(modules, project_name)
    
    def generate_class_docs(self, class_info: ClassInfo, context: str = "") -> str:
        """
        Generate documentation for a specific class.
        
        Args:
            class_info: Information about the class
            context: Additional context about the class's purpose
            
        Returns:
            Generated class documentation
        """
        try:
            prompt = self._create_class_documentation_prompt(class_info, context)
            
            self.rate_limiter.wait_if_needed()
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "You are a technical documentation expert. Generate clear, comprehensive documentation for Python classes."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=min(800, self.config.max_tokens),
                temperature=self.config.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating documentation for class {class_info.name}: {e}")
            return self._generate_fallback_class_docs(class_info)
    
    def _create_file_documentation_prompt(self, module_info: ModuleInfo) -> str:
        """Create a prompt for generating file documentation."""
        file_name = Path(module_info.file_path).name
        
        functions_summary = []
        for func in module_info.functions:
            func_args = ", ".join(func.args)
            functions_summary.append(f"- {func.name}({func_args})")
            if func.docstring:
                functions_summary.append(f"  - {func.docstring.split('.')[0]}")
        
        classes_summary = []
        for cls in module_info.classes:
            classes_summary.append(f"- {cls.name}")
            if cls.docstring:
                classes_summary.append(f"  - {cls.docstring.split('.')[0]}")
            if cls.methods:
                classes_summary.append(f"  - Methods: {', '.join([m.name for m in cls.methods[:5]])}")
        
        imports_list = module_info.imports[:10]  # Limit imports to avoid token overflow
        
        prompt = f"""
Analyze this Python module and generate comprehensive documentation:

**File:** {file_name}
**Path:** {module_info.file_path}

**Module Docstring:**
{module_info.docstring or "No docstring available"}

**Functions:**
{chr(10).join(functions_summary) if functions_summary else "No functions found"}

**Classes:**
{chr(10).join(classes_summary) if classes_summary else "No classes found"}

**Imports:**
{chr(10).join(imports_list) if imports_list else "No imports found"}

**Constants:**
{', '.join(module_info.constants) if module_info.constants else "No constants found"}

Generate professional documentation including:
1. Module overview and purpose
2. Key functionality description
3. Usage examples (if applicable)
4. Function and class summaries
5. Dependencies and requirements
6. Notes on implementation details

Format: Clean markdown with appropriate headers and code blocks.
"""
        return prompt
    
    def _create_function_documentation_prompt(self, function_info: FunctionInfo, context: str) -> str:
        """Create a prompt for generating function documentation."""
        type_hints_str = ""
        if function_info.type_hints:
            type_hints_str = f"\n**Type Hints:** {json.dumps(function_info.type_hints, indent=2)}"
        
        prompt = f"""
Generate documentation for this Python function:

**Function:** {function_info.name}
**Arguments:** {', '.join(function_info.args)}
**Return Type:** {function_info.return_annotation or "Not specified"}
**Is Async:** {function_info.is_async}
**Decorators:** {', '.join(function_info.decorators) if function_info.decorators else "None"}
{type_hints_str}

**Existing Docstring:**
{function_info.docstring or "No docstring available"}

**Context:** {context}

Generate clear documentation including:
1. Purpose and functionality
2. Parameter descriptions
3. Return value explanation
4. Usage example
5. Any exceptions or edge cases

Format: Clean markdown suitable for technical documentation.
"""
        return prompt
    
    def _create_class_documentation_prompt(self, class_info: ClassInfo, context: str) -> str:
        """Create a prompt for generating class documentation."""
        methods_summary = []
        for method in class_info.methods:
            method_args = ", ".join(method.args)
            methods_summary.append(f"- {method.name}({method_args})")
        
        prompt = f"""
Generate documentation for this Python class:

**Class:** {class_info.name}
**Base Classes:** {', '.join(class_info.bases) if class_info.bases else "None"}
**Decorators:** {', '.join(class_info.decorators) if class_info.decorators else "None"}

**Existing Docstring:**
{class_info.docstring or "No docstring available"}

**Methods:**
{chr(10).join(methods_summary) if methods_summary else "No methods found"}

**Attributes:**
{', '.join(class_info.attributes) if class_info.attributes else "No attributes found"}

**Context:** {context}

Generate comprehensive documentation including:
1. Class purpose and functionality
2. Constructor parameters
3. Key methods overview
4. Usage examples
5. Inheritance relationships
6. Important attributes

Format: Clean markdown with appropriate structure.
"""
        return prompt
    
    def _create_project_overview_prompt(self, modules: Dict[str, ModuleInfo], project_name: str) -> str:
        """Create a prompt for generating project overview documentation."""
        module_summaries = []
        for path, module in list(modules.items())[:20]:  # Limit to avoid token overflow
            file_name = Path(path).name
            func_count = len(module.functions)
            class_count = len(module.classes)
            module_summaries.append(f"- **{file_name}**: {func_count} functions, {class_count} classes")
        
        prompt = f"""
Generate a comprehensive README.md for this Python project:

**Project Name:** {project_name}
**Total Modules:** {len(modules)}

**Module Structure:**
{chr(10).join(module_summaries)}

**Key Information to Include:**
1. Project title and description
2. Installation instructions
3. Basic usage examples
4. Project structure overview
5. Key features and functionality
6. Requirements and dependencies
7. Contributing guidelines
8. License information

Generate professional documentation suitable for a GitHub repository.
Format: Clean markdown with badges, code examples, and clear structure.
"""
        return prompt
    
    def _generate_fallback_documentation(self, module_info: ModuleInfo) -> str:
        """Generate fallback documentation when AI fails."""
        file_name = Path(module_info.file_path).name
        
        doc = f"# {file_name}\n\n"
        
        if module_info.docstring:
            doc += f"{module_info.docstring}\n\n"
        
        if module_info.functions:
            doc += "## Functions\n\n"
            for func in module_info.functions:
                args_str = ", ".join(func.args)
                doc += f"### {func.name}({args_str})\n\n"
                if func.docstring:
                    doc += f"{func.docstring}\n\n"
        
        if module_info.classes:
            doc += "## Classes\n\n"
            for cls in module_info.classes:
                doc += f"### {cls.name}\n\n"
                if cls.docstring:
                    doc += f"{cls.docstring}\n\n"
        
        return doc
    
    def _generate_fallback_function_docs(self, function_info: FunctionInfo) -> str:
        """Generate fallback function documentation."""
        args_str = ", ".join(function_info.args)
        doc = f"### {function_info.name}({args_str})\n\n"
        
        if function_info.docstring:
            doc += f"{function_info.docstring}\n\n"
        else:
            doc += f"Function {function_info.name} with {len(function_info.args)} parameters.\n\n"
        
        if function_info.return_annotation:
            doc += f"**Returns:** {function_info.return_annotation}\n\n"
        
        return doc
    
    def _generate_fallback_class_docs(self, class_info: ClassInfo) -> str:
        """Generate fallback class documentation."""
        doc = f"### {class_info.name}\n\n"
        
        if class_info.docstring:
            doc += f"{class_info.docstring}\n\n"
        else:
            doc += f"Class {class_info.name} with {len(class_info.methods)} methods.\n\n"
        
        if class_info.bases:
            doc += f"**Inherits from:** {', '.join(class_info.bases)}\n\n"
        
        return doc
    
    def _generate_fallback_project_overview(self, modules: Dict[str, ModuleInfo], project_name: str) -> str:
        """Generate fallback project overview."""
        doc = f"# {project_name}\n\n"
        doc += "Auto-generated project documentation.\n\n"
        doc += "## Project Structure\n\n"
        
        for path, module in modules.items():
            file_name = Path(path).name
            doc += f"- **{file_name}**: {len(module.functions)} functions, {len(module.classes)} classes\n"
        
        return doc
    
    def clear_cache(self):
        """Clear the documentation cache."""
        self.doc_cache.clear()
        logger.info("Documentation cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the documentation cache."""
        return {
            "cache_size": len(self.doc_cache),
            "cache_keys": list(self.doc_cache.keys())
        }