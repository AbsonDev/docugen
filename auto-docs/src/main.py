"""
Main CLI interface for auto-docs.

This module provides the command-line interface for the auto-docs tool,
allowing users to analyze repositories, generate documentation, and manage git hooks.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import click
from dotenv import load_dotenv
import colorama
from tqdm import tqdm

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from analyzer import RepoAnalyzer
from ai_generator import DocGenerator, DocGenerationConfig
from git_watcher import GitWatcher
from documentation_organizer import DocumentationOrganizer

# Initialize colorama for cross-platform colored output
colorama.init()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_environment():
    """Load environment variables from .env file."""
    env_files = ['.env', '.env.local', os.path.expanduser('~/.auto-docs.env')]
    
    for env_file in env_files:
        if os.path.exists(env_file):
            load_dotenv(env_file)
            logger.info(f"Loaded environment from {env_file}")
            break


def get_api_key() -> Optional[str]:
    """Get Groq API key from environment or user input."""
    api_key = os.getenv('GROQ_API_KEY')
    
    if not api_key:
        api_key = click.prompt(
            'Please enter your Groq API key',
            hide_input=True,
            type=str
        )
    
    return api_key


def create_doc_generator(config_overrides: Optional[Dict[str, Any]] = None) -> DocGenerator:
    """Create a DocGenerator instance with configuration."""
    api_key = get_api_key()
    
    if not api_key:
        raise click.ClickException("Groq API key is required")
    
    # Load configuration
    config = DocGenerationConfig(
        model=os.getenv('DEFAULT_MODEL', 'llama3-8b-8192'),
        max_tokens=int(os.getenv('MAX_TOKENS', '1000')),
        temperature=float(os.getenv('TEMPERATURE', '0.3')),
        max_requests_per_minute=int(os.getenv('MAX_REQUESTS_PER_MINUTE', '100')),
        output_format=os.getenv('OUTPUT_FORMAT', 'markdown'),
        include_examples=os.getenv('INCLUDE_EXAMPLES', 'true').lower() == 'true',
        include_type_hints=os.getenv('INCLUDE_TYPE_HINTS', 'true').lower() == 'true',
        include_complexity=os.getenv('INCLUDE_COMPLEXITY', 'false').lower() == 'true'
    )
    
    # Apply overrides
    if config_overrides:
        for key, value in config_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    return DocGenerator(api_key, config)


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--quiet', '-q', is_flag=True, help='Suppress output')
@click.pass_context
def cli(ctx, verbose, quiet):
    """Auto-Docs: Automated documentation generator for Python projects."""
    # Load environment
    load_environment()
    
    # Configure logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif quiet:
        logging.getLogger().setLevel(logging.ERROR)
    
    # Store context
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['quiet'] = quiet


@cli.command()
@click.option('--repo', '-r', default='.', help='Repository path to analyze')
@click.option('--output', '-o', default='docs', help='Output directory for documentation')
@click.option('--format', '-f', default='markdown', help='Output format (markdown)')
@click.option('--include-examples', is_flag=True, help='Include usage examples')
@click.option('--include-complexity', is_flag=True, help='Include complexity metrics')
@click.option('--max-files', default=None, type=int, help='Maximum number of files to process')
@click.option('--organized', '-org', is_flag=True, default=True, help='Generate organized documentation structure')
@click.option('--chunk-size', default=15, type=int, help='Number of files to process per chunk')
@click.option('--priority-only', is_flag=True, help='Process only high priority files')
@click.pass_context
def analyze(ctx, repo, output, format, include_examples, include_complexity, max_files, organized, chunk_size, priority_only):
    """Analyze repository and generate documentation."""
    repo_path = Path(repo).resolve()
    output_path = Path(output).resolve()
    
    if not repo_path.exists():
        raise click.ClickException(f"Repository path does not exist: {repo_path}")
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Initialize analyzer
        analyzer = RepoAnalyzer(str(repo_path))
        
        # Create doc generator
        config_overrides = {
            'output_format': format,
            'include_examples': include_examples,
            'include_complexity': include_complexity
        }
        doc_generator = create_doc_generator(config_overrides)
        
        # Determine analysis method based on project size
        if not ctx.obj['quiet']:
            click.echo(f"Analyzing repository: {repo_path}")
        
        # Fast scan first to determine approach
        structure = analyzer.fast_scan_project_structure()
        total_files = structure['file_count_by_type']['total']
        
        if total_files == 0:
            click.echo("No Python or C# files found in repository")
            return
        
        # Show structure info for large projects
        if total_files > 50 and not ctx.obj['quiet']:
            click.echo(f"📊 Large project detected ({total_files} files)")
            click.echo(f"   • Python files: {structure['file_count_by_type']['python']}")
            click.echo(f"   • C# files: {structure['file_count_by_type']['csharp']}")
            if structure['file_count_by_type']['csharp'] > 0:
                click.echo(f"   • High priority: {len(structure['priority_files']['high'])}")
                click.echo(f"   • Medium priority: {len(structure['priority_files']['medium'])}")
                click.echo(f"   • Low priority: {len(structure['priority_files']['low'])}")
        
        # Use appropriate scanning method
        if total_files > 50:
            # Use chunked processing for large projects
            if not ctx.obj['quiet']:
                mode = "high priority only" if priority_only else "all files"
                click.echo(f"🚀 Using chunked processing ({mode}, {chunk_size} files per chunk)")
            modules = analyzer.scan_project_chunked(chunk_size=chunk_size, priority_only=priority_only)
        else:
            # Use traditional method for small projects
            modules = analyzer.scan_project()
        
        if not modules:
            click.echo("No files were successfully analyzed")
            return
        
        # Limit files if specified
        if max_files:
            modules = dict(list(modules.items())[:max_files])
        
        project_name = repo_path.name
        
        if organized:
            # Use DocumentationOrganizer for structured output
            if not ctx.obj['quiet']:
                click.echo("Generating organized documentation structure...")
            
            # Initialize organizer
            organizer = DocumentationOrganizer(str(output_path), project_name)
            
            # Generate documentation for all modules
            documentation = {}
            with tqdm(total=len(modules), desc="Generating documentation", 
                     disable=ctx.obj['quiet']) as pbar:
                
                for file_path, module_info in modules.items():
                    try:
                        # Generate documentation
                        doc_content = doc_generator.generate_file_docs(module_info)
                        documentation[file_path] = doc_content
                        
                        if ctx.obj['verbose']:
                            click.echo(f"Generated documentation for {file_path}")
                        
                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
                    
                    pbar.update(1)
            
            # Organize documentation into structured folders
            if not ctx.obj['quiet']:
                click.echo("Organizing documentation into folders...")
            
            structure = organizer.organize_documentation(modules, documentation)
            
            # Create architecture documentation
            if not ctx.obj['quiet']:
                click.echo("Creating architecture documentation...")
            
            organizer.create_architecture_docs(modules)
            
            if not ctx.obj['quiet']:
                click.echo(f"Organized documentation generated successfully in {output_path}")
                click.echo(f"Processed {len(modules)} files")
                click.echo(f"Created {len(structure.folders)} documentation folders")
                click.echo(f"View documentation at: {output_path / 'README.md'}")
        
        else:
            # Traditional flat file structure
            with tqdm(total=len(modules), desc="Generating documentation", 
                     disable=ctx.obj['quiet']) as pbar:
                
                for file_path, module_info in modules.items():
                    try:
                        # Generate documentation
                        documentation = doc_generator.generate_file_docs(module_info)
                        
                        # Save documentation
                        relative_path = Path(file_path).relative_to(repo_path)
                        doc_filename = relative_path.with_suffix('.md').name
                        doc_path = output_path / doc_filename
                        
                        with open(doc_path, 'w', encoding='utf-8') as f:
                            f.write(documentation)
                        
                        if ctx.obj['verbose']:
                            click.echo(f"Generated documentation for {file_path}")
                        
                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
                    
                    pbar.update(1)
            
            # Generate project overview
            if not ctx.obj['quiet']:
                click.echo("Generating project overview...")
            
            overview = doc_generator.generate_project_overview(modules, project_name)
            
            readme_path = output_path / "README.md"
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(overview)
            
            if not ctx.obj['quiet']:
                click.echo(f"Documentation generated successfully in {output_path}")
                click.echo(f"Processed {len(modules)} files")
    
    except Exception as e:
        raise click.ClickException(f"Error during analysis: {e}")


@cli.command()
@click.option('--repo', '-r', default='/Users/absondutragalvao/Receba Projects/receba-api', help='Repository path to analyze')
@click.option('--output', '-o', default='receba-docs', help='Output directory for documentation')
@click.option('--max-files', default=None, type=int, help='Maximum number of files to process (for testing)')
@click.option('--chunk-size', default=15, type=int, help='Number of files to process per chunk')
@click.option('--priority-only', is_flag=True, help='Process only high priority files (Controllers, Program.cs, etc.)')
@click.pass_context
def organize(ctx, repo, output, max_files, chunk_size, priority_only):
    """Generate comprehensive organized documentation for C#/.NET projects."""
    repo_path = Path(repo).resolve()
    output_path = Path(output).resolve()
    
    if not repo_path.exists():
        raise click.ClickException(f"Repository path does not exist: {repo_path}")
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Initialize analyzer
        analyzer = RepoAnalyzer(str(repo_path))
        
        # Create doc generator optimized for C#
        config_overrides = {
            'output_format': 'markdown',
            'include_examples': True,
            'include_complexity': False,
            'max_tokens': 2000,  # More tokens for detailed C# documentation
            'temperature': 0.2   # Lower temperature for more consistent technical docs
        }
        doc_generator = create_doc_generator(config_overrides)
        
        # Fast scan first to show project structure
        if not ctx.obj['quiet']:
            click.echo(f"🔍 Analyzing C#/.NET repository: {repo_path}")
        
        structure = analyzer.fast_scan_project_structure()
        
        if not structure['csharp_files']:
            click.echo("❌ No C# files found in repository")
            return
        
        # Show structure info
        if not ctx.obj['quiet']:
            click.echo(f"📊 Project Structure:")
            click.echo(f"   • Total files: {structure['file_count_by_type']['total']}")
            click.echo(f"   • C# files: {structure['file_count_by_type']['csharp']}")
            click.echo(f"   • High priority: {len(structure['priority_files']['high'])}")
            click.echo(f"   • Medium priority: {len(structure['priority_files']['medium'])}")
            click.echo(f"   • Low priority: {len(structure['priority_files']['low'])}")
        
        # Use chunked processing
        if not ctx.obj['quiet']:
            mode = "high priority only" if priority_only else "all files"
            click.echo(f"🚀 Processing {mode} using chunks of {chunk_size} files...")
        
        modules = analyzer.scan_project_chunked(chunk_size=chunk_size, priority_only=priority_only)
        
        # Filter for C# files only (chunked method might return some Python files)
        csharp_modules = {path: info for path, info in modules.items() 
                         if getattr(info, 'file_type', 'python') == 'csharp'}
        
        if not csharp_modules:
            click.echo("❌ No C# files were successfully analyzed")
            return
        
        # Limit files if specified (for testing)
        if max_files:
            csharp_modules = dict(list(csharp_modules.items())[:max_files])
            if not ctx.obj['quiet']:
                click.echo(f"🔬 Limited to {max_files} files for testing")
        
        project_name = repo_path.name
        
        if not ctx.obj['quiet']:
            click.echo(f"✅ Successfully analyzed {len(csharp_modules)} C# files")
            click.echo("📝 Generating comprehensive documentation...")
        
        # Initialize organizer
        organizer = DocumentationOrganizer(str(output_path), project_name)
        
        # Generate documentation for all modules
        documentation = {}
        with tqdm(total=len(csharp_modules), desc="📝 Generating docs", 
                 disable=ctx.obj['quiet']) as pbar:
            
            for file_path, module_info in csharp_modules.items():
                try:
                    # Generate detailed documentation
                    doc_content = doc_generator.generate_file_docs(module_info)
                    documentation[file_path] = doc_content
                    
                    if ctx.obj['verbose']:
                        classification = getattr(module_info, 'classification', 'unknown')
                        click.echo(f"✅ Generated docs for {Path(file_path).name} ({classification})")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing {file_path}: {e}")
                
                pbar.update(1)
        
        # Organize documentation into structured folders
        if not ctx.obj['quiet']:
            click.echo("📂 Organizing documentation into Clean Architecture structure...")
        
        structure = organizer.organize_documentation(csharp_modules, documentation)
        
        # Create architecture documentation
        if not ctx.obj['quiet']:
            click.echo("🏗️ Creating architecture documentation...")
        
        organizer.create_architecture_docs(csharp_modules)
        
        # Show results
        if not ctx.obj['quiet']:
            click.echo("\n🎉 Documentation generation completed!")
            click.echo(f"📊 Statistics:")
            click.echo(f"   • Processed: {len(csharp_modules)} C# files")
            click.echo(f"   • Created: {len(structure.folders)} documentation folders")
            click.echo(f"   • Output: {output_path}")
            click.echo(f"\n🔗 Start reading at: {output_path / 'README.md'}")
            click.echo(f"🧭 Navigation guide: {output_path / 'NAVIGATION.md'}")
    
    except Exception as e:
        raise click.ClickException(f"Error during organized documentation generation: {e}")


