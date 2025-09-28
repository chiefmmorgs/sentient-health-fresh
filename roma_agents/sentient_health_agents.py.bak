"""
Sentient ROMA Health Tracker Agents

Implements the ROMA (Recursive Open Meta-Agent) framework for hierarchical health analysis.
Each agent follows the ROMA pattern: Atomizer → Planner → Executor → Aggregator
"""

from typing import Any, Dict, List, Optional, Union
from agno import Agent, TaskNode
from agno.models.openai import OpenAIChat
from agno.tools.calculator import Calculator
import json
import asyncio


class HealthAtomizer(Agent):
    """
    Atomizer Agent: Determines if a health analysis task is atomic or needs decomposition
    
    ROMA Role: Decides whether a request is atomic (directly executable) or requires planning
    """
    
    def __init__(self):
        super().__init__(
            name="HealthAtomizer",
            role="Health task atomicity analyzer",
            model=OpenAIChat(id="gpt-4o-mini"),
            instructions="""
            You are the Atomizer in a ROMA health analysis system. Your job is to determine if a health analysis task is atomic or needs to be broken down.
            
            A task is ATOMIC if it can be directly executed by a single specialized agent:
            - Data validation and normalization
            - Basic metric calculation (BMI, TDEE) 
            - Simple adherence scoring
            - Single-domain recommendations
            
            A task needs PLANNING if it requires multiple steps:
            - Comprehensive health analysis with insights
            - Multi-domain coaching recommendations  
            - Cross-metric correlations and trends
            - Personalized action plan generation
            
            Always respond with JSON: {"is_atomic": boolean, "reasoning": "explanation", "suggested_agent": "agent_name_if_atomic"}
            """,
            show_tool_calls=False,
            markdown=False
        )
    
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Determine if the health task is atomic"""
        task_description = task.get("description", "")
        user_profile = task.get("user_profile", {})
        daily_logs = task.get("daily_logs", [])
        
        prompt = f"""
        Analyze this health task for atomicity:
        
        Task: {task_description}
        User Profile: {json.dumps(user_profile, indent=2)}
        Daily Logs: {len(daily_logs)} days of data
        
        Determine if this is atomic (single agent can handle) or needs planning (multiple agents required).
        Consider the complexity, data volume, and expected output sophistication.
        """
        
        try:
            response = self.run(prompt)
            result = json.loads(response.content)
            return {
                "status": "ok",
                "is_atomic": result.get("is_atomic", False),
                "reasoning": result.get("reasoning", ""),
                "suggested_agent": result.get("suggested_agent", "")
            }
        except Exception as e:
            return {
                "status": "error",
                "is_atomic": False,
                "reasoning": f"Atomization failed: {str(e)}",
                "suggested_agent": ""
            }


class HealthPlanner(Agent):
    """
    Planner Agent: Breaks down complex health analysis into subtasks
    
    ROMA Role: If planning is needed, breaks task into smaller subtasks for recursive processing
    """
    
    def __init__(self):
        super().__init__(
            name="HealthPlanner", 
            role="Health analysis task decomposition specialist",
            model=OpenAIChat(id="gpt-4o-mini"),
            instructions="""
            You are the Planner in a ROMA health analysis system. Your job is to break down complex health analysis tasks into executable subtasks.
            
            Available specialized agents:
            1. DataIngestionAgent - Validates and normalizes health data
            2. MetricsAnalysisAgent - Calculates health metrics and adherence 
            3. CoachingAgent - Provides personalized recommendations
            4. ReportingAgent - Generates comprehensive reports
            5. TrendsAnalysisAgent - Analyzes patterns and trends
            
            Create a dependency-aware execution plan where:
            - Tasks are ordered by dependencies
            - Independent tasks can run in parallel
            - Each subtask specifies the required agent and input data
            
            Always respond with JSON: {"subtasks": [{"id": "unique_id", "agent": "agent_name", "description": "task_description", "depends_on": ["task_ids"], "priority": 1-5}], "reasoning": "explanation"}
            """,
            show_tool_calls=False,
            markdown=False
        )
    
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Break down the health analysis task into subtasks"""
        task_description = task.get("description", "")
        user_profile = task.get("user_profile", {})
        daily_logs = task.get("daily_logs", [])
        targets = task.get("targets", {})
        
        prompt = f"""
        Plan the execution of this complex health analysis task:
        
        Task: {task_description}
        User Profile: {json.dumps(user_profile, indent=2)}
        Targets: {json.dumps(targets, indent=2)}
        Daily Logs: {len(daily_logs)} days of data
        
        Break this down into subtasks that can be executed by specialized agents.
        Consider dependencies - data must be ingested before metrics can be calculated, etc.
        Focus on parallel execution where possible for efficiency.
        """
        
        try:
            response = self.run(prompt)
            result = json.loads(response.content)
            
            return {
                "status": "ok",
                "subtasks": result.get("subtasks", []),
                "reasoning": result.get("reasoning", ""),
                "execution_strategy": "parallel_with_dependencies"
            }
        except Exception as e:
            # Fallback to standard health analysis plan
            return {
                "status": "ok",
                "subtasks": [
                    {
                        "id": "data_ingestion",
                        "agent": "DataIngestionAgent", 
                        "description": "Validate and normalize health data",
                        "depends_on": [],
                        "priority": 1
                    },
                    {
                        "id": "metrics_analysis", 
                        "agent": "MetricsAnalysisAgent",
                        "description": "Calculate health metrics and adherence scores",
                        "depends_on": ["data_ingestion"],
                        "priority": 2
                    },
                    {
                        "id": "coaching",
                        "agent": "CoachingAgent",
                        "description": "Generate personalized recommendations", 
                        "depends_on": ["data_ingestion", "metrics_analysis"],
                        "priority": 3
                    },
                    {
                        "id": "reporting",
                        "agent": "ReportingAgent",
                        "description": "Create comprehensive health report",
                        "depends_on": ["metrics_analysis", "coaching"],
                        "priority": 4
                    }
                ],
                "reasoning": f"Using fallback plan due to planning error: {str(e)}",
                "execution_strategy": "sequential_fallback"
            }


