"""
Project Structure Manager

Single source of truth for project directory structure creation and path calculation.
All components should use this module to get consistent project paths.
"""

import os
from pathlib import Path
from typing import Dict, Optional
from loguru import logger


class ProjectStructure:
    """Centralized project structure manager."""
    
    @staticmethod
    def get_project_root(project_id: str) -> Path:
        """Get the root directory for a project based on configuration.
        
        Args:
            project_id: The unique project identifier
            
        Returns:
            Path to the project root directory
        """
        # Determine base directory using S3 mount or default paths
        s3_mount_env = os.getenv("S3_MOUNT_ENABLED", "false").lower().strip()
        s3_mount_enabled = s3_mount_env in ("true", "yes", "1", "on", "enabled")
        s3_mount_dir = os.getenv("S3_MOUNT_DIR")
        
        if s3_mount_enabled and s3_mount_dir and os.path.exists(s3_mount_dir):
            # Use S3 mounted directory
            return Path(s3_mount_dir) / project_id
        else:
            # Use default local directory
            from ..config.paths import RuntimePaths
            paths = RuntimePaths.get_default()
            return paths.projects_dir / project_id
    
    @staticmethod
    def get_project_directories(project_id: str) -> Dict[str, str]:
        """Get all project directory paths.
        
        Args:
            project_id: The unique project identifier
            
        Returns:
            Dictionary containing all project directory paths
        """
        project_root = ProjectStructure.get_project_root(project_id)
        
        return {
            'project_id': project_id,
            'project_root': str(project_root),
            'toolkits_dir': str(project_root / "toolkits"),
            'results_dir': str(project_root / "results"),
            'plots_dir': str(project_root / "results" / "plots"),
            'artifacts_dir': str(project_root / "results" / "artifacts"),
            'reports_dir': str(project_root / "results" / "reports")
        }
    
    @staticmethod
    def create_project_structure(project_id: str) -> Dict[str, str]:
        """Create the complete directory structure for a project.
        
        Args:
            project_id: The unique project identifier
            
        Returns:
            Dictionary containing all created directory paths
        """
        dirs = ProjectStructure.get_project_directories(project_id)
        
        # Create all directories
        for dir_key, dir_path in dirs.items():
            if dir_key != 'project_id':  # Skip the ID field
                Path(dir_path).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Created project structure for {project_id}: {dirs['project_root']}")
        return dirs
    
    @staticmethod
    def get_toolkits_dir(project_id: str) -> str:
        """Get the toolkits directory for a project."""
        return ProjectStructure.get_project_directories(project_id)['toolkits_dir']
    
    @staticmethod
    def get_results_dir(project_id: str) -> str:
        """Get the results directory for a project."""
        return ProjectStructure.get_project_directories(project_id)['results_dir']