@cli.command()
@click.option('--repo', '-r', default='.', help='Repository path')
@click.option('--hook-type', default='post-commit', help='Git hook type to install')
@click.option('--force', is_flag=True, help='Force installation (overwrite existing hook)')
@click.pass_context
def install_hook(ctx, repo, hook_type, force):
    """Install git hook for automatic documentation generation."""
    repo_path = Path(repo).resolve()
    
    if not repo_path.exists():
        raise click.ClickException(f"Repository path does not exist: {repo_path}")
    
    try:
        # Create doc generator
        doc_generator = create_doc_generator()
        
        # Initialize git watcher
        git_watcher = GitWatcher(str(repo_path), doc_generator)
        
        # Check if hook already exists
        hook_status = git_watcher.get_hook_status()
        
        if hook_status.get(hook_type, False) and not force:
            if not click.confirm(f"Git {hook_type} hook already exists. Overwrite?"):
                click.echo("Installation cancelled")
                return
        
        # Install hook
        if git_watcher.install_git_hook(hook_type):
            click.echo(f"Git {hook_type} hook installed successfully")
            
            # Update configuration
            config_file = repo_path / ".auto-docs.json"
            config = {}
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            config.update({
                'hook_installed': True,
                'hook_type': hook_type,
                'installation_date': str(Path().cwd())
            })
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            if not ctx.obj['quiet']:
                click.echo(f"Configuration saved to {config_file}")
        else:
            raise click.ClickException("Failed to install git hook")
    
    except Exception as e:
        raise click.ClickException(f"Error installing hook: {e}")


