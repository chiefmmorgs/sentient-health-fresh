"""
REAL Sentient ROMA Health Agents with LLM Fallback Support

Updated to use the LLM fallback system for reliable AI calls
"""

from typing import Any, Dict, List, Optional
import os, json
from datetime import datetime
from storage.db import save_report

# Import the fallback system
try:
    from llm_fallback import call_llm_with_fallback
    FALLBACK_AVAILABLE = True
except ImportError:
    FALLBACK_AVAILABLE = False
    # Fallback to direct litellm if module not available
    from litellm import completion
    
    OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
    MODEL = os.getenv("DEFAULT_MODEL", "gpt-3.5-turbo")

def _ask_llm(prompt: str, system_prompt: str = "") -> str:
    """Helper to call LLM with automatic fallback support"""
    
    if FALLBACK_AVAILABLE:
        # Use the fallback system (preferred)
        try:
            return call_llm_with_fallback(prompt, system_prompt, temperature=0.7)
        except Exception as e:
            return f"LLM fallback error: {e}"
    else:
        # Direct call as backup
        if not OPENROUTER_KEY:
            return "Error: No LLM provider configured"
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            resp = completion(
                model=MODEL,
                messages=messages,
                api_key=OPENROUTER_KEY,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.7
            )
            return resp["choices"][0]["message"]["content"]
        except Exception as e:
            return f"LLM error: {e}"

# Rest of your existing agent classes remain the same...
class HealthAtomizer:
    """ROMA Atomizer with LLM fallback support"""
    
    def is_atomic(self, task: Dict[str, Any]) -> bool:
        task_description = task.get("description", str(task))
        task_data = task.get("data", {})
        
        system_prompt = """You are the Atomizer in a ROMA health analysis system.

Determine if a task is ATOMIC (single agent) or COMPLEX (needs decomposition).

ATOMIC tasks:
- Simple data validation  
- Basic metric calculation
- Single-domain analysis
- Direct coaching questions

COMPLEX tasks:
- Multi-domain health analysis
- Cross-metric correlations
- Comprehensive reporting
- Multi-step reasoning

Respond with JSON: {"is_atomic": boolean, "reasoning": "explanation"}"""

        prompt = f"""
        Analyze this health task for atomicity:
        
        Task: {task_description}
        Data size: {len(str(task_data))} chars
        Data keys: {list(task_data.keys()) if isinstance(task_data, dict) else "non-dict"}
        
        Is this atomic (single agent) or complex (needs decomposition)?
        """
        
        try:
            response = _ask_llm(prompt, system_prompt)
            result = json.loads(response)
            
            is_atomic = result.get("is_atomic", False)
            reasoning = result.get("reasoning", "No reasoning provided")
            
            print(f"🔍 Atomizer: Task is {'ATOMIC' if is_atomic else 'COMPLEX'} - {reasoning}")
            return is_atomic
            
        except Exception as e:
            print(f"⚠️ Atomizer failed, defaulting to COMPLEX: {e}")
            return False

