"""
Git integration and monitoring module for auto-docs.

This module provides functionality to monitor git repositories for changes
and automatically trigger documentation generation through git hooks.
"""

import os
import shutil
import subprocess
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
import git
from analyzer import RepoAnalyzer
from ai_generator import DocGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GitWatcher:
    """Monitors git repositories and manages documentation generation hooks."""
    
    def __init__(self, repo_path: str, doc_generator: Optional[DocGenerator] = None):
        """
        Initialize the git watcher.
        
        Args:
            repo_path: Path to the git repository
            doc_generator: Optional DocGenerator instance for automatic documentation
        """
        self.repo_path = Path(repo_path).resolve()
        self.doc_generator = doc_generator
        self.analyzer = RepoAnalyzer(str(self.repo_path))
        
        try:
            self.repo = git.Repo(repo_path)
        except git.InvalidGitRepositoryError:
            raise ValueError(f"Not a git repository: {repo_path}")
        
        # Configuration
        self.config_file = self.repo_path / ".auto-docs.json"
        self.backup_dir = self.repo_path / "backup-docs"
        self.docs_dir = self.repo_path / "docs"
        
        # Load configuration
        self.config = self._load_config()
    
    def install_git_hook(self, hook_type: str = "post-commit") -> bool:
        """
        Install a git hook to automatically generate documentation.
        
        Args:
            hook_type: Type of git hook to install (default: post-commit)
            
        Returns:
            True if hook was installed successfully
        """
        hooks_dir = self.repo_path / ".git" / "hooks"
        hook_file = hooks_dir / hook_type
        
        if not hooks_dir.exists():
            logger.error("Git hooks directory not found")
            return False
        
        # Create the hook script
        hook_script = self._create_hook_script(hook_type)
        
        try:
            # Backup existing hook if it exists
            if hook_file.exists():
                backup_file = hooks_dir / f"{hook_type}.backup"
                shutil.copy2(hook_file, backup_file)
                logger.info(f"Existing hook backed up to {backup_file}")
            
            # Write the new hook
            with open(hook_file, 'w') as f:
                f.write(hook_script)
            
            # Make hook executable
            os.chmod(hook_file, 0o755)
            
            logger.info(f"Git {hook_type} hook installed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to install git hook: {e}")
            return False
    
    def uninstall_git_hook(self, hook_type: str = "post-commit") -> bool:
        """
        Uninstall the auto-docs git hook.
        
        Args:
            hook_type: Type of git hook to uninstall
            
        Returns:
            True if hook was uninstalled successfully
        """
        hooks_dir = self.repo_path / ".git" / "hooks"
        hook_file = hooks_dir / hook_type
        backup_file = hooks_dir / f"{hook_type}.backup"
        
        try:
            if hook_file.exists():
                hook_file.unlink()
                logger.info(f"Git {hook_type} hook removed")
            
            # Restore backup if it exists
            if backup_file.exists():
                shutil.copy2(backup_file, hook_file)
                backup_file.unlink()
                logger.info(f"Previous hook restored from backup")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to uninstall git hook: {e}")
            return False
    
    def check_for_changes(self, since_commit: Optional[str] = None) -> List[str]:
        """
        Check for changes in Python files since a specific commit.
        
        Args:
            since_commit: Commit hash to compare against
            
        Returns:
            List of changed Python files
        """
        try:
            return self.analyzer.get_changed_files(since_commit)
        except Exception as e:
            logger.error(f"Error checking for changes: {e}")
            return []
    
    def get_commit_diff(self, commit1: str, commit2: str = "HEAD") -> Dict[str, List[str]]:
        """
        Get the diff between two commits for Python files.
        
        Args:
            commit1: First commit hash
            commit2: Second commit hash (default: HEAD)
            
        Returns:
            Dictionary with added, modified, and deleted files
        """
        try:
            diff = self.repo.git.diff('--name-status', commit1, commit2)
            changes = {'added': [], 'modified': [], 'deleted': []}
            
            for line in diff.split('\n'):
                if not line.strip():
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 2:
                    status = parts[0]
                    file_path = parts[1]
                    
                    if file_path.endswith('.py'):
                        if status == 'A':
                            changes['added'].append(file_path)
                        elif status == 'M':
                            changes['modified'].append(file_path)
                        elif status == 'D':
                            changes['deleted'].append(file_path)
            
            return changes
            
        except Exception as e:
            logger.error(f"Error getting commit diff: {e}")
            return {'added': [], 'modified': [], 'deleted': []}
    
    def update_documentation(self, changed_files: Optional[List[str]] = None) -> bool:
        """
        Update documentation for changed files.
        
        Args:
            changed_files: List of files to update (if None, detect automatically)
            
        Returns:
            True if documentation was updated successfully
        """
        if not self.doc_generator:
            logger.warning("No DocGenerator provided, skipping documentation update")
            return False
        
        try:
            # Get changed files if not provided
            if changed_files is None:
                changed_files = self.check_for_changes()
            
            if not changed_files:
                logger.info("No changes detected, skipping documentation update")
                return True
            
            # Create backup before updating
            self._create_backup()
            
            # Ensure docs directory exists
            self.docs_dir.mkdir(exist_ok=True)
            
            # Update documentation for each changed file
            for file_path in changed_files:
                if not Path(file_path).exists():
                    logger.info(f"File {file_path} was deleted, skipping")
                    continue
                
                try:
                    module_info = self.analyzer.analyze_python_file(file_path)
                    if module_info:
                        documentation = self.doc_generator.generate_file_docs(module_info)
                        
                        # Save documentation
                        doc_filename = Path(file_path).stem + ".md"
                        doc_path = self.docs_dir / doc_filename
                        
                        with open(doc_path, 'w', encoding='utf-8') as f:
                            f.write(documentation)
                        
                        logger.info(f"Updated documentation for {file_path}")
                
                except Exception as e:
                    logger.error(f"Error updating documentation for {file_path}: {e}")
            
            # Update project overview
            self._update_project_overview()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating documentation: {e}")
            return False
    
    def watch_repository(self, interval: int = 5) -> None:
        """
        Watch repository for changes and update documentation automatically.
        
        Args:
            interval: Check interval in seconds
        """
        import time
        
        logger.info(f"Starting to watch repository {self.repo_path}")
        last_commit = self.repo.head.commit.hexsha
        
        try:
            while True:
                current_commit = self.repo.head.commit.hexsha
                
                if current_commit != last_commit:
                    logger.info("Changes detected, updating documentation...")
                    self.update_documentation()
                    last_commit = current_commit
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Stopping repository watcher")
    
    def _create_hook_script(self, hook_type: str) -> str:
        """Create the git hook script content."""
        python_path = shutil.which("python3") or shutil.which("python")
        auto_docs_path = self.repo_path / "auto-docs"
        
        script = f"""#!/bin/bash
# Auto-docs git hook - automatically generates documentation

# Check if auto-docs is available
if [ ! -d "{auto_docs_path}" ]; then
    echo "Auto-docs not found in repository, skipping documentation update"
    exit 0
fi

# Check if Python is available
if [ ! -f "{python_path}" ]; then
    echo "Python not found, skipping documentation update"
    exit 0
fi

# Check if we're in a rebase or merge
if [ -f .git/REBASE_HEAD ] || [ -f .git/MERGE_HEAD ]; then
    echo "In rebase/merge, skipping documentation update"
    exit 0
fi

# Run auto-docs to update documentation
echo "Updating documentation..."
cd "{self.repo_path}"

# Set up environment
export PYTHONPATH="{auto_docs_path}:$PYTHONPATH"

# Run the documentation update
{python_path} -m src.main update --repo . --quiet

# Check if documentation was updated
if [ $? -eq 0 ]; then
    echo "Documentation updated successfully"
else
    echo "Warning: Documentation update failed"
fi

exit 0
"""
        return script
    
    def _load_config(self) -> Dict:
        """Load configuration from .auto-docs.json."""
        default_config = {
            "enabled": True,
            "auto_update": True,
            "backup_enabled": True,
            "docs_directory": "docs",
            "exclude_patterns": ["__pycache__", ".git", "venv", "env"],
            "include_examples": True,
            "include_type_hints": True,
            "max_file_size": 1000000,  # 1MB
            "last_update": None
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    default_config.update(config)
            except Exception as e:
                logger.warning(f"Error loading config: {e}")
        
        return default_config
    
    def _save_config(self) -> None:
        """Save configuration to .auto-docs.json."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def _create_backup(self) -> None:
        """Create a backup of existing documentation."""
        if not self.config.get("backup_enabled", True):
            return
        
        if not self.docs_dir.exists():
            return
        
        try:
            # Create backup directory
            self.backup_dir.mkdir(exist_ok=True)
            
            # Create timestamped backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"docs_backup_{timestamp}"
            
            if self.docs_dir.exists():
                shutil.copytree(self.docs_dir, backup_path)
                logger.info(f"Documentation backed up to {backup_path}")
            
            # Clean old backups (keep last 5)
            backups = sorted([d for d in self.backup_dir.iterdir() if d.is_dir()])
            if len(backups) > 5:
                for old_backup in backups[:-5]:
                    shutil.rmtree(old_backup)
                    logger.info(f"Removed old backup: {old_backup}")
                    
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
    
    def _update_project_overview(self) -> None:
        """Update the project overview documentation."""
        if not self.doc_generator:
            return
        
        try:
            # Analyze all modules
            modules = self.analyzer.scan_project()
            
            # Generate project overview
            project_name = self.repo_path.name
            overview = self.doc_generator.generate_project_overview(modules, project_name)
            
            # Save to README.md in docs directory
            readme_path = self.docs_dir / "README.md"
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(overview)
            
            logger.info("Project overview updated")
            
        except Exception as e:
            logger.error(f"Error updating project overview: {e}")
    
    def get_hook_status(self) -> Dict[str, bool]:
        """Get the status of installed git hooks."""
        hooks_dir = self.repo_path / ".git" / "hooks"
        hook_types = ["post-commit", "pre-push", "post-merge"]
        
        status = {}
        for hook_type in hook_types:
            hook_file = hooks_dir / hook_type
            status[hook_type] = hook_file.exists() and hook_file.is_file()
        
        return status
    
    def cleanup_hooks(self) -> None:
        """Clean up auto-docs related git hooks."""
        for hook_type in ["post-commit", "pre-push", "post-merge"]:
            self.uninstall_git_hook(hook_type)
    
    def get_recent_commits(self, count: int = 10) -> List[Dict]:
        """Get recent commits information."""
        try:
            commits = []
            for commit in self.repo.iter_commits(max_count=count):
                commits.append({
                    'hash': commit.hexsha[:8],
                    'message': commit.message.strip(),
                    'author': str(commit.author),
                    'date': commit.committed_datetime.isoformat(),
                    'files_changed': len(commit.stats.files)
                })
            return commits
        except Exception as e:
            logger.error(f"Error getting recent commits: {e}")
            return []