@cli.command()
@click.option('--repo', '-r', default='.', help='Repository path')
@click.option('--since', help='Update files changed since this commit')
@click.option('--force', is_flag=True, help='Force update all files')
@click.pass_context
def update(ctx, repo, since, force):
    """Update documentation for changed files."""
    repo_path = Path(repo).resolve()
    
    if not repo_path.exists():
        raise click.ClickException(f"Repository path does not exist: {repo_path}")
    
    try:
        # Create doc generator
        doc_generator = create_doc_generator()
        
        # Initialize git watcher
        git_watcher = GitWatcher(str(repo_path), doc_generator)
        
        # Get changed files
        if force:
            # Process all Python files
            analyzer = RepoAnalyzer(str(repo_path))
            modules = analyzer.scan_project()
            changed_files = list(modules.keys())
        else:
            changed_files = git_watcher.check_for_changes(since)
        
        if not changed_files:
            if not ctx.obj['quiet']:
                click.echo("No changes detected")
            return
        
        if not ctx.obj['quiet']:
            click.echo(f"Updating documentation for {len(changed_files)} files...")
        
        # Update documentation
        if git_watcher.update_documentation(changed_files):
            if not ctx.obj['quiet']:
                click.echo("Documentation updated successfully")
        else:
            raise click.ClickException("Failed to update documentation")
    
    except Exception as e:
        raise click.ClickException(f"Error updating documentation: {e}")