class HealthPlanner:
    """ROMA Planner with LLM fallback support"""
    
    def plan(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        task_description = task.get("description", str(task))
        task_data = task.get("data", {})
        
        system_prompt = """You are the Planner in a ROMA health analysis system.

Break complex health tasks into executable subtasks with proper dependencies.

Available Agents:
- DataIngestionAgent: Validates, normalizes health data
- MetricsAnalysisAgent: Computes health metrics, adherence
- CoachingAgent: Provides personalized recommendations  
- ReportingAgent: Creates comprehensive reports

Respond with JSON: {"subtasks": [{"id": "unique_id", "kind": "agent_type", "description": "task_description", "depends_on": ["task_ids"], "priority": 1-5}], "reasoning": "explanation"}"""

        prompt = f"""
        Create an execution plan for this complex health analysis:
        
        Task: {task_description}
        Data: {json.dumps(task_data, indent=2)}
        
        Break this into subtasks that specialized agents can handle.
        Consider dependencies - data before metrics, metrics before coaching.
        """
        
        try:
            response = _ask_llm(prompt, system_prompt)
            result = json.loads(response)
            
            subtasks = result.get("subtasks", [])
            reasoning = result.get("reasoning", "No planning reasoning")
            
            print(f"🗺️ Planner: Created {len(subtasks)} subtasks - {reasoning}")
            
            # Ensure subtasks have required fields
            for i, subtask in enumerate(subtasks):
                if "id" not in subtask:
                    subtask["id"] = f"subtask_{i}"
                if "data" not in subtask:
                    subtask["data"] = task_data
                if "depends_on" not in subtask:
                    subtask["depends_on"] = []
                if "priority" not in subtask:
                    subtask["priority"] = 3
            
            return subtasks
            
        except Exception as e:
            print(f"⚠️ Planner failed, using fallback plan: {e}")
            # Fallback to standard health analysis pipeline
            return [
                {
                    "id": "data_validation",
                    "kind": "ingest", 
                    "description": "Validate and normalize health data",
                    "depends_on": [],
                    "priority": 1,
                    "data": task_data
                },
                {
                    "id": "health_metrics",
                    "kind": "metrics",
                    "description": "Calculate comprehensive health metrics",
                    "depends_on": ["data_validation"],
                    "priority": 2,
                    "data": task_data
                },
                {
                    "id": "personalized_coaching", 
                    "kind": "coach",
                    "description": "Generate personalized health recommendations",
                    "depends_on": ["health_metrics"],
                    "priority": 3,
                    "data": {"message": "Provide weekly health coaching based on metrics"}
                },
                {
                    "id": "comprehensive_report",
                    "kind": "report",
                    "description": "Create comprehensive health report",
                    "depends_on": ["health_metrics", "personalized_coaching"],
                    "priority": 4,
                    "data": task_data
                }
            ]

class DataIngestionAgent:
    """ROMA Executor: Data validation with LLM fallback"""
    
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        data = task.get("data", {})
        
        if not isinstance(data, dict) or not data:
            return {
                "stage": "ingest",
                "ok": False, 
                "error": "No or invalid input data",
                "agent": "DataIngestionAgent"
            }
        
        # Extract basic health metrics
        steps = int(data.get("steps", 0) or 0)
        sleep_hours = float(data.get("sleep_hours", 0) or 0.0)
        workouts = int(data.get("workouts", 0) or 0)
        water_liters = float(data.get("water_liters", 0) or 0.0)
        
        validation_summary = {
            "steps": steps,
            "sleep_hours": sleep_hours,
            "workouts": workouts,
            "water_liters": water_liters,
            "data_quality": "good" if all([steps > 0, sleep_hours > 0, workouts >= 0, water_liters > 0]) else "incomplete",
            "total_data_points": len([x for x in [steps, sleep_hours, workouts, water_liters] if x > 0])
        }
        
        # AI validation with fallback
        system_prompt = """You are a health data validation expert. Analyze health data for:
1. Completeness and quality
2. Concerning values that need attention  
3. Data consistency and patterns
4. Missing critical information

Provide practical validation insights, not medical diagnosis."""

        prompt = f"""
        Validate this health data and provide insights:
        
        {json.dumps(validation_summary, indent=2)}
        
        Respond with JSON:
        {{
            "validation_status": "good/warning/concerning",
            "data_quality_score": 0-100,
            "missing_fields": ["field1", "field2"],
            "health_flags": ["flag1", "flag2"],
            "recommendations": ["rec1", "rec2"],
            "normalized_data": {{normalized version}}
        }}
        """
        
        ai_validation = _ask_llm(prompt, system_prompt)
        
        try:
            validation_result = json.loads(ai_validation)
        except:
            validation_result = {
                "validation_status": "processed",
                "data_quality_score": 75,
                "missing_fields": [],
                "health_flags": [],
                "recommendations": ["Continue tracking consistently"],
                "normalized_data": validation_summary
            }
        
        return {
            "stage": "ingest",
            "ok": True,
            "agent": "DataIngestionAgent",
            "raw_data": data,
            "validation_summary": validation_summary,
            "ai_validation": validation_result,
            "normalized_data": validation_result.get("normalized_data", validation_summary)
        }

class MetricsAnalysisAgent:
    """ROMA Executor: Health metrics with LLM fallback"""
    
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        data = task.get("data", {})
        
        # Extract metrics
        steps = int(data.get("steps", 0) or 0)
        sleep_hours = float(data.get("sleep_hours", 0) or 0.0)
        workouts = int(data.get("workouts", 0) or 0)
        water_liters = float(data.get("water_liters", 0) or 0.0)
        
        # Calculate scores
        activity_score = min(100, (steps / 10000) * 100 + workouts * 15)
        hydration_score = min(100, (water_liters / 14.0) * 100)
        sleep_score = min(100, (sleep_hours / 56.0) * 100)
        overall_score = (activity_score + hydration_score + sleep_score) / 3
        
        metrics_summary = {
            "steps": steps,
            "sleep_hours": sleep_hours,
            "workouts": workouts, 
            "water_liters": water_liters,
            "scores": {
                "activity": round(activity_score, 1),
                "hydration": round(hydration_score, 1), 
                "sleep": round(sleep_score, 1),
                "overall": round(overall_score, 1)
            },
            "weekly_averages": {
                "daily_steps": round(steps / 7, 0),
                "daily_sleep": round(sleep_hours / 7, 1),
                "daily_water": round(water_liters / 7, 1)
            }
        }
        
        # AI analysis with fallback
        system_prompt = """You are a health metrics analyst. Provide data-driven insights about:
1. Performance against health targets
2. Patterns and trends in the data
3. Areas of strength and improvement  
4. Risk factors or concerning patterns
5. Actionable metrics-based recommendations

Focus on objective analysis, avoid medical advice."""

        prompt = f"""
        Analyze these weekly health metrics:
        
        {json.dumps(metrics_summary, indent=2)}
        
        Provide comprehensive analysis as JSON:
        {{
            "performance_analysis": "detailed assessment",
            "key_insights": ["insight1", "insight2", "insight3"],
            "strengths": ["strength1", "strength2"],
            "improvement_areas": ["area1", "area2"],
            "trend_analysis": "patterns observed",
            "risk_factors": ["risk1", "risk2"],
            "next_week_targets": {{"metric": target}}
        }}
        """
        
        ai_analysis = _ask_llm(prompt, system_prompt)
        
        try:
            analysis_result = json.loads(ai_analysis)
        except:
            analysis_result = {
                "performance_analysis": "Metrics calculated successfully",
                "key_insights": ["Activity and sleep data processed", "Hydration levels tracked"],
                "strengths": ["Consistent data tracking"],
                "improvement_areas": ["Focus on target achievement"],
                "trend_analysis": "Baseline established for future comparison",
                "risk_factors": [],
                "next_week_targets": {"overall_score": min(100, overall_score + 5)}
            }
        
        return {
            "stage": "metrics",
            "ok": True,
            "agent": "MetricsAnalysisAgent",
            "metrics_summary": metrics_summary,
            "ai_analysis": analysis_result,
            "health_score": round(overall_score, 1)
        }

class CoachingAgent:
    """ROMA Executor: AI coaching with fallback"""
    
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        data = task.get("data", {})
        user_message = data.get("message", "Weekly health coaching")
        
        # Context from data
        context_data = {
            "steps": data.get("steps", 0),
            "sleep_hours": data.get("sleep_hours", 0),
            "workouts": data.get("workouts", 0),
            "water_liters": data.get("water_liters", 0)
        }
        
        system_prompt = """You are an expert health and wellness coach. Provide:
1. Personalized, actionable advice
2. Motivational and supportive guidance
3. Specific behavioral recommendations
4. Weekly focus areas and goals
5. Encouraging but realistic expectations

Be warm, professional, and evidence-based. Avoid medical diagnosis."""

        prompt = f"""
        Provide health coaching for this situation:
        
        Request: {user_message}
        Health Context: {json.dumps(context_data, indent=2)}
        
        Respond as JSON:
        {{
            "coaching_response": "main response to user",
            "key_recommendations": ["rec1", "rec2", "rec3"],
            "weekly_focus": ["focus1", "focus2"],
            "motivation_message": "encouraging message",
            "specific_actions": ["action1", "action2", "action3"],
            "success_tips": ["tip1", "tip2"],
            "check_in_questions": ["question1", "question2"]
        }}
        """
        
        coaching_response = _ask_llm(prompt, system_prompt)
        
        try:
            coaching_result = json.loads(coaching_response)
        except:
            coaching_result = {
                "coaching_response": f"Great job tracking your health data! {user_message}",
                "key_recommendations": ["Stay consistent with tracking", "Focus on gradual improvements", "Celebrate small wins"],
                "weekly_focus": ["Consistency", "Balance"],
                "motivation_message": "Every step towards better health counts. You're building great habits!",
                "specific_actions": ["Track daily metrics", "Set realistic weekly goals", "Review progress regularly"],
                "success_tips": ["Start small and build up", "Focus on consistency over perfection"],
                "check_in_questions": ["How are you feeling about your progress?", "What's working well for you?"]
            }
        
        return {
            "stage": "coach",
            "ok": True,
            "agent": "CoachingAgent", 
            "user_request": user_message,
            "coaching_result": coaching_result
        }

class ReportingAgent:
    """ROMA Executor: Report generation with fallback"""
    
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        data = task.get("data", {})
        
        system_prompt = """You are a health report specialist. Create comprehensive reports that:
1. Synthesize all health data into clear insights
2. Provide executive summary of health status
3. Highlight key achievements and areas for improvement
4. Create actionable weekly plans
5. Set realistic goals and milestones

Make reports professional yet accessible."""

        prompt = f"""
        Create a comprehensive weekly health report:
        
        Health Data: {json.dumps(data, indent=2)}
        
        Generate as JSON:
        {{
            "executive_summary": "2-3 sentence overview",
            "week_highlights": ["highlight1", "highlight2", "highlight3"],
            "areas_for_improvement": ["area1", "area2"],
            "health_score_explanation": "why this score",
            "weekly_achievements": ["achievement1", "achievement2"],
            "concerns_to_monitor": ["concern1", "concern2"],
            "next_week_plan": {{
                "primary_goals": ["goal1", "goal2"],
                "daily_actions": ["action1", "action2", "action3"],
                "success_metrics": ["metric1", "metric2"]
            }},
            "long_term_recommendations": ["rec1", "rec2", "rec3"]
        }}
        """
        
        report_content = _ask_llm(prompt, system_prompt)
        
        try:
            report_result = json.loads(report_content)
        except:
            report_result = {
                "executive_summary": "Health data tracked successfully for the week with areas for continued focus.",
                "week_highlights": ["Consistent data tracking", "Health awareness maintained"],
                "areas_for_improvement": ["Optimize daily routines", "Focus on consistency"],
                "health_score_explanation": "Score reflects current tracking and baseline establishment",
                "weekly_achievements": ["Data collection completed"],
                "concerns_to_monitor": ["Maintain tracking consistency"],
                "next_week_plan": {
                    "primary_goals": ["Continue tracking", "Improve consistency"],
                    "daily_actions": ["Log health metrics", "Stay hydrated", "Get adequate sleep"],
                    "success_metrics": ["Daily logging", "Target achievement"]
                },
                "long_term_recommendations": ["Build sustainable habits", "Focus on gradual improvement", "Regular progress reviews"]
            }
        
        # Save report to database
        try:
            report_text = json.dumps(report_result, indent=2)
            report_id = save_report(data, report_text)
        except Exception as e:
            report_id = None
            print(f"Failed to save report: {e}")
        
        return {
            "stage": "report",
            "ok": True,
            "agent": "ReportingAgent",
            "report_result": report_result,
            "report_id": report_id,
            "generated_at": datetime.utcnow().isoformat()
        }

class HealthAggregator:
    """ROMA Aggregator: Intelligent results integration with fallback"""
    
    def combine(self, parts: List[Dict[str, Any]], original_task: Dict[str, Any] = None) -> Dict[str, Any]:
        if not parts:
            return {"ok": False, "error": "No parts to aggregate"}
        
        # Organize results by agent type
        results_by_agent = {}
        for part in parts:
            agent = part.get("agent", part.get("stage", "unknown"))
            results_by_agent[agent] = part
        
        # Extract key information
        ingestion_result = results_by_agent.get("DataIngestionAgent", {})
        metrics_result = results_by_agent.get("MetricsAnalysisAgent", {})
        coaching_result = results_by_agent.get("CoachingAgent", {})
        reporting_result = results_by_agent.get("ReportingAgent", {})
        
        # Build comprehensive response without AI aggregation to avoid complexity
        final_response = {
            "ok": True,
            "roma_execution": "completed_successfully",
            "framework": "Sentient ROMA with LLM Fallback",
            "execution_summary": {
                "total_agents": len(parts),
                "successful_agents": len([p for p in parts if p.get("ok", False)]),
                "agent_results": {part.get("agent", part.get("stage", "unknown")): part.get("ok", False) for part in parts}
            },
            
            # Core data
            "validated_data": {
                "profile": ingestion_result.get("normalized_data", {}),
                "quality_score": ingestion_result.get("ai_validation", {}).get("data_quality_score", 75),
                "warnings": ingestion_result.get("ai_validation", {}).get("health_flags", [])
            },
            
            # Metrics and performance
            "health_metrics": metrics_result.get("metrics_summary", {}),
            "health_score": metrics_result.get("health_score", 75),
            "ai_insights": metrics_result.get("ai_analysis", {}),
            
            # Coaching and recommendations  
            "coaching_recommendations": coaching_result.get("coaching_result", {}),
            "comprehensive_report": reporting_result.get("report_result", {}),
            
            # Quick access summary
            "summary": {
                "health_score": metrics_result.get("health_score", 75),
                "status": "Analysis completed with multi-agent coordination",
                "top_recommendations": coaching_result.get("coaching_result", {}).get("key_recommendations", [])[:3],
                "next_actions": reporting_result.get("report_result", {}).get("next_week_plan", {}).get("daily_actions", [])[:3]
            },
            
            # Execution metadata
            "agent_execution": {
                agent: res.get("ok", False) 
                for agent, res in results_by_agent.items()
            }
        }
        
        return final_response