class DataIngestionAgent(Agent):
    """Executor Agent: Validates and normalizes health data"""
    
    def __init__(self):
        super().__init__(
            name="DataIngestionAgent",
            role="Health data validation and normalization specialist", 
            model=OpenAIChat(id="gpt-4o-mini"),
            tools=[Calculator()],
            instructions="""
            You are a health data validation expert. Your responsibilities:
            
            1. Validate health data completeness and consistency
            2. Normalize data to standard formats and units
            3. Calculate derived metrics like BMI when possible
            4. Flag any concerning health values or anomalies
            5. Identify missing critical fields
            
            Be conservative with health interpretations and flag concerning values for professional review.
            Always return structured JSON with validation results.
            """,
            show_tool_calls=True,
            markdown=False
        )
    
    def execute(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate health data"""
        user_profile = task_data.get("user_profile", {})
        daily_logs = task_data.get("daily_logs", [])
        targets = task_data.get("targets", {})
        
        prompt = f"""
        Validate and normalize this health data:
        
        User Profile: {json.dumps(user_profile, indent=2)}
        Targets: {json.dumps(targets, indent=2)}
        Daily Logs ({len(daily_logs)} days): {json.dumps(daily_logs, indent=2)}
        
        Tasks:
        1. Validate data completeness and identify missing fields
        2. Normalize all values to standard units
        3. Calculate BMI if height/weight available
        4. Flag any concerning health values
        5. Structure data for downstream analysis
        
        Return JSON with: normalized_profile, normalized_logs, normalized_targets, missing_fields, warnings, bmi
        """
        
        try:
            response = self.run(prompt)
            result = json.loads(response.content)
            
            # Ensure required structure
            normalized_data = {
                "status": "ok",
                "normalized_profile": result.get("normalized_profile", user_profile),
                "normalized_logs": result.get("normalized_logs", daily_logs),
                "normalized_targets": result.get("normalized_targets", targets),
                "missing_fields": result.get("missing_fields", []),
                "warnings": result.get("warnings", []),
                "health_flags": result.get("health_flags", []),
                "bmi": result.get("bmi", None)
            }
            
            return normalized_data
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "normalized_profile": user_profile,
                "normalized_logs": daily_logs, 
                "normalized_targets": targets,
                "missing_fields": ["validation_failed"],
                "warnings": ["Data validation failed"],
                "health_flags": [],
                "bmi": None
            }


class MetricsAnalysisAgent(Agent):
    """Executor Agent: Calculates comprehensive health metrics"""
    
    def __init__(self):
        super().__init__(
            name="MetricsAnalysisAgent",
            role="Health metrics calculation and adherence analysis specialist",
            model=OpenAIChat(id="gpt-4o-mini"),
            tools=[Calculator()], 
            instructions="""
            You are a health metrics calculation expert. Your responsibilities:
            
            1. Calculate comprehensive health metrics (averages, totals, ratios)
            2. Compute TDEE using Mifflin-St Jeor equation with activity factors
            3. Analyze adherence to targets as percentages (0-100%)
            4. Calculate calorie balance (intake vs expenditure)
            5. Identify trends and patterns in the data
            
            Use standard formulas:
            - BMR (Men): 10×weight + 6.25×height - 5×age + 5
            - BMR (Women): 10×weight + 6.25×height - 5×age - 161  
            - Activity factors: Sedentary(1.2), Light(1.375), Moderate(1.55), Active(1.725), Very Active(1.9)
            - BMI = weight(kg) / height(m)²
            
            Return structured JSON with all calculated metrics.
            """,
            show_tool_calls=True,
            markdown=False
        )
    
    def execute(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive health metrics"""
        normalized_profile = task_data.get("normalized_profile", {})
        normalized_logs = task_data.get("normalized_logs", [])
        normalized_targets = task_data.get("normalized_targets", {})
        
        prompt = f"""
        Calculate comprehensive health metrics for:
        
        Profile: {json.dumps(normalized_profile, indent=2)}
        Targets: {json.dumps(normalized_targets, indent=2)}
        Daily Logs ({len(normalized_logs)} days): {json.dumps(normalized_logs, indent=2)}
        
        Calculate and return JSON with:
        - averages: sleep_h, steps, water_l, calories_in
        - totals: workouts_count, exercise_minutes  
        - health_indicators: bmi, tdee, calorie_balance
        - adherence_scores: percentage adherence for each target (0-100%)
        - trends: day-to-day patterns and insights
        - performance_summary: overall health performance assessment
        """
        
        try:
            response = self.run(prompt)
            result = json.loads(response.content)
            
            return {
                "status": "ok",
                "metrics": {
                    "averages": result.get("averages", {}),
                    "totals": result.get("totals", {}), 
                    "health_indicators": result.get("health_indicators", {}),
                    "adherence_scores": result.get("adherence_scores", {}),
                    "trends": result.get("trends", {}),
                    "performance_summary": result.get("performance_summary", "")
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "metrics": {
                    "averages": {},
                    "totals": {},
                    "health_indicators": {},
                    "adherence_scores": {},
                    "trends": {},
                    "performance_summary": "Metrics calculation failed"
                }
            }


class CoachingAgent(Agent):
    """Executor Agent: Provides personalized health coaching"""
    
    def __init__(self):
        super().__init__(
            name="CoachingAgent", 
            role="Personalized health and wellness coach",
            model=OpenAIChat(id="gpt-4o-mini"),
            instructions="""
            You are an expert health and wellness coach. Your responsibilities:
            
            1. Analyze individual health data and performance patterns
            2. Provide personalized, actionable recommendations
            3. Create specific daily and weekly action plans  
            4. Offer motivational messaging tailored to the individual
            5. Suggest sustainable habit changes based on adherence gaps
            
            Focus on:
            - Small, achievable improvements over dramatic changes
            - Evidence-based health recommendations
            - Individual constraints and preferences
            - Positive reinforcement and motivation
            - Safety and sustainability
            
            Consider the person's goals, current performance, and life constraints.
            """,
            show_tool_calls=False,
            markdown=False
        )
    
    def execute(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate personalized coaching recommendations"""
        normalized_profile = task_data.get("normalized_profile", {})
        metrics = task_data.get("metrics", {})
        normalized_targets = task_data.get("normalized_targets", {})
        
        prompt = f"""
        As a health coach, provide personalized recommendations for:
        
        Profile: {json.dumps(normalized_profile, indent=2)}
        Targets: {json.dumps(normalized_targets, indent=2)}
        Performance Metrics: {json.dumps(metrics, indent=2)}
        
        Generate coaching insights with JSON structure:
        - daily_suggestions: specific actionable tips for improvement
        - weekly_focus: 2-3 main priorities for the coming week
        - habit_recommendations: sustainable changes to implement
        - motivation_message: encouraging, personalized message
        - milestone_goals: achievable short-term targets
        - constraint_solutions: address any mentioned limitations
        """
        
        try:
            response = self.run(prompt)
            result = json.loads(response.content)
            
            return {
                "status": "ok",
                "coaching": {
                    "daily_suggestions": result.get("daily_suggestions", []),
                    "weekly_focus": result.get("weekly_focus", []),
                    "habit_recommendations": result.get("habit_recommendations", []),
                    "motivation_message": result.get("motivation_message", "Keep up the great work!"),
                    "milestone_goals": result.get("milestone_goals", []),
                    "constraint_solutions": result.get("constraint_solutions", [])
                }
            }
            
        except Exception as e:
            return {
                "status": "error", 
                "error": str(e),
                "coaching": {
                    "daily_suggestions": ["Focus on consistent data logging"],
                    "weekly_focus": ["Establish baseline habits"],
                    "habit_recommendations": ["Track daily health metrics"],
                    "motivation_message": "Every step towards health awareness counts!",
                    "milestone_goals": ["Complete 7 days of consistent logging"],
                    "constraint_solutions": ["Start with simple, manageable changes"]
                }
            }


class ReportingAgent(Agent):
    """Executor Agent: Generates comprehensive health reports"""
    
    def __init__(self):
        super().__init__(
            name="ReportingAgent",
            role="Comprehensive health report generator",
            model=OpenAIChat(id="gpt-4o-mini"), 
            instructions="""
            You are a health data analyst specializing in creating comprehensive, actionable reports.
            
            Your responsibilities:
            1. Synthesize data from multiple analysis sources
            2. Create executive summaries that highlight key insights
            3. Generate structured weekly action plans
            4. Provide health scores with explanations
            5. Offer long-term recommendations and goal setting
            
            Reports should be:
            - Clear and accessible to non-experts
            - Action-oriented with specific next steps  
            - Motivating while being honest about areas for improvement
            - Data-driven with clear supporting metrics
            - Structured for easy reference and follow-up
            """,
            show_tool_calls=False,
            markdown=False
        )
    
    def execute(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        normalized_profile = task_data.get("normalized_profile", {})
        metrics = task_data.get("metrics", {})
        coaching = task_data.get("coaching", {})
        
        prompt = f"""
        Generate a comprehensive health report for:
        
        Profile: {json.dumps(normalized_profile, indent=2)}
        Health Metrics: {json.dumps(metrics, indent=2)}  
        Coaching Insights: {json.dumps(coaching, indent=2)}
        
        Create a structured JSON report with:
        - executive_summary: concise overview of health status
        - health_score: 0-100 score with explanation
        - key_insights: most important findings and patterns  
        - weekly_plan: structured action plan for next week
        - progress_indicators: metrics to track for improvement
        - long_term_recommendations: sustainable health strategy
        - next_actions: immediate actionable steps (max 3)
        """
        
        try:
            response = self.run(prompt)
            result = json.loads(response.content)
            
            return {
                "status": "ok",
                "report": {
                    "executive_summary": result.get("executive_summary", "Health analysis completed"),
                    "health_score": result.get("health_score", 75),
                    "key_insights": result.get("key_insights", []),
                    "weekly_plan": result.get("weekly_plan", {}),
                    "progress_indicators": result.get("progress_indicators", []),
                    "long_term_recommendations": result.get("long_term_recommendations", []),
                    "next_actions": result.get("next_actions", [])
                }
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "report": {
                    "executive_summary": "Report generation encountered issues",
                    "health_score": 50,
                    "key_insights": ["Unable to generate detailed insights"],
                    "weekly_plan": {"focus": ["Ensure consistent data collection"]},
                    "progress_indicators": ["Daily logging consistency"],
                    "long_term_recommendations": ["Establish sustainable tracking habits"],
                    "next_actions": ["Review data quality and completeness"]
                }
            }


class HealthAggregator(Agent):
    """
    Aggregator Agent: Combines results from subtasks into coherent final output
    
    ROMA Role: Collects and integrates results from subtasks into the final answer
    """
    
    def __init__(self):
        super().__init__(
            name="HealthAggregator",
            role="Health analysis results integration specialist",
            model=OpenAIChat(id="gpt-4o-mini"),
            instructions="""
            You are the Aggregator in a ROMA health analysis system. Your job is to integrate results from multiple specialized agents into a coherent, comprehensive final report.
            
            You receive outputs from:
            - DataIngestionAgent: normalized data and validation results
            - MetricsAnalysisAgent: calculated metrics and adherence scores  
            - CoachingAgent: personalized recommendations and action plans
            - ReportingAgent: structured reports and insights
            
            Your job is to:
            1. Combine all agent outputs into a unified response
            2. Resolve any conflicts or inconsistencies
            3. Ensure the final output addresses the original request
            4. Maintain data integrity and coherence across domains
            5. Present insights in a structured, actionable format
            
            The final output should be comprehensive yet accessible.
            """,
            show_tool_calls=False,
            markdown=False
        )
    
    def execute(self, subtask_results: Dict[str, Dict[str, Any]], original_task: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate results from all health analysis subtasks"""
        
        prompt = f"""
        Integrate these health analysis results into a comprehensive final report:
        
        Original Task: {json.dumps(original_task.get('description', 'Comprehensive health analysis'), indent=2)}
        
        Agent Results:
        {json.dumps(subtask_results, indent=2)}
        
        Create a unified health report that:
        1. Addresses the original request comprehensively
        2. Integrates insights from all specialized agents
        3. Resolves any conflicts or inconsistencies  
        4. Provides clear, actionable next steps
        5. Maintains professional health guidance standards
        
        Return JSON with the complete integrated analysis.
        """
        
        try:
            response = self.run(prompt)
            result = json.loads(response.content)
            
            # Ensure we have the key components
            ingestion_result = subtask_results.get("data_ingestion", {})
            metrics_result = subtask_results.get("metrics_analysis", {})
            coaching_result = subtask_results.get("coaching", {})
            reporting_result = subtask_results.get("reporting", {})
            
            # Build comprehensive response
            final_report = {
                "status": "ok",
                "roma_execution": "completed",
                "analysis_type": "hierarchical_multi_agent",
                
                # Core data
                "validated_data": {
                    "profile": ingestion_result.get("normalized_profile", {}),
                    "targets": ingestion_result.get("normalized_targets", {}),
                    "logs_analyzed": len(ingestion_result.get("normalized_logs", [])),
                    "missing_fields": ingestion_result.get("missing_fields", []),
                    "health_warnings": ingestion_result.get("warnings", [])
                },
                
                # Metrics and performance
                "health_metrics": metrics_result.get("metrics", {}),
                "health_score": reporting_result.get("report", {}).get("health_score", 75),
                
                # Insights and recommendations  
                "executive_summary": reporting_result.get("report", {}).get("executive_summary", ""),
                "key_insights": reporting_result.get("report", {}).get("key_insights", []),
                "coaching_recommendations": coaching_result.get("coaching", {}),
                
                # Action plans
                "weekly_plan": reporting_result.get("report", {}).get("weekly_plan", {}),
                "next_actions": reporting_result.get("report", {}).get("next_actions", []),
                "long_term_strategy": reporting_result.get("report", {}).get("long_term_recommendations", []),
                
                # Execution metadata
                "agent_execution": {
                    agent: res.get("status", "unknown") 
                    for agent, res in subtask_results.items()
                },
                "aggregation": result if isinstance(result, dict) else {"raw_response": str(result)}
            }
            
            return final_report
            
        except Exception as e:
            # Fallback aggregation without AI processing
            return {
                "status": "ok",
                "roma_execution": "completed_with_fallback", 
                "analysis_type": "hierarchical_multi_agent",
                "aggregation_error": str(e),
                
                "validated_data": subtask_results.get("data_ingestion", {}),
                "health_metrics": subtask_results.get("metrics_analysis", {}).get("metrics", {}),
                "coaching_recommendations": subtask_results.get("coaching", {}).get("coaching", {}),
                "comprehensive_report": subtask_results.get("reporting", {}).get("report", {}),
                
                "agent_execution": {
                    agent: res.get("status", "unknown")
                    for agent, res in subtask_results.items()
                },
                
                "next_actions": subtask_results.get("reporting", {}).get("report", {}).get("next_actions", ["Review analysis results"])
            }