@cli.command()
@click.option('--repo', '-r', default='.', help='Repository path')
@click.option('--output', '-o', default='README.md', help='Output file for README')
@click.pass_context
def readme(ctx, repo, output):
    """Generate project README documentation."""
    repo_path = Path(repo).resolve()
    
    if not repo_path.exists():
        raise click.ClickException(f"Repository path does not exist: {repo_path}")
    
    try:
        # Initialize analyzer
        analyzer = RepoAnalyzer(str(repo_path))
        
        # Create doc generator
        doc_generator = create_doc_generator()
        
        # Scan project
        if not ctx.obj['quiet']:
            click.echo(f"Scanning repository: {repo_path}")
        
        modules = analyzer.scan_project()
        
        if not modules:
            click.echo("No Python files found in repository")
            return
        
        # Generate README
        project_name = repo_path.name
        readme_content = doc_generator.generate_project_overview(modules, project_name)
        
        # Save README
        output_path = Path(output)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        if not ctx.obj['quiet']:
            click.echo(f"README generated successfully: {output_path}")
    
    except Exception as e:
        raise click.ClickException(f"Error generating README: {e}")


@cli.command()
@click.option('--repo', '-r', default='.', help='Repository path')
@click.pass_context
def init(ctx, repo):
    """Initialize auto-docs configuration for a repository."""
    repo_path = Path(repo).resolve()
    
    if not repo_path.exists():
        raise click.ClickException(f"Repository path does not exist: {repo_path}")
    
    try:
        # Create configuration file
        config_file = repo_path / ".auto-docs.json"
        
        if config_file.exists():
            if not click.confirm("Configuration file already exists. Overwrite?"):
                click.echo("Initialization cancelled")
                return
        
        # Get API key
        api_key = get_api_key()
        
        # Create .env file
        env_file = repo_path / ".env"
        env_content = f"""# Auto-docs configuration
GROQ_API_KEY={api_key}
DEFAULT_MODEL=llama3-8b-8192
MAX_TOKENS=1000
TEMPERATURE=0.3
MAX_REQUESTS_PER_MINUTE=100
OUTPUT_FORMAT=markdown
BACKUP_ENABLED=true
VERBOSE_MODE=false
"""
        
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        # Create configuration
        config = {
            "enabled": True,
            "auto_update": True,
            "backup_enabled": True,
            "docs_directory": "docs",
            "exclude_patterns": ["__pycache__", ".git", "venv", "env"],
            "include_examples": True,
            "include_type_hints": True,
            "max_file_size": 1000000,
            "last_update": None,
            "created_at": str(Path().cwd())
        }
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Create docs directory
        docs_dir = repo_path / "docs"
        docs_dir.mkdir(exist_ok=True)
        
        # Add to .gitignore
        gitignore_file = repo_path / ".gitignore"
        gitignore_entries = [
            "# Auto-docs",
            ".env",
            ".auto-docs.json",
            "backup-docs/",
            ""
        ]
        
        if gitignore_file.exists():
            with open(gitignore_file, 'r') as f:
                content = f.read()
            
            if "# Auto-docs" not in content:
                with open(gitignore_file, 'a') as f:
                    f.write('\n' + '\n'.join(gitignore_entries))
        else:
            with open(gitignore_file, 'w') as f:
                f.write('\n'.join(gitignore_entries))
        
        if not ctx.obj['quiet']:
            click.echo(f"Auto-docs initialized successfully in {repo_path}")
            click.echo(f"Configuration saved to {config_file}")
            click.echo(f"Environment variables saved to {env_file}")
            click.echo("Run 'auto-docs install-hook' to set up automatic documentation")
    
    except Exception as e:
        raise click.ClickException(f"Error initializing auto-docs: {e}")


