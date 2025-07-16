"""
Tests for the main CLI module.
"""

import os
import sys
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from click.testing import CliRunner

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import cli, get_api_key, create_doc_generator, load_environment


class TestCLI:
    """Test cases for CLI functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)
        
        # Create test Python file
        self.test_file = self.repo_path / "test.py"
        self.test_file.write_text('''
def test_function():
    """A test function."""
    pass

class TestClass:
    """A test class."""
    pass
''')
        
        # Create git structure
        self.git_dir = self.repo_path / ".git"
        self.git_dir.mkdir()
        (self.git_dir / "hooks").mkdir()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_cli_help(self):
        """Test CLI help command."""
        result = self.runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert "Auto-Docs: Automated documentation generator" in result.output
    
    def test_cli_version_info(self):
        """Test CLI with verbose flag."""
        result = self.runner.invoke(cli, ['--verbose', '--help'])
        assert result.exit_code == 0
    
    def test_cli_quiet_mode(self):
        """Test CLI with quiet flag."""
        result = self.runner.invoke(cli, ['--quiet', '--help'])
        assert result.exit_code == 0
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    def test_get_api_key_from_env(self):
        """Test getting API key from environment."""
        api_key = get_api_key()
        assert api_key == 'test_key'
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('click.prompt')
    def test_get_api_key_from_prompt(self, mock_prompt):
        """Test getting API key from prompt."""
        mock_prompt.return_value = 'prompted_key'
        
        api_key = get_api_key()
        
        assert api_key == 'prompted_key'
        mock_prompt.assert_called_once()
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('groq.Groq')
    def test_create_doc_generator(self, mock_groq):
        """Test creating doc generator."""
        generator = create_doc_generator()
        
        mock_groq.assert_called_once_with(api_key='test_key')
        assert generator is not None
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('groq.Groq')
    def test_create_doc_generator_with_overrides(self, mock_groq):
        """Test creating doc generator with config overrides."""
        overrides = {
            'max_tokens': 2000,
            'temperature': 0.5
        }
        
        generator = create_doc_generator(overrides)
        
        assert generator.config.max_tokens == 2000
        assert generator.config.temperature == 0.5
    
    @patch('dotenv.load_dotenv')
    def test_load_environment(self, mock_load_dotenv):
        """Test loading environment variables."""
        # Create .env file
        env_file = Path(self.temp_dir) / ".env"
        env_file.write_text("GROQ_API_KEY=test_key")
        
        with patch('os.path.exists', return_value=True):
            with patch('os.getcwd', return_value=str(self.temp_dir)):
                load_environment()
        
        mock_load_dotenv.assert_called()
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('src.analyzer.RepoAnalyzer')
    @patch('src.ai_generator.DocGenerator')
    def test_analyze_command(self, mock_doc_gen, mock_analyzer):
        """Test analyze command."""
        # Mock analyzer
        mock_module = MagicMock()
        mock_analyzer.return_value.scan_project.return_value = {
            str(self.test_file): mock_module
        }
        
        # Mock doc generator
        mock_doc_gen.return_value.generate_file_docs.return_value = "# Test Documentation"
        mock_doc_gen.return_value.generate_project_overview.return_value = "# Project Overview"
        
        result = self.runner.invoke(cli, [
            'analyze',
            '--repo', str(self.repo_path),
            '--output', str(self.repo_path / 'docs'),
            '--quiet'
        ])
        
        assert result.exit_code == 0
        mock_analyzer.assert_called_once_with(str(self.repo_path))
        mock_analyzer.return_value.scan_project.assert_called_once()
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('src.git_watcher.GitWatcher')
    @patch('src.ai_generator.DocGenerator')
    def test_install_hook_command(self, mock_doc_gen, mock_git_watcher):
        """Test install-hook command."""
        # Mock git watcher
        mock_git_watcher.return_value.get_hook_status.return_value = {
            'post-commit': False
        }
        mock_git_watcher.return_value.install_git_hook.return_value = True
        
        result = self.runner.invoke(cli, [
            'install-hook',
            '--repo', str(self.repo_path),
            '--quiet'
        ])
        
        assert result.exit_code == 0
        mock_git_watcher.assert_called_once()
        mock_git_watcher.return_value.install_git_hook.assert_called_once_with('post-commit')
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('src.git_watcher.GitWatcher')
    @patch('src.ai_generator.DocGenerator')
    def test_install_hook_command_with_existing_hook(self, mock_doc_gen, mock_git_watcher):
        """Test install-hook command with existing hook."""
        # Mock git watcher
        mock_git_watcher.return_value.get_hook_status.return_value = {
            'post-commit': True
        }
        mock_git_watcher.return_value.install_git_hook.return_value = True
        
        result = self.runner.invoke(cli, [
            'install-hook',
            '--repo', str(self.repo_path),
            '--force',
            '--quiet'
        ])
        
        assert result.exit_code == 0
        mock_git_watcher.return_value.install_git_hook.assert_called_once_with('post-commit')
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('src.git_watcher.GitWatcher')
    @patch('src.ai_generator.DocGenerator')
    def test_update_command(self, mock_doc_gen, mock_git_watcher):
        """Test update command."""
        # Mock git watcher
        mock_git_watcher.return_value.check_for_changes.return_value = [str(self.test_file)]
        mock_git_watcher.return_value.update_documentation.return_value = True
        
        result = self.runner.invoke(cli, [
            'update',
            '--repo', str(self.repo_path),
            '--quiet'
        ])
        
        assert result.exit_code == 0
        mock_git_watcher.return_value.update_documentation.assert_called_once()
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('src.git_watcher.GitWatcher')
    @patch('src.ai_generator.DocGenerator')
    def test_update_command_no_changes(self, mock_doc_gen, mock_git_watcher):
        """Test update command with no changes."""
        # Mock git watcher
        mock_git_watcher.return_value.check_for_changes.return_value = []
        
        result = self.runner.invoke(cli, [
            'update',
            '--repo', str(self.repo_path),
            '--quiet'
        ])
        
        assert result.exit_code == 0
        mock_git_watcher.return_value.update_documentation.assert_not_called()
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('src.analyzer.RepoAnalyzer')
    @patch('src.ai_generator.DocGenerator')
    def test_readme_command(self, mock_doc_gen, mock_analyzer):
        """Test readme command."""
        # Mock analyzer
        mock_module = MagicMock()
        mock_analyzer.return_value.scan_project.return_value = {
            str(self.test_file): mock_module
        }
        
        # Mock doc generator
        mock_doc_gen.return_value.generate_project_overview.return_value = "# Project README"
        
        result = self.runner.invoke(cli, [
            'readme',
            '--repo', str(self.repo_path),
            '--output', str(self.repo_path / 'README.md'),
            '--quiet'
        ])
        
        assert result.exit_code == 0
        
        # Check if README was created
        readme_path = self.repo_path / 'README.md'
        assert readme_path.exists()
        assert readme_path.read_text() == "# Project README"
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('click.prompt')
    def test_init_command(self, mock_prompt):
        """Test init command."""
        mock_prompt.return_value = 'test_api_key'
        
        result = self.runner.invoke(cli, [
            'init',
            '--repo', str(self.repo_path),
            '--quiet'
        ])
        
        assert result.exit_code == 0
        
        # Check if config file was created
        config_file = self.repo_path / '.auto-docs.json'
        assert config_file.exists()
        
        # Check if .env file was created
        env_file = self.repo_path / '.env'
        assert env_file.exists()
        
        # Check if docs directory was created
        docs_dir = self.repo_path / 'docs'
        assert docs_dir.exists()
        
        # Check if .gitignore was updated
        gitignore_file = self.repo_path / '.gitignore'
        assert gitignore_file.exists()
        gitignore_content = gitignore_file.read_text()
        assert "# Auto-docs" in gitignore_content
        assert ".env" in gitignore_content
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('src.git_watcher.GitWatcher')
    def test_status_command(self, mock_git_watcher):
        """Test status command."""
        # Create config file
        config_file = self.repo_path / '.auto-docs.json'
        config_data = {
            'enabled': True,
            'auto_update': True,
            'docs_directory': 'docs'
        }
        config_file.write_text(json.dumps(config_data))
        
        # Mock git watcher
        mock_git_watcher.return_value.get_hook_status.return_value = {
            'post-commit': True,
            'pre-push': False,
            'post-merge': False
        }
        mock_git_watcher.return_value.get_recent_commits.return_value = [
            {
                'hash': 'abc123de',
                'message': 'Test commit',
                'author': 'Test Author',
                'date': '2023-01-01T12:00:00',
                'files_changed': 2
            }
        ]
        
        result = self.runner.invoke(cli, [
            'status',
            '--repo', str(self.repo_path)
        ])
        
        assert result.exit_code == 0
        assert "Auto-docs configuration found" in result.output
        assert "Enabled: True" in result.output
        assert "✓ post-commit" in result.output
        assert "✗ pre-push" in result.output
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('src.git_watcher.GitWatcher')
    def test_uninstall_command(self, mock_git_watcher):
        """Test uninstall command."""
        # Mock git watcher
        mock_git_watcher.return_value.uninstall_git_hook.return_value = True
        
        result = self.runner.invoke(cli, [
            'uninstall',
            '--repo', str(self.repo_path),
            '--quiet'
        ], input='n\nn\n')  # Answer 'no' to cleanup questions
        
        assert result.exit_code == 0
        mock_git_watcher.return_value.uninstall_git_hook.assert_called_once_with('post-commit')
    
    def test_analyze_command_invalid_repo(self):
        """Test analyze command with invalid repository."""
        result = self.runner.invoke(cli, [
            'analyze',
            '--repo', '/nonexistent/path',
            '--quiet'
        ])
        
        assert result.exit_code != 0
        assert "Repository path does not exist" in result.output
    
    def test_analyze_command_no_python_files(self):
        """Test analyze command with no Python files."""
        # Remove Python file
        self.test_file.unlink()
        
        with patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'}):
            with patch('src.analyzer.RepoAnalyzer') as mock_analyzer:
                mock_analyzer.return_value.scan_project.return_value = {}
                
                result = self.runner.invoke(cli, [
                    'analyze',
                    '--repo', str(self.repo_path),
                    '--quiet'
                ])
                
                assert result.exit_code == 0
                assert "No Python files found" in result.output
    
    @patch.dict(os.environ, {}, clear=True)
    def test_analyze_command_no_api_key(self):
        """Test analyze command without API key."""
        result = self.runner.invoke(cli, [
            'analyze',
            '--repo', str(self.repo_path),
            '--quiet'
        ], input='')  # Empty input for API key prompt
        
        assert result.exit_code != 0
    
    def test_status_command_no_config(self):
        """Test status command without configuration."""
        result = self.runner.invoke(cli, [
            'status',
            '--repo', str(self.repo_path)
        ])
        
        assert result.exit_code == 0
        assert "No auto-docs configuration found" in result.output
        assert "Run 'auto-docs init' to initialize" in result.output
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('src.analyzer.RepoAnalyzer')
    @patch('src.ai_generator.DocGenerator')
    def test_analyze_command_with_max_files(self, mock_doc_gen, mock_analyzer):
        """Test analyze command with max files limit."""
        # Mock analyzer with multiple files
        mock_modules = {}
        for i in range(5):
            mock_modules[f"file{i}.py"] = MagicMock()
        
        mock_analyzer.return_value.scan_project.return_value = mock_modules
        mock_doc_gen.return_value.generate_file_docs.return_value = "# Test Documentation"
        mock_doc_gen.return_value.generate_project_overview.return_value = "# Project Overview"
        
        result = self.runner.invoke(cli, [
            'analyze',
            '--repo', str(self.repo_path),
            '--max-files', '3',
            '--quiet'
        ])
        
        assert result.exit_code == 0
        # Should have processed only 3 files
        assert mock_doc_gen.return_value.generate_file_docs.call_count == 3
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('src.git_watcher.GitWatcher')
    @patch('src.analyzer.RepoAnalyzer')
    @patch('src.ai_generator.DocGenerator')
    def test_update_command_force_all_files(self, mock_doc_gen, mock_analyzer, mock_git_watcher):
        """Test update command with force flag."""
        # Mock analyzer
        mock_modules = {str(self.test_file): MagicMock()}
        mock_analyzer.return_value.scan_project.return_value = mock_modules
        
        # Mock git watcher
        mock_git_watcher.return_value.update_documentation.return_value = True
        
        result = self.runner.invoke(cli, [
            'update',
            '--repo', str(self.repo_path),
            '--force',
            '--quiet'
        ])
        
        assert result.exit_code == 0
        mock_git_watcher.return_value.update_documentation.assert_called_once_with([str(self.test_file)])
    
    @patch.dict(os.environ, {'GROQ_API_KEY': 'test_key'})
    @patch('src.git_watcher.GitWatcher')
    @patch('src.ai_generator.DocGenerator')
    def test_install_hook_command_failure(self, mock_doc_gen, mock_git_watcher):
        """Test install-hook command failure."""
        # Mock git watcher to fail
        mock_git_watcher.return_value.get_hook_status.return_value = {
            'post-commit': False
        }
        mock_git_watcher.return_value.install_git_hook.return_value = False
        
        result = self.runner.invoke(cli, [
            'install-hook',
            '--repo', str(self.repo_path),
            '--quiet'
        ])
        
        assert result.exit_code != 0
        assert "Failed to install git hook" in result.output