"""
REAL Sentient ROMA Engine with Safety Depth Limits

Fixed version that prevents infinite recursion while maintaining true ROMA functionality.
"""

from typing import Any, Dict, List, Optional
import time
from roma_agents.sentient_health_agents import (
    HealthAtomizer, HealthPlanner, HealthAggregator,
    DataIngestionAgent, MetricsAnalysisAgent, 
    CoachingAgent, ReportingAgent
)

class ROMARunner:
    """
    Real Sentient ROMA Implementation with Safety Limits
    
    Prevents infinite recursion while maintaining true hierarchical intelligence
    """
    
    def __init__(self, max_depth: int = 3):
        print("🤖 Initializing REAL Sentient ROMA Engine...")
        # ROMA Core Components
        self.atomizer = HealthAtomizer()
        self.planner = HealthPlanner()
        self.aggregator = HealthAggregator()
        
        # SAFETY: Maximum recursion depth
        self.max_depth = max_depth
        
        # Import ResearchAgent
        try:
            from roma_agents.research_agent import ResearchAgent
            research_agent = ResearchAgent()
        except ImportError:
            print("⚠️  ResearchAgent not found, skipping...")
            research_agent = None
        
        # Specialized Health Executors
        self.executors = {
            "ingest": DataIngestionAgent(),
            "metrics": MetricsAnalysisAgent(),
            "research": research_agent,  # NEW
            "coach": CoachingAgent(),
            "report": ReportingAgent(),
            # Map alternative names
            "DataIngestionAgent": DataIngestionAgent(),
            "MetricsAnalysisAgent": MetricsAnalysisAgent(),
            "ResearchAgent": research_agent,  # NEW
            "CoachingAgent": CoachingAgent(),
            "ReportingAgent": ReportingAgent()
        }
        print("✅ REAL ROMA agents initialized successfully")
        if research_agent:
            print("🔍 ResearchAgent integrated")
        print(f"🛡️  Safety: Maximum recursion depth = {max_depth}")
    
    def _solve(self, task: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
        """
        THE CORE ROMA RECURSIVE FUNCTION with Safety Limits
        
        This maintains true ROMA recursion but prevents infinite loops
        """
        indent = "  " * depth
        print(f"{indent}🔄 ROMA Solve (depth={depth}): {task.get('description', str(task)[:50])}...")
        
        # SAFETY CHECK: Prevent infinite recursion
        if depth >= self.max_depth:
            print(f"{indent}🛡️  SAFETY LIMIT: Max depth ({self.max_depth}) reached, executing atomically")
            return self._execute(task, depth)
        
        # STEP 1: Atomizer - Check if task is atomic
        print(f"{indent}📋 Step 1: Atomizer analyzing task...")
        
        try:
            # Enhanced atomizer check with depth awareness
            is_atomic = self._smart_atomizer_check(task, depth)
        except Exception as e:
            print(f"{indent}⚠️  Atomizer failed: {str(e)}, defaulting to atomic")
            is_atomic = True
        
        if is_atomic:
            # STEP 2a: Direct execution for atomic tasks
            print(f"{indent}⚡ Task is ATOMIC - executing directly")
            return self._execute(task, depth)
        else:
            # STEP 2b: Complex task - decompose and recurse
            print(f"{indent}🗺️  Task is COMPLEX - planning decomposition")
            
            try:
                # Plan the task into subtasks
                subtasks = self.planner.plan(task)
                print(f"{indent}📝 Planner created {len(subtasks)} subtasks")
                
                # Safety: Limit number of subtasks
                if not subtasks or len(subtasks) > 6:
                    print(f"{indent}⚠️  Invalid subtask count ({len(subtasks)}), executing atomically")
                    return self._execute(task, depth)
                
                # STEP 3: Execute subtasks recursively with dependency management
                print(f"{indent}🔗 Executing subtasks with dependencies...")
                results = self._execute_subtasks_safely(subtasks, task, depth + 1)
                
                # STEP 4: Aggregate results
                print(f"{indent}🔄 Aggregating {len(results)} subtask results...")
                final_result = self.aggregator.combine(results, task)
                
                print(f"{indent}✅ ROMA recursion completed at depth {depth}")
                return final_result
                
            except Exception as e:
                print(f"{indent}❌ Planning/execution failed: {str(e)}, falling back to atomic")
                return self._execute(task, depth)
    
    def _smart_atomizer_check(self, task: Dict[str, Any], depth: int) -> bool:
        """
        Smart atomizer that considers depth and task complexity
        
        Forces atomic execution for deeper levels and specific patterns
        """
        # Force atomic execution for deeper recursion levels
        if depth >= 2:
            print(f"  🛡️  Depth {depth}: Forcing atomic for safety")
            return True
        
        # Check for specific atomic task types
        task_kind = task.get("kind", "")
        if task_kind in ["ingest", "metrics", "coach", "report"]:
            print(f"  ⚡ Known atomic task '{task_kind}'")
            return True
        
        # Check task description for atomic patterns
        desc = task.get("description", "").lower()
        atomic_patterns = ["single", "quick", "simple", "basic", "direct"]
        if any(pattern in desc for pattern in atomic_patterns):
            print(f"  ⚡ Atomic pattern detected in description")
            return True
        
        # Use AI atomizer for top-level tasks only
        if depth == 0:
            try:
                return self.atomizer.is_atomic(task)
            except Exception as e:
                print(f"  ⚠️  AI Atomizer failed: {str(e)}, defaulting to atomic")
                return True
        
        # Default to atomic for safety
        return True
    
    def _execute_subtasks_safely(self, subtasks: List[Dict], original_task: Dict, depth: int) -> List[Dict[str, Any]]:
        """
        Execute subtasks with safety limits and proper error handling
        """
        indent = "  " * depth
        print(f"{indent}🔗 Managing {len(subtasks)} subtasks safely...")
        
        # Safety: Limit number of subtasks
        if len(subtasks) > 4:
            print(f"{indent}🛡️  Safety: Limiting to first 4 subtasks (was {len(subtasks)})")
            subtasks = subtasks[:4]
        
        results = []
        completed_tasks = {}
        
        for i, subtask in enumerate(subtasks):
            if i >= 4:  # Hard limit
                print(f"{indent}🛡️  Safety: Stopping at 4 subtasks")
                break
                
            subtask_id = subtask.get("id", f"task_{i}")
            print(f"{indent}🔄 Executing subtask {i+1}/{len(subtasks)}: {subtask_id}")
            
            try:
                # Prepare subtask with dependencies
                enhanced_subtask = self._prepare_subtask_data(subtask, original_task, completed_tasks)
                
                # RECURSIVE CALL with timeout protection
                subtask_result = self._solve_with_timeout(enhanced_subtask, depth)
                
                # Store result
                completed_tasks[subtask_id] = subtask_result
                results.append(subtask_result)
                
                status = subtask_result.get("ok", subtask_result.get("status") == "ok")
                print(f"{indent}{'✅' if status else '⚠️'} Subtask {subtask_id} completed")
                
            except Exception as e:
                print(f"{indent}❌ Subtask {subtask_id} failed: {str(e)}")
                error_result = {
                    "ok": False,
                    "error": str(e),
                    "subtask_id": subtask_id,
                    "status": "failed"
                }
                completed_tasks[subtask_id] = error_result
                results.append(error_result)
        
        return results
    
    def _solve_with_timeout(self, task: Dict[str, Any], depth: int) -> Dict[str, Any]:
        """
        Execute solve with timeout protection to prevent hanging
        """
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("ROMA execution timed out")
        
        try:
            # Set 30-second timeout for subtask execution
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)
            
            result = self._solve(task, depth)
            
            # Cancel timeout
            signal.alarm(0)
            return result
            
        except TimeoutError:
            print(f"  ⏰ Subtask timed out after 30s, executing atomically")
            signal.alarm(0)
            return self._execute(task, depth)
        except Exception as e:
            signal.alarm(0)
            raise e
    
    def _prepare_subtask_data(self, subtask: Dict, original_task: Dict, completed_tasks: Dict) -> Dict[str, Any]:
        """
        Prepare subtask with data from dependencies (safely)
        """
        enhanced_subtask = {
            "kind": subtask.get("kind", ""),
            "description": subtask.get("description", ""),
            "data": dict(subtask.get("data", original_task.get("data", {}))),
            "subtask_id": subtask.get("id", "")
        }
        
        # Add dependency outputs (limited for safety)
        dependencies = subtask.get("depends_on", [])[:2]  # Max 2 dependencies
        for dep_id in dependencies:
            if dep_id in completed_tasks:
                dep_result = completed_tasks[dep_id]
                if dep_result.get("normalized_data"):
                    enhanced_subtask["data"]["dependency_data"] = dep_result["normalized_data"]
        
        return enhanced_subtask
    
    def _execute(self, task: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
        """
        Execute atomic task using appropriate specialized agent
        """
        indent = "  " * depth
        task_kind = task.get("kind", "")
        
        # Smart executor mapping
        if task_kind in self.executors:
            executor_name = task_kind
        else:
            # Map by description
            desc = task.get("description", "").lower()
            if any(word in desc for word in ["ingest", "validat", "normalize"]):
                executor_name = "ingest"
            elif any(word in desc for word in ["metric", "calculat", "score", "analysis"]):
                executor_name = "metrics"  
            elif any(word in desc for word in ["coach", "recommend", "advice"]):
                executor_name = "coach"
            elif any(word in desc for word in ["report", "summary", "generate"]):
                executor_name = "report"
            else:
                executor_name = "ingest"  # Safe default
        
        print(f"{indent}⚙️ Executing with {executor_name} agent...")
        
        try:
            executor = self.executors[executor_name]
            result = executor.run(task)
            
            # Ensure result structure
            if isinstance(result, dict):
                result["executor_used"] = executor_name
                result["depth"] = depth
            
            status = result.get("ok", result.get("status") == "ok")
            print(f"{indent}{'✅' if status else '⚠️'} {executor_name} completed")
            
            return result
            
        except Exception as e:
            print(f"{indent}❌ Execution failed: {str(e)}")
            return {
                "ok": False,
                "error": str(e),
                "executor_used": executor_name,
                "depth": depth
            }
    
    # Public API methods
    def run_weekly(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for comprehensive health analysis
        """
        print("🚀 Starting ROMA weekly health analysis...")
        start_time = time.time()
        
        root_task = {
            "kind": "comprehensive_health_analysis",
            "description": "Comprehensive weekly health analysis with personalized insights",
            "data": data,
            "complexity": "high"
        }
        
        try:
            result = self._solve(root_task)
            
            execution_time = time.time() - start_time
            print(f"✅ ROMA analysis completed in {execution_time:.2f}s")
            
            # Add metadata
            if isinstance(result, dict):
                result["roma_metadata"] = {
                    "framework": "Sentient ROMA with Safety Limits",
                    "execution_time_seconds": round(execution_time, 2),
                    "max_depth_limit": self.max_depth,
                    "version": "1.0.0-safe"
                }
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"❌ ROMA analysis failed after {execution_time:.2f}s: {str(e)}")
            return {
                "ok": False,
                "error": f"ROMA execution failed: {str(e)}",
                "execution_time_seconds": round(execution_time, 2)
            }
    
    def analyze_single(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Quick single-entry analysis (should be atomic)"""
        task = {
            "kind": "metrics",
            "description": "Single entry health metrics analysis", 
            "data": entry,
            "complexity": "low"
        }
        return self._solve(task)
    
    def chat(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Health coaching chat (should be atomic)"""
        task = {
            "kind": "coach",
            "description": "Health coaching conversation",
            "data": message,
            "complexity": "low"
        }
        return self._solve(task)
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get ROMA system information"""
        return {
            "framework": "Sentient ROMA with Safety Limits",
            "version": "1.0.0-safe",
            "max_depth": self.max_depth,
            "safety_features": [
                "Recursion depth limits",
                "Subtask count limits", 
                "Timeout protection",
                "Error fallbacks",
                "Smart atomizer decisions"
            ]
        }
