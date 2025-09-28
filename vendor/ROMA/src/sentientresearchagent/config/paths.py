"""
Centralized path configuration for SentientResearchAgent.

This module ensures all runtime files are organized in a consistent structure.
"""

import os
from pathlib import Path
from typing import Optional


class RuntimePaths:
    """Manages all runtime paths for the application."""
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize runtime paths.
        
        Args:
            base_dir: Base directory for all runtime files. 
                     Defaults to SENTIENT_RUNTIME_DIR env var or 'runtime'
        """
        self.base_dir = Path(base_dir or os.getenv("SENTIENT_RUNTIME_DIR", "runtime"))
        
        # Create subdirectories
        self.cache_dir = self.base_dir / "cache"
        self.logs_dir = self.base_dir / "logs"
        self.projects_dir = self.base_dir / "projects"
        self.temp_dir = self.base_dir / "temp"
        
        # Legacy paths (for backward compatibility during migration)
        self.legacy_projects_dir = Path(".agent_projects")
        self.legacy_results_dir = Path("project_results")
        self.legacy_emergency_dir = Path("emergency_backups")
        
        # Experiment paths (new structure)
        self.experiments_dir = Path("experiments")
        self.experiment_results_dir = self.experiments_dir / "results"
        self.experiment_emergency_dir = self.experiments_dir / "emergency_backups"
        self.experiment_configs_dir = self.experiments_dir / "configs"
    
    def ensure_directories(self):
        """Create all necessary directories."""
        # Runtime directories
        self.base_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        self.projects_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
        
        # Experiment directories
        self.experiments_dir.mkdir(exist_ok=True)
        self.experiment_results_dir.mkdir(exist_ok=True)
        self.experiment_emergency_dir.mkdir(exist_ok=True)
        self.experiment_configs_dir.mkdir(exist_ok=True)
    
    def get_log_path(self, name: str = "sentient") -> Path:
        """Get path for a log file."""
        return self.logs_dir / f"{name}.log"
    
    def get_cache_path(self, cache_type: str = "agent") -> Path:
        """Get path for cache directory."""
        cache_path = self.cache_dir / cache_type
        cache_path.mkdir(exist_ok=True)
        return cache_path
    
    def get_project_path(self, project_id: str) -> Path:
        """Get path for a specific project."""
        return self.projects_dir / project_id
    
    def get_experiment_results_path(self, experiment_name: str) -> Path:
        """Get path for experiment results."""
        return self.experiment_results_dir / experiment_name
    
    def get_emergency_backup_path(self) -> Path:
        """Get path for emergency backups."""
        return self.experiment_emergency_dir
    
    @classmethod
    def get_default(cls) -> 'RuntimePaths':
        """Get default runtime paths instance."""
        instance = cls()
        instance.ensure_directories()
        return instance
    
    def migrate_legacy_files(self):
        """Migrate files from legacy locations to new structure."""
        import shutil
        
        migrations = [
            # (source, destination, description)
            (self.legacy_projects_dir, self.projects_dir, "projects"),
            (self.legacy_results_dir, self.experiment_results_dir, "results"),
            (self.legacy_emergency_dir, self.experiment_emergency_dir, "emergency backups"),
        ]
        
        for source, dest, desc in migrations:
            if source.exists() and source.is_dir():
                print(f"Migrating {desc} from {source} to {dest}...")
                for item in source.iterdir():
                    dest_item = dest / item.name
                    if not dest_item.exists():
                        if item.is_dir():
                            shutil.copytree(item, dest_item)
                        else:
                            shutil.copy2(item, dest_item)
                print(f"  Migrated {len(list(source.iterdir()))} items")
    
    def create_readme(self):
        """Create README files explaining the directory structure."""
        readme_content = {
            self.base_dir: """# Runtime Directory

This directory contains all runtime files for SentientResearchAgent.

## Structure

- `cache/` - Cached agent responses and computations
- `logs/` - Application and execution logs
- `projects/` - Active project/session data
- `temp/` - Temporary files

## Notes

- This directory is git-ignored
- Files here are transient and can be safely deleted when the application is not running
- Use `make clean` to remove all runtime files
""",
            self.experiments_dir: """# Experiments Directory

This directory contains experiment configurations and results.

## Structure

- `configs/` - Experiment configuration files
- `results/` - Experiment results organized by timestamp
- `emergency_backups/` - Auto-saved states during crashes

## Usage

See scripts/ directory for utilities to manage experiments.
"""
        }
        
        for path, content in readme_content.items():
            readme_path = path / "README.md"
            if not readme_path.exists():
                readme_path.write_text(content)