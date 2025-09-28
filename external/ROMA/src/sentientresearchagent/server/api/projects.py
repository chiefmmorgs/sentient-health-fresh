"""
Project API Routes

REST endpoints for project management.
"""

from flask import jsonify, request, send_file
from loguru import logger
from datetime import datetime
import json
import os
import tempfile
from pathlib import Path

from ..utils.validation import RequestValidator
from ...config import SentientConfig, LLMConfig, ExecutionConfig, CacheConfig


def create_project_routes(app, project_service, execution_service):
    """
    Create project-related API routes.
    
    Args:
        app: Flask application instance
        project_service: ProjectService instance
        execution_service: ExecutionService instance
    """
    
    @app.route('/api/projects', methods=['GET'])
    def get_projects():
        """Get all projects."""
        try:
            projects_data = project_service.get_all_projects()
            return jsonify(projects_data)
        except Exception as e:
            logger.error(f"Get projects error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/projects', methods=['POST'])
    def create_project():
        """Create a new project."""
        try:
            # Validate request
            is_valid, error_msg, data = RequestValidator.validate_json_required(['goal'])
            if not is_valid:
                return jsonify({"error": error_msg}), 400
            
            goal = data['goal']
            max_steps = data.get('max_steps', 250)  # Default from config would be better
            
            # Validate goal
            goal_valid, goal_error = RequestValidator.validate_project_goal(goal)
            if not goal_valid:
                return jsonify({"error": goal_error}), 400
            
            # Validate max_steps
            steps_valid, steps_error, validated_steps = RequestValidator.validate_max_steps(max_steps)
            if not steps_valid:
                return jsonify({"error": steps_error}), 400
            
            # Create project
            project_dict = project_service.create_project(goal, validated_steps)
            
            # Start project execution in background
            success = execution_service.start_project_execution(
                project_dict['id'], goal, validated_steps
            )
            
            if not success:
                return jsonify({"error": "Failed to start project execution"}), 500
            
            return jsonify({
                "project": project_dict,
                "message": "Project created and started"
            }), 201
            
        except Exception as e:
            logger.error(f"Create project error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/projects/configured', methods=['POST'])
    def create_configured_project():
        """Create a new project with custom configuration."""
        try:
            # Validate request
            is_valid, error_msg, data = RequestValidator.validate_json_required(['goal', 'config'])
            if not is_valid:
                return jsonify({"error": error_msg}), 400
            
            goal = data['goal']
            config_data = data['config']
            max_steps = data.get('max_steps', 250)
            
            # Validate goal
            goal_valid, goal_error = RequestValidator.validate_project_goal(goal)
            if not goal_valid:
                return jsonify({"error": goal_error}), 400
            
            # Validate config
            config_valid, config_error = RequestValidator.validate_project_config(config_data)
            if not config_valid:
                return jsonify({"error": config_error}), 400
            
            # Validate max_steps
            steps_valid, steps_error, validated_steps = RequestValidator.validate_max_steps(max_steps)
            if not steps_valid:
                return jsonify({"error": steps_error}), 400
            
            # Create a custom config for this project
            custom_config = _create_project_config(config_data)
            
            # Create project
            project_dict = project_service.create_project(goal, validated_steps, custom_config)
            
            # Start project execution with custom config in background
            success = execution_service.start_configured_project_execution(
                project_dict['id'], goal, validated_steps, custom_config
            )
            
            if not success:
                return jsonify({"error": "Failed to start configured project execution"}), 500
            
            return jsonify({
                "project": project_dict,
                "message": "Configured project created and started",
                "config_applied": True
            }), 201
            
        except Exception as e:
            logger.error(f"Create configured project error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/projects/<project_id>', methods=['GET'])
    def get_project(project_id: str):
        """Get a specific project and its state."""
        try:
            project_data = project_service.get_project(project_id)
            if not project_data:
                return jsonify({"error": "Project not found"}), 404
            
            return jsonify(project_data)
            
        except Exception as e:
            logger.error(f"Get project error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/projects/<project_id>/switch', methods=['POST'])
    def switch_project(project_id: str):
        """Switch to a different project."""
        try:
            success = project_service.switch_project(project_id)
            if not success:
                return jsonify({"error": "Failed to switch project"}), 500
            
            project_data = project_service.get_project(project_id)
            return jsonify({
                "project": project_data['project'] if project_data else None,
                "message": f"Switched to project {project_id}"
            })
            
        except Exception as e:
            logger.error(f"Switch project error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/projects/<project_id>', methods=['DELETE'])
    def delete_project(project_id: str):
        """Delete a project."""
        try:
            success = project_service.delete_project(project_id)
            if not success:
                return jsonify({"error": "Project not found"}), 404
            
            return jsonify({"message": "Project deleted successfully"})
            
        except Exception as e:
            logger.error(f"Delete project error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/projects/<project_id>/config', methods=['GET'])
    def get_project_config(project_id: str):
        """Get the configuration used for a specific project."""
        try:
            config_data = project_service.get_project_config(project_id)
            if not config_data:
                return jsonify({"error": "Project configuration not found"}), 404
            
            return jsonify({
                "project_id": project_id,
                "config": config_data
            })
            
        except Exception as e:
            logger.error(f"Get project config error: {e}")
            return jsonify({"error": str(e)}), 500
    
    # NEW: Save project results endpoint
    @app.route('/api/projects/<project_id>/save-results', methods=['POST'])
    def save_project_results(project_id: str):
        """Save project results for persistence."""
        try:
            # Get current project state
            project_data = project_service.get_project(project_id)
            if not project_data:
                return jsonify({"error": "Project not found"}), 404
            
            # Get task graph data from system manager
            system_manager = app.system_manager
            graph_data = system_manager.task_graph.to_visualization_dict() if system_manager.task_graph else {}
            
            # Create results package
            results_package = {
                "project": project_data['project'],
                "saved_at": datetime.now().isoformat(),
                "graph_data": graph_data,
                "metadata": {
                    "total_nodes": len(graph_data.get('all_nodes', {})),
                    "project_goal": graph_data.get('overall_project_goal'),
                    "completion_status": _get_project_completion_status(graph_data.get('all_nodes', {}))
                }
            }
            
            # Save to project service
            success = project_service.save_project_results(project_id, results_package)
            if not success:
                return jsonify({"error": "Failed to save project results"}), 500
            
            return jsonify({
                "message": "Project results saved successfully",
                "saved_at": results_package["saved_at"],
                "metadata": results_package["metadata"]
            })
            
        except Exception as e:
            logger.error(f"Save project results error: {e}")
            return jsonify({"error": str(e)}), 500
    
    # NEW: Load project results endpoint
    @app.route('/api/projects/<project_id>/load-results', methods=['GET'])
    def load_project_results(project_id: str):
        """Load saved project results."""
        try:
            results_package = project_service.load_project_results(project_id)
            if not results_package:
                return jsonify({"error": "No saved results found for this project"}), 404
            
            return jsonify(results_package)
            
        except Exception as e:
            logger.error(f"Load project results error: {e}")
            return jsonify({"error": str(e)}), 500
    
    # NEW: Download project report endpoint
    @app.route('/api/projects/<project_id>/download-report', methods=['GET'])
    def download_project_report(project_id: str):
        """Download project report as a file."""
        try:
            # Get report format from query params
            format_type = request.args.get('format', 'markdown')  # markdown, json, html
            
            # Load project results
            results_package = project_service.load_project_results(project_id)
            if not results_package:
                return jsonify({"error": "No saved results found for this project"}), 404
            
            # Generate report content
            if format_type == 'markdown':
                content, filename, mimetype = _generate_markdown_report(results_package)
            elif format_type == 'json':
                content, filename, mimetype = _generate_json_report(results_package)
            elif format_type == 'html':
                content, filename, mimetype = _generate_html_report(results_package)
            else:
                return jsonify({"error": "Unsupported format"}), 400
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'.{format_type}') as tmp_file:
                tmp_file.write(content)
                tmp_file_path = tmp_file.name
            
            try:
                return send_file(
                    tmp_file_path,
                    as_attachment=True,
                    download_name=filename,
                    mimetype=mimetype
                )
            finally:
                # Clean up temp file after sending
                try:
                    os.unlink(tmp_file_path)
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Download project report error: {e}")
            return jsonify({"error": str(e)}), 500
        
    @app.route('/api/executions', methods=['GET'])
    def get_running_executions():
        """Get information about currently running executions."""
        try:
            executions = execution_service.get_running_executions()
            return jsonify({"running_executions": executions})
        except Exception as e:
            logger.error(f"Get executions error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/project/details', methods=['GET'])
    @app.route('/api/project/<project_id>/details', methods=['GET'])
    def get_project_details(project_id=None):
        """Get project environment details including paths and S3 configuration."""
        try:
            # If no project_id provided, try to get from query parameter or use current
            if not project_id:
                project_id = request.args.get('project_id')
                if not project_id:
                    project_id = project_service.project_manager.current_project_id
            
            if not project_id:
                return jsonify({
                    "project_id": None,
                    "message": "No project ID specified and no active project",
                    "timestamp": datetime.now().isoformat()
                })
            
            # Get project details from project manager
            project = project_service.project_manager.projects.get(project_id)
            if not project:
                return jsonify({
                    "project_id": project_id,
                    "error": "Project not found",
                    "timestamp": datetime.now().isoformat()
                })
            
            # Get S3 configuration from environment
            s3_bucket_name = os.getenv("S3_BUCKET_NAME")
            s3_mount_enabled = os.getenv("S3_MOUNT_ENABLED", "false").lower() in ("true", "yes", "1", "on", "enabled")
            
            # Get project directories using centralized structure
            from sentientresearchagent.core.project_structure import ProjectStructure
            project_dirs = ProjectStructure.get_project_directories(project_id)
            
            return jsonify({
                "project_id": project_id,
                "title": project.title,
                "goal": project.goal,
                "s3_bucket_name": s3_bucket_name,
                "s3_mount_enabled": s3_mount_enabled,
                "project_toolkits_dir": project_dirs['toolkits_dir'],
                "project_results_dir": project_dirs['results_dir'],
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Get project details error: {e}")
            return jsonify({"error": str(e)}), 500


def _create_project_config(config_data):
    """Create project configuration from request data."""
    # Extract profile name if provided
    active_profile_name = config_data.get('active_profile_name', 'general_agent')
    
    # Create LLM config
    llm_data = config_data.get('llm', {})
    llm_config = LLMConfig(
        provider=llm_data.get('provider', 'openai'),
        model=llm_data.get('model', 'gpt-4o'),
        temperature=llm_data.get('temperature', 0.7),
        max_tokens=llm_data.get('max_tokens', 4000),
        timeout=llm_data.get('timeout', 60),
        max_retries=llm_data.get('max_retries', 3)
    )
    
    # Create execution config using centralized method for consistency
    exec_data = config_data.get('execution', {})
    execution_config = ExecutionConfig.create_with_overrides(overrides=exec_data)
    
    # Create cache config
    cache_data = config_data.get('cache', {})
    cache_config = CacheConfig(
        enabled=cache_data.get('enabled', True),
        ttl_seconds=cache_data.get('ttl_seconds', 3600),
        max_size=cache_data.get('max_size', 1000),
        cache_type=cache_data.get('cache_type', 'file')
    )
    
    # Create the main config
    return SentientConfig(
        llm=llm_config,
        execution=execution_config,
        cache=cache_config,
        active_profile_name=active_profile_name
    )


def _get_project_completion_status(nodes):
    """Get project completion status from nodes."""
    if not nodes:
        return "no_nodes"
    
    total_nodes = len(nodes)
    completed_nodes = sum(1 for node in nodes.values() if node.get('status') == 'DONE')
    failed_nodes = sum(1 for node in nodes.values() if node.get('status') == 'FAILED')
    
    if completed_nodes == total_nodes:
        return "completed"
    elif failed_nodes > 0:
        return "partial_failure"
    else:
        return "in_progress"


def _generate_markdown_report(results_package):
    """Generate markdown report from results package."""
    project = results_package['project']
    graph_data = results_package['graph_data']
    metadata = results_package['metadata']
    
    # Find root node
    root_node = None
    for node in graph_data.get('all_nodes', {}).values():
        if node.get('layer') == 0 and not node.get('parent_node_id'):
            root_node = node
            break
    
    content = f"""# Project Report: {project['title']}

**Generated:** {results_package['saved_at']}
**Project Goal:** {metadata.get('project_goal', 'N/A')}
**Status:** {metadata.get('completion_status', 'unknown')}
**Total Nodes:** {metadata.get('total_nodes', 0)}

## Project Description
{project.get('description', 'No description provided')}

## Final Result
"""
    
    if root_node and root_node.get('status') == 'DONE':
        full_result = root_node.get('full_result')
        if full_result and isinstance(full_result, dict):
            if full_result.get('output_text_with_citations'):
                content += full_result['output_text_with_citations']
            elif full_result.get('output_text'):
                content += full_result['output_text']
            else:
                content += root_node.get('output_summary', "No final result available.")
        else:
            content += root_node.get('output_summary', "No final result available.")
    else:
        content += "Project not completed or no root node found."
    
    content += f"""

## Execution Summary
- **Total Tasks:** {metadata.get('total_nodes', 0)}
- **Completion Status:** {metadata.get('completion_status', 'unknown')}
- **Saved At:** {results_package['saved_at']}

---
*Generated by Sentient Research Agent*
"""
    
    filename = f"project-report-{project['id']}-{datetime.now().strftime('%Y%m%d')}.md"
    return content, filename, 'text/markdown'


def _generate_json_report(results_package):
    """Generate JSON report from results package."""
    content = json.dumps(results_package, indent=2, default=str)
    filename = f"project-data-{results_package['project']['id']}-{datetime.now().strftime('%Y%m%d')}.json"
    return content, filename, 'application/json'


def _generate_html_report(results_package):
    """Generate HTML report from results package."""
    project = results_package['project']
    metadata = results_package['metadata']
    
    # Find root node
    root_node = None
    for node in results_package['graph_data'].get('all_nodes', {}).values():
        if node.get('layer') == 0 and not node.get('parent_node_id'):
            root_node = node
            break
    
    # Get final result
    final_result = "Project not completed or no root node found."
    if root_node and root_node.get('status') == 'DONE':
        full_result = root_node.get('full_result')
        if full_result and isinstance(full_result, dict):
            if full_result.get('output_text_with_citations'):
                final_result = full_result['output_text_with_citations']
            elif full_result.get('output_text'):
                final_result = full_result['output_text']
            else:
                final_result = root_node.get('output_summary', "No final result available.")
        else:
            final_result = root_node.get('output_summary', "No final result available.")
    
    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Report: {project['title']}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .header {{ border-bottom: 2px solid #eee; padding-bottom: 20px; margin-bottom: 30px; }}
        .metadata {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 30px; }}
        .result {{ background: white; border: 1px solid #ddd; padding: 20px; border-radius: 5px; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 0.9em; }}
        h1 {{ color: #333; }}
        h2 {{ color: #555; }}
        pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Project Report: {project['title']}</h1>
        <p><strong>Generated:</strong> {results_package['saved_at']}</p>
    </div>
    
    <div class="metadata">
        <h2>Project Information</h2>
        <p><strong>Goal:</strong> {metadata.get('project_goal', 'N/A')}</p>
        <p><strong>Status:</strong> {metadata.get('completion_status', 'unknown')}</p>
        <p><strong>Total Tasks:</strong> {metadata.get('total_nodes', 0)}</p>
        <p><strong>Description:</strong> {project.get('description', 'No description provided')}</p>
    </div>
    
    <div class="result">
        <h2>Final Result</h2>
        <pre>{final_result}</pre>
    </div>
    
    <div class="footer">
        <p><em>Generated by Sentient Research Agent</em></p>
    </div>
</body>
</html>"""
    
    filename = f"project-report-{project['id']}-{datetime.now().strftime('%Y%m%d')}.html"
    return content, filename, 'text/html'

    # Configuration endpoints for debugging and validation
    @app.route('/api/config/execution', methods=['GET'])
    def get_execution_config():
        """Get current execution configuration for debugging and frontend display."""
        try:
            from ...config import auto_load_config
            config = auto_load_config()
            
            return jsonify({
                "execution_config": config.execution.to_frontend_dict(),
                "config_source": "Loaded from YAML + environment variables",
                "validation": {
                    "timeout_seconds": config.execution.node_execution_timeout_seconds,
                    "max_concurrent": config.execution.max_concurrent_nodes,
                    "hitl_enabled": config.execution.enable_hitl,
                    "hitl_timeout": config.execution.hitl_timeout_seconds
                }
            })
        except Exception as e:
            logger.error(f"Get execution config error: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/api/config/validate', methods=['POST'])
    def validate_config():
        """Validate a configuration before applying it."""
        try:
            is_valid, error_msg, data = RequestValidator.validate_json_required(['config'])
            if not is_valid:
                return jsonify({"error": error_msg}), 400
            
            config_data = data['config']
            
            # Validate using our centralized method
            try:
                if 'execution' in config_data:
                    ExecutionConfig.create_with_overrides(config_data['execution'])
                return jsonify({"valid": True, "message": "Configuration is valid"})
            except Exception as e:
                return jsonify({"valid": False, "error": str(e)}), 400
                
        except Exception as e:
            logger.error(f"Validate config error: {e}")
            return jsonify({"error": str(e)}), 500