@cli.command()
@click.option('--repo', '-r', default='.', help='Repository path')
@click.pass_context
def status(ctx, repo):
    """Show auto-docs status and configuration."""
    repo_path = Path(repo).resolve()
    
    if not repo_path.exists():
        raise click.ClickException(f"Repository path does not exist: {repo_path}")
    
    try:
        # Check configuration
        config_file = repo_path / ".auto-docs.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            click.echo(f"Auto-docs configuration found: {config_file}")
            click.echo(f"Enabled: {config.get('enabled', 'Unknown')}")
            click.echo(f"Auto-update: {config.get('auto_update', 'Unknown')}")
            click.echo(f"Docs directory: {config.get('docs_directory', 'Unknown')}")
        else:
            click.echo("No auto-docs configuration found")
            click.echo("Run 'auto-docs init' to initialize")
            return
        
        # Check git hooks
        git_watcher = GitWatcher(str(repo_path))
        hook_status = git_watcher.get_hook_status()
        
        click.echo("\nGit hooks status:")
        for hook_type, installed in hook_status.items():
            status_icon = "✓" if installed else "✗"
            click.echo(f"  {status_icon} {hook_type}")
        
        # Check recent commits
        recent_commits = git_watcher.get_recent_commits(5)
        if recent_commits:
            click.echo("\nRecent commits:")
            for commit in recent_commits:
                click.echo(f"  {commit['hash']} - {commit['message'][:50]}...")
        
        # Check docs directory
        docs_dir = repo_path / config.get('docs_directory', 'docs')
        if docs_dir.exists():
            doc_files = list(docs_dir.glob("*.md"))
            click.echo(f"\nDocumentation files: {len(doc_files)}")
            for doc_file in doc_files[:5]:  # Show first 5
                click.echo(f"  - {doc_file.name}")
            if len(doc_files) > 5:
                click.echo(f"  ... and {len(doc_files) - 5} more")
        else:
            click.echo(f"\nDocs directory not found: {docs_dir}")
    
    except Exception as e:
        raise click.ClickException(f"Error getting status: {e}")


