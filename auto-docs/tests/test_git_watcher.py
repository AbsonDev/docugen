"""
Tests for the git_watcher module.
"""

import os
import sys
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from git_watcher import GitWatcher
from ai_generator import DocGenerator


class TestGitWatcher:
    """Test cases for GitWatcher class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)
        
        # Create a git repository structure
        self.git_dir = self.repo_path / ".git"
        self.git_dir.mkdir()
        (self.git_dir / "hooks").mkdir()
        
        # Create test files
        self.test_file = self.repo_path / "test.py"
        self.test_file.write_text('def test_func(): pass')
        
        self.config_file = self.repo_path / ".auto-docs.json"
        self.docs_dir = self.repo_path / "docs"
        self.backup_dir = self.repo_path / "backup-docs"
        
        # Mock git repo
        self.mock_repo = MagicMock()
        self.mock_doc_generator = MagicMock()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    @patch('git.Repo')
    def test_init_with_valid_repo(self, mock_git_repo):
        """Test GitWatcher initialization with valid repository."""
        mock_git_repo.return_value = self.mock_repo
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        assert watcher.repo_path == self.repo_path
        assert watcher.doc_generator == self.mock_doc_generator
        assert watcher.config_file == self.config_file
        assert watcher.docs_dir == self.docs_dir
        assert watcher.backup_dir == self.backup_dir
    
    @patch('git.Repo')
    def test_init_with_invalid_repo(self, mock_git_repo):
        """Test GitWatcher initialization with invalid repository."""
        mock_git_repo.side_effect = Exception("Invalid repository")
        
        with pytest.raises(ValueError, match="Not a git repository"):
            GitWatcher(str(self.repo_path), self.mock_doc_generator)
    
    @patch('git.Repo')
    def test_install_git_hook(self, mock_git_repo):
        """Test git hook installation."""
        mock_git_repo.return_value = self.mock_repo
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        result = watcher.install_git_hook("post-commit")
        
        assert result is True
        
        # Check if hook file was created
        hook_file = self.git_dir / "hooks" / "post-commit"
        assert hook_file.exists()
        
        # Check if hook is executable
        assert os.access(hook_file, os.X_OK)
    
    @patch('git.Repo')
    def test_install_git_hook_backup_existing(self, mock_git_repo):
        """Test git hook installation with existing hook backup."""
        mock_git_repo.return_value = self.mock_repo
        
        # Create existing hook
        hook_file = self.git_dir / "hooks" / "post-commit"
        hook_file.write_text("#!/bin/bash\necho 'existing hook'")
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        result = watcher.install_git_hook("post-commit")
        
        assert result is True
        
        # Check if backup was created
        backup_file = self.git_dir / "hooks" / "post-commit.backup"
        assert backup_file.exists()
        assert backup_file.read_text() == "#!/bin/bash\necho 'existing hook'"
    
    @patch('git.Repo')
    def test_uninstall_git_hook(self, mock_git_repo):
        """Test git hook uninstallation."""
        mock_git_repo.return_value = self.mock_repo
        
        # Create hook and backup
        hook_file = self.git_dir / "hooks" / "post-commit"
        hook_file.write_text("auto-docs hook")
        
        backup_file = self.git_dir / "hooks" / "post-commit.backup"
        backup_file.write_text("original hook")
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        result = watcher.uninstall_git_hook("post-commit")
        
        assert result is True
        
        # Check if hook was removed and backup restored
        assert hook_file.exists()
        assert hook_file.read_text() == "original hook"
        assert not backup_file.exists()
    
    @patch('git.Repo')
    def test_check_for_changes(self, mock_git_repo):
        """Test checking for changes."""
        mock_git_repo.return_value = self.mock_repo
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        # Mock analyzer's get_changed_files
        with patch.object(watcher.analyzer, 'get_changed_files') as mock_get_changed:
            mock_get_changed.return_value = [str(self.test_file)]
            
            result = watcher.check_for_changes()
            
            assert result == [str(self.test_file)]
            mock_get_changed.assert_called_once_with(None)
    
    @patch('git.Repo')
    def test_get_commit_diff(self, mock_git_repo):
        """Test getting commit diff."""
        mock_git_repo.return_value = self.mock_repo
        self.mock_repo.git.diff.return_value = "A\tfile1.py\nM\tfile2.py\nD\tfile3.py\nA\tfile4.txt"
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        result = watcher.get_commit_diff("commit1", "commit2")
        
        expected = {
            'added': ['file1.py'],
            'modified': ['file2.py'],
            'deleted': ['file3.py']
        }
        
        assert result == expected
        self.mock_repo.git.diff.assert_called_once_with('--name-status', 'commit1', 'commit2')
    
    @patch('git.Repo')
    def test_update_documentation(self, mock_git_repo):
        """Test documentation update."""
        mock_git_repo.return_value = self.mock_repo
        
        # Mock doc generator
        self.mock_doc_generator.generate_file_docs.return_value = "# Test Documentation"
        self.mock_doc_generator.generate_project_overview.return_value = "# Project Overview"
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        # Mock analyzer methods
        with patch.object(watcher.analyzer, 'analyze_python_file') as mock_analyze, \
             patch.object(watcher.analyzer, 'scan_project') as mock_scan:
            
            mock_analyze.return_value = MagicMock()
            mock_scan.return_value = {str(self.test_file): MagicMock()}
            
            result = watcher.update_documentation([str(self.test_file)])
            
            assert result is True
            
            # Check if docs directory was created
            assert self.docs_dir.exists()
            
            # Check if documentation file was created
            doc_file = self.docs_dir / "test.md"
            assert doc_file.exists()
            assert doc_file.read_text() == "# Test Documentation"
    
    @patch('git.Repo')
    def test_update_documentation_no_generator(self, mock_git_repo):
        """Test documentation update without generator."""
        mock_git_repo.return_value = self.mock_repo
        
        watcher = GitWatcher(str(self.repo_path), None)
        
        result = watcher.update_documentation([str(self.test_file)])
        
        assert result is False
    
    @patch('git.Repo')
    def test_load_config_default(self, mock_git_repo):
        """Test loading default configuration."""
        mock_git_repo.return_value = self.mock_repo
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        config = watcher.config
        
        assert config['enabled'] is True
        assert config['auto_update'] is True
        assert config['backup_enabled'] is True
        assert config['docs_directory'] == "docs"
        assert isinstance(config['exclude_patterns'], list)
    
    @patch('git.Repo')
    def test_load_config_from_file(self, mock_git_repo):
        """Test loading configuration from file."""
        mock_git_repo.return_value = self.mock_repo
        
        # Create config file
        config_data = {
            'enabled': False,
            'docs_directory': 'custom_docs',
            'custom_setting': 'value'
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f)
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        config = watcher.config
        
        assert config['enabled'] is False
        assert config['docs_directory'] == 'custom_docs'
        assert config['custom_setting'] == 'value'
        # Default values should still be present
        assert config['auto_update'] is True
    
    @patch('git.Repo')
    def test_save_config(self, mock_git_repo):
        """Test saving configuration."""
        mock_git_repo.return_value = self.mock_repo
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        watcher.config['test_setting'] = 'test_value'
        
        watcher._save_config()
        
        # Check if config file was created
        assert self.config_file.exists()
        
        # Check if config was saved correctly
        with open(self.config_file, 'r') as f:
            saved_config = json.load(f)
        
        assert saved_config['test_setting'] == 'test_value'
    
    @patch('git.Repo')
    def test_create_backup(self, mock_git_repo):
        """Test creating documentation backup."""
        mock_git_repo.return_value = self.mock_repo
        
        # Create docs directory with files
        self.docs_dir.mkdir()
        (self.docs_dir / "file1.md").write_text("Doc 1")
        (self.docs_dir / "file2.md").write_text("Doc 2")
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        watcher._create_backup()
        
        # Check if backup directory was created
        assert self.backup_dir.exists()
        
        # Check if backup contains files
        backup_files = list(self.backup_dir.glob("docs_backup_*/"))
        assert len(backup_files) == 1
        
        backup_content = backup_files[0]
        assert (backup_content / "file1.md").exists()
        assert (backup_content / "file2.md").exists()
    
    @patch('git.Repo')
    def test_create_backup_cleanup_old(self, mock_git_repo):
        """Test backup cleanup of old backups."""
        mock_git_repo.return_value = self.mock_repo
        
        # Create docs directory
        self.docs_dir.mkdir()
        (self.docs_dir / "file1.md").write_text("Doc 1")
        
        # Create backup directory with old backups
        self.backup_dir.mkdir()
        for i in range(7):
            backup_path = self.backup_dir / f"docs_backup_202301{i:02d}_120000"
            backup_path.mkdir()
            (backup_path / "old_file.md").write_text("Old doc")
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        watcher._create_backup()
        
        # Check if old backups were cleaned up (should keep only 5 + 1 new)
        backup_files = list(self.backup_dir.glob("docs_backup_*/"))
        assert len(backup_files) == 6  # 5 old + 1 new
    
    @patch('git.Repo')
    def test_get_hook_status(self, mock_git_repo):
        """Test getting hook status."""
        mock_git_repo.return_value = self.mock_repo
        
        # Create some hooks
        (self.git_dir / "hooks" / "post-commit").write_text("hook content")
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        status = watcher.get_hook_status()
        
        assert status['post-commit'] is True
        assert status['pre-push'] is False
        assert status['post-merge'] is False
    
    @patch('git.Repo')
    def test_cleanup_hooks(self, mock_git_repo):
        """Test cleaning up hooks."""
        mock_git_repo.return_value = self.mock_repo
        
        # Create hooks
        (self.git_dir / "hooks" / "post-commit").write_text("hook content")
        (self.git_dir / "hooks" / "pre-push").write_text("hook content")
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        with patch.object(watcher, 'uninstall_git_hook') as mock_uninstall:
            watcher.cleanup_hooks()
            
            # Should attempt to uninstall all hook types
            assert mock_uninstall.call_count == 3
            mock_uninstall.assert_any_call("post-commit")
            mock_uninstall.assert_any_call("pre-push")
            mock_uninstall.assert_any_call("post-merge")
    
    @patch('git.Repo')
    def test_get_recent_commits(self, mock_git_repo):
        """Test getting recent commits."""
        mock_git_repo.return_value = self.mock_repo
        
        # Mock commits
        mock_commit1 = MagicMock()
        mock_commit1.hexsha = "abc123def456"
        mock_commit1.message = "First commit"
        mock_commit1.author = "Test Author"
        mock_commit1.committed_datetime.isoformat.return_value = "2023-01-01T12:00:00"
        mock_commit1.stats.files = {"file1.py": {}, "file2.py": {}}
        
        mock_commit2 = MagicMock()
        mock_commit2.hexsha = "def456ghi789"
        mock_commit2.message = "Second commit"
        mock_commit2.author = "Test Author"
        mock_commit2.committed_datetime.isoformat.return_value = "2023-01-02T12:00:00"
        mock_commit2.stats.files = {"file3.py": {}}
        
        self.mock_repo.iter_commits.return_value = [mock_commit1, mock_commit2]
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        commits = watcher.get_recent_commits(2)
        
        assert len(commits) == 2
        assert commits[0]['hash'] == "abc123de"
        assert commits[0]['message'] == "First commit"
        assert commits[0]['files_changed'] == 2
        assert commits[1]['hash'] == "def456gh"
        assert commits[1]['message'] == "Second commit"
        assert commits[1]['files_changed'] == 1
    
    @patch('git.Repo')
    def test_watch_repository(self, mock_git_repo):
        """Test repository watching (basic test)."""
        mock_git_repo.return_value = self.mock_repo
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        # Mock the head commit
        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123"
        self.mock_repo.head.commit = mock_commit
        
        # This would run indefinitely, so we'll just test the setup
        # In a real test, we'd use threading or mocking to test the loop
        with patch('time.sleep') as mock_sleep:
            mock_sleep.side_effect = KeyboardInterrupt()  # Stop after first iteration
            
            with pytest.raises(KeyboardInterrupt):
                watcher.watch_repository(interval=1)
    
    @patch('git.Repo')
    def test_create_hook_script(self, mock_git_repo):
        """Test hook script creation."""
        mock_git_repo.return_value = self.mock_repo
        
        watcher = GitWatcher(str(self.repo_path), self.mock_doc_generator)
        
        script = watcher._create_hook_script("post-commit")
        
        assert "#!/bin/bash" in script
        assert "Auto-docs git hook" in script
        assert str(self.repo_path) in script
        assert "python3" in script or "python" in script
        assert "src.main update" in script