@cli.command()
@click.option('--repo', '-r', default='.', help='Repository path')
@click.option('--hook-type', default='post-commit', help='Git hook type to uninstall')
@click.pass_context
def uninstall(ctx, repo, hook_type):
    """Uninstall git hooks and clean up auto-docs."""
    repo_path = Path(repo).resolve()
    
    if not repo_path.exists():
        raise click.ClickException(f"Repository path does not exist: {repo_path}")
    
    try:
        git_watcher = GitWatcher(str(repo_path))
        
        # Remove hooks
        if git_watcher.uninstall_git_hook(hook_type):
            click.echo(f"Git {hook_type} hook uninstalled successfully")
        
        # Ask about configuration cleanup
        if click.confirm("Remove auto-docs configuration files?"):
            config_file = repo_path / ".auto-docs.json"
            if config_file.exists():
                config_file.unlink()
                click.echo("Configuration file removed")
            
            env_file = repo_path / ".env"
            if env_file.exists() and click.confirm("Remove .env file?"):
                env_file.unlink()
                click.echo("Environment file removed")
        
        # Ask about documentation cleanup
        if click.confirm("Remove generated documentation?"):
            docs_dir = repo_path / "docs"
            if docs_dir.exists():
                import shutil
                shutil.rmtree(docs_dir)
                click.echo("Documentation directory removed")
            
            backup_dir = repo_path / "backup-docs"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
                click.echo("Backup directory removed")
        
        if not ctx.obj['quiet']:
            click.echo("Auto-docs uninstalled successfully")
    
    except Exception as e:
        raise click.ClickException(f"Error uninstalling auto-docs: {e}")


if __name__ == '__main__':
    cli()