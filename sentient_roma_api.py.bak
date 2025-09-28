"""
Sentient ROMA Health Tracker API

Implements the Sentient AGI ROMA framework for hierarchical health analysis.
Uses recursive task decomposition with specialized AI agents.

Architecture:
- Atomizer: Determines task complexity
- Planner: Breaks down complex tasks  
- Executors: Specialized health agents
- Aggregator: Integrates results

ROMA Process: solve(task) -> if atomic: execute(task) else: plan -> [solve(subtasks)] -> aggregate
"""

from dotenv import load_dotenv
from pathlib import Path
import os, sys, json, traceback
from typing import Optional, Dict, Any, List

# Load environment variables
_here = Path(__file__).resolve()
_root = _here.parent
load_dotenv(dotenv_path=_root / ".env")

# Validate AI API keys
openai_key = os.getenv("OPENAI_API_KEY")
anthropic_key = os.getenv("ANTHROPIC_API_KEY")
openrouter_key = os.getenv("OPENROUTER_API_KEY")

if not any([openai_key, anthropic_key, openrouter_key]):
    print("❌ ERROR: No AI API key found!")
    print("\nPlease set one of these in your .env file:")
    print("• OPENAI_API_KEY=sk-your-openai-key-here")
    print("• OPENROUTER_API_KEY=sk-or-your-openrouter-key-here") 
    print("• ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here")
    print("\n🔗 Get API keys:")
    print("• OpenAI: https://platform.openai.com/api-keys")
    print("• OpenRouter (cheaper): https://openrouter.ai/keys")
    print("• Anthropic: https://console.anthropic.com/")
    sys.exit(1)

# Configure AI model based on available keys
if openrouter_key:
    os.environ["OPENAI_API_KEY"] = f"sk-or-{openrouter_key}"
    os.environ["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
    ai_provider = "OpenRouter"
    print("🔧 Using OpenRouter for AI models (cost-effective)")
elif anthropic_key:
    ai_provider = "Anthropic Claude"  
    print("🔧 Using Anthropic Claude for AI models")
else:
    ai_provider = "OpenAI"
    print("🔧 Using OpenAI for AI models")

# FastAPI imports
from fastapi import FastAPI, Body, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Import Sentient ROMA engine
from roma_engine.sentient_roma_runner import SentientRomaHealthRunner

# Initialize FastAPI app
app = FastAPI(
    title="Sentient Health Tracker",
    version="1.0.0-beta",
    description="""
    Advanced health analysis using the Sentient AGI ROMA framework.
    
    **ROMA (Recursive Open Meta-Agent)** uses hierarchical task decomposition:
    - 🧠 **Atomizer**: Analyzes task complexity  
    - 🗺️ **Planner**: Breaks down complex tasks into subtasks
    - ⚙️ **Executors**: Specialized health analysis agents
    - 🔄 **Aggregator**: Integrates results into coherent insights
    
    This enables sophisticated multi-agent reasoning for personalized health recommendations.
    """,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True, 
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Sentient ROMA engine
print("🚀 Initializing Sentient ROMA Health Analysis Engine...")
try:
    roma_runner = SentientRomaHealthRunner()
    print("✅ Sentient ROMA engine ready!")
    roma_status = "active"
except Exception as e:
    print(f"❌ Failed to initialize ROMA engine: {str(e)}")
    roma_runner = None
    roma_status = "failed"

# Pydantic models
class HealthEntry(BaseModel):
    meal_log: Optional[str] = Field(None, example="Grilled salmon with quinoa and vegetables")
    exercise_log: Optional[str] = Field(None, example="45 min strength training + 20 min cardio")
    sleep_log: Optional[str] = Field(None, example="7.5h")
    mood_log: Optional[str] = Field(None, example="Energetic and focused")
    water_intake_l: Optional[float] = Field(None, example=3.2)
    notes: Optional[str] = Field(None, example="Great energy today, feeling strong")

class ChatMessage(BaseModel):
    message: str = Field(..., example="I'm struggling with consistency in my workouts. Any advice?")
    context: Optional[str] = Field(None, example="I work from home and have been sedentary")

# API Endpoints
@app.get("/")
def home():
    """System information and available endpoints"""
    return {
        "name": "Sentient ROMA Health Tracker",
        "version": "1.0.0-beta",
        "framework": "Sentient AGI ROMA (Recursive Open Meta-Agent)",
        "description": "Advanced hierarchical AI system for health analysis",
        "ai_provider": ai_provider,
        "roma_status": roma_status,
        "architecture": {
            "type": "recursive_hierarchical_multi_agent",
            "components": ["atomizer", "planner", "executors", "aggregator"],
            "workflow": "solve(task) → if atomic: execute(task) else: plan → [solve(subtasks)] → aggregate"
        },
        "endpoints": {
            "/": "System information",
            "/docs": "Interactive API documentation",
            "/health": "System health check", 
            "/roma-info": "Detailed ROMA system information",
            "/example": "Example payload for testing",
            "/weekly-report": "🚀 Main feature: Comprehensive AI health analysis (POST)",
            "/analyze": "Quick single-entry analysis (POST)",
            "/chat": "Chat with AI health coach (POST)"
        },
        "status": "🤖 ROMA agents ready for hierarchical analysis"
    }

@app.get("/health")
def health_check():
    """System health and readiness check"""
    return {
        "status": "healthy" if roma_status == "active" else "degraded",
        "roma_engine": roma_status,
        "ai_provider": ai_provider,
        "components": {
            "atomizer": "ready" if roma_runner else "unavailable",
            "planner": "ready" if roma_runner else "unavailable", 
            "executors": "ready" if roma_runner else "unavailable",
            "aggregator": "ready" if roma_runner else "unavailable"
        },
        "api_keys_configured": {
            "openai": bool(openai_key),
            "anthropic": bool(anthropic_key),
            "openrouter": bool(openrouter_key)
        }
    }

@app.get("/roma-info")
def roma_system_info():
    """Detailed information about the ROMA system architecture"""
    if not roma_runner:
        raise HTTPException(status_code=503, detail="ROMA engine not available")
    
    return roma_runner.get_system_info()

@app.get("/example")
def example_payload():
    """Example payload demonstrating the expected data format"""
    return {
        "user_profile": {
            "age": 32,
            "sex": "F",
            "height_cm": 168,
            "weight_kg": 65,
            "goal": "improve overall fitness and energy levels",
            "constraints": "busy work schedule, limited gym access, vegetarian diet"
        },
        "targets": {
            "sleep_h": 7.5,
            "steps": 10000, 
            "workouts_per_week": 4,
            "calories_in": 1900,
            "water_liters": 2.8
        },
        "daily_logs": [
            {
                "date": "2025-09-15",
                "sleep_hours": 6.8,
                "steps": 7800,
                "workouts": [
                    {"type": "yoga", "minutes": 30, "intensity_1_5": 2},
                    {"type": "walking", "minutes": 20, "intensity_1_5": 3}
                ],
                "calories_in": 1850,
                "water_liters": 2.4,
                "mood_1_5": 3,
                "notes": "tired from late work meeting"
            },
            {
                "date": "2025-09-16",
                "sleep_hours": 7.5,
                "steps": 11200,
                "workouts": [{"type": "strength", "minutes": 40, "intensity_1_5": 4}],
                "calories_in": 1920,
                "water_liters": 3.1,
                "mood_1_5": 4,
                "notes": "great energy, productive day"
            },
            {
                "date": "2025-09-17",
                "sleep_hours": 8.0,
                "steps": 9500,
                "workouts": [],
                "calories_in": 1780,
                "water_liters": 2.9,
                "mood_1_5": 4,
                "notes": "rest day, focused on meal prep"
            },
            {
                "date": "2025-09-18",
                "sleep_hours": 7.2,
                "steps": 13000,
                "workouts": [
                    {"type": "cardio", "minutes": 35, "intensity_1_5": 4},
                    {"type": "flexibility", "minutes": 15, "intensity_1_5": 2}
                ],
                "calories_in": 2000,
                "water_liters": 3.0,
                "mood_1_5": 5,
                "notes": "excellent workout, feeling strong"
            },
            {
                "date": "2025-09-19",
                "sleep_hours": 6.5,
                "steps": 6200,
                "workouts": [],
                "calories_in": 1650,
                "water_liters": 2.2,
                "mood_1_5": 2,
                "notes": "stressful day, skipped lunch"
            }
        ]
    }

@app.post("/weekly-report")
async def weekly_report(payload: Dict[str, Any] = Body(...)):
    """
    🚀 **Main Feature**: Comprehensive health analysis using Sentient ROMA
    
    **How ROMA Works:**
    1. **Atomizer** analyzes your request complexity
    2. **Planner** breaks down complex analysis into specialized subtasks  
    3. **Executors** (specialized AI agents) handle each domain:
       - Data validation and normalization
       - Health metrics calculation  
       - Personalized coaching recommendations
       - Comprehensive report generation
    4. **Aggregator** combines all insights into a coherent final report
    
    **Expected Response Time:** 30-90 seconds for comprehensive analysis
    **AI Model Usage:** Multiple specialized agents work in parallel/sequence
    """
    if not roma_runner:
        raise HTTPException(
            status_code=503, 
            detail="ROMA engine unavailable - check system configuration"
        )
    
    try:
        print(f"📊 Processing ROMA health analysis for {len(payload.get('daily_logs', []))} days...")
        
        # Execute Sentient ROMA hierarchical analysis
        result = roma_runner.run(payload)
        
        # Add API metadata
        result["api_metadata"] = {
            "endpoint": "/weekly-report",
            "analysis_type": "comprehensive_roma_health_analysis", 
            "framework": "Sentient AGI ROMA v0.1 (Beta)"
        }
        
        print(f"✅ ROMA analysis completed: {result.get('status', 'unknown')}")
        return result
        
    except Exception as e:
        tb = traceback.format_exc()
        print(f"❌ ROMA analysis failed: {str(e)}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": f"ROMA analysis failed: {str(e)}",
                "status": "error",
                "roma_execution": "failed",
                "trace_tail": tb[-1500:],
                "troubleshooting": {
                    "check_data_format": "Ensure all required fields are provided",
                    "check_api_keys": "Verify AI API keys are configured in .env",
                    "check_logs": "Review server logs for detailed error information"
                }
            }
        )

@app.post("/analyze") 
async def analyze_single_entry(entry: HealthEntry = Body(...)):
    """
    Quick analysis of a single health entry using ROMA intelligence
    
    Converts simple health logs into structured analysis with AI insights.
    Less comprehensive than /weekly-report but faster for single-day analysis.
    """
    if not roma_runner:
        raise HTTPException(status_code=503, detail="ROMA engine unavailable")
    
    try:
        data = entry.model_dump(exclude_none=True)
        
        # Convert single entry to minimal analysis format
        daily_log = {
            "date": "2025-09-20",
            "sleep_hours": None,
            "steps": None,
            "workouts": [],
            "calories_in": None, 
            "water_liters": entry.water_intake_l,
            "mood_1_5": None,
            "notes": entry.notes or ""
        }
        
        # Parse sleep information
        if entry.sleep_log:
            try:
                import re
                hours_match = re.search(r'(\d+\.?\d*)', entry.sleep_log.replace('h', ''))
                if hours_match:
                    daily_log["sleep_hours"] = float(hours_match.group(1))
            except:
                daily_log["notes"] += f" Sleep: {entry.sleep_log}"
        
        # Parse exercise information
        if entry.exercise_log:
            import re
            
            # Default workout
            workout = {"type": "general", "minutes": 30, "intensity_1_5": 3}
            
            # Extract workout type
            exercise_lower = entry.exercise_log.lower()
            if any(word in exercise_lower for word in ["run", "jog", "cardio", "bike", "cycle"]):
                workout.update({"type": "cardio", "intensity_1_5": 4})
            elif any(word in exercise_lower for word in ["strength", "weight", "lift", "gym", "resistance"]):
                workout.update({"type": "strength", "intensity_1_5": 4})
            elif any(word in exercise_lower for word in ["yoga", "stretch", "pilates", "flexibility"]):
                workout.update({"type": "flexibility", "intensity_1_5": 2})
            elif any(word in exercise_lower for word in ["walk", "hike"]):
                workout.update({"type": "walking", "intensity_1_5": 3})
            elif any(word in exercise_lower for word in ["swim"]):
                workout.update({"type": "swimming", "intensity_1_5": 4})
            
            # Extract duration
            time_match = re.search(r'(\d+)\s*min', exercise_lower)
            if time_match:
                workout["minutes"] = int(time_match.group(1))
            
            daily_log["workouts"] = [workout]
        
        # Parse mood
        if entry.mood_log:
            mood_keywords = {
                1: ["terrible", "awful", "exhausted", "depressed", "horrible"],
                2: ["tired", "low", "stressed", "frustrated", "sad", "anxious"], 
                3: ["okay", "ok", "fine", "neutral", "alright", "decent"],
                4: ["good", "happy", "positive", "energetic", "motivated", "content"],
                5: ["great", "excellent", "amazing", "fantastic", "wonderful", "outstanding", "euphoric"]
            }
            
            mood_score = 3  # default neutral
            mood_lower = entry.mood_log.lower()
            
            for score, keywords in mood_keywords.items():
                if any(keyword in mood_lower for keyword in keywords):
                    mood_score = score
                    break
            
            daily_log["mood_1_5"] = mood_score
            daily_log["notes"] += f" Mood: {entry.mood_log}"
        
        # Create minimal payload for ROMA analysis
        minimal_payload = {
            "user_profile": {
                "age": 30,
                "sex": "U", 
                "height_cm": 170,
                "weight_kg": 70,
                "goal": "health maintenance and improvement",
                "constraints": "single day analysis"
            },
            "targets": {
                "sleep_h": 8,
                "steps": 8000,
                "workouts_per_week": 3,
                "calories_in": 2000,
                "water_liters": 2.5
            },
            "daily_logs": [daily_log]
        }
        
        print("🔍 Running ROMA analysis on single entry...")
        result = roma_runner.run(minimal_payload)
        
        # Create user-friendly analysis summary
        analysis_summary = {
            "input_parsing": {
                "logged_items": list(data.keys()),
                "extracted_data": {
                    "sleep": f"{daily_log['sleep_hours']}h" if daily_log['sleep_hours'] else "not specified",
                    "activity": daily_log['workouts'][0] if daily_log['workouts'] else "none logged",
                    "hydration": f"{daily_log['water_liters']}L" if daily_log['water_liters'] else "not specified", 
                    "mood": daily_log.get('mood_1_5', 'not specified'),
                    "notes": daily_log.get('notes', 'none')
                }
            },
            "roma_insights": {
                "health_score": result.get("health_score", 75),
                "key_recommendations": result.get("next_actions", ["Continue tracking daily health data"]),
                "motivation": result.get("coaching_recommendations", {}).get("motivation_message", "Every step towards health awareness counts!"),
                "analysis_summary": result.get("executive_summary", "Single day analysis completed")
            },
            "execution_info": {
                "roma_status": result.get("roma_execution", "completed"),
                "analysis_time": result.get("execution_metadata", {}).get("execution_time_seconds", "unknown"),
                "agents_used": result.get("agent_execution", {})
            }
        }
        
        return {"analysis": analysis_summary}
        
    except Exception as e:
        tb = traceback.format_exc()
        print(f"❌ Single entry analysis failed: {str(e)}")
        
        return {"analysis": {
            "error": str(e),
            "status": "error", 
            "trace_tail": tb[-800:],
            "fallback_message": "Unable to process entry with ROMA - check data format"
        }}

@app.post("/chat")
async def chat_with_coach(chat_request: ChatMessage = Body(...)):
    """
    Direct conversation with AI health coach using ROMA intelligence
    
    Unlike simple chatbots, this uses ROMA's hierarchical reasoning:
    - Atomizer determines if question is simple or complex
    - For complex questions, Planner breaks down into research subtasks
    - Specialized agents provide evidence-based responses
    - Aggregator creates coherent, personalized advice
    """
    if not roma_runner:
        raise HTTPException(status_code=503, detail="ROMA engine unavailable")
    
    try:
        user_message = chat_request.message
        context = chat_request.context or ""
        
        # Create a conversational task for ROMA
        chat_task = {
            "description": f"Health coaching conversation: {user_message}",
            "conversation_type": "health_coaching_chat",
            "user_message": user_message,
            "context": context,
            "response_format": "conversational"
        }
        
        print(f"💬 Processing ROMA chat request: '{user_message[:50]}...'")
        
        # Use ROMA's CoachingAgent directly for conversational responses
        from roma_agents.sentient_health_agents import CoachingAgent
        
        coach = CoachingAgent()
        
        coaching_prompt = f"""
        You are having a direct conversation with someone seeking health advice.
        
        Their message: "{user_message}"
        Context: {context if context else "No additional context provided"}
        
        Provide a helpful, conversational response that:
        1. Directly addresses their question or concern
        2. Offers practical, evidence-based advice
        3. Is encouraging and supportive in tone
        4. Includes 2-3 specific actionable tips
        5. Ends with a follow-up question to continue the conversation
        
        Be personal, warm, and professional. Avoid overly clinical language.
        
        Return JSON with:
        - response: your main conversational response
        - quick_tips: 2-3 immediate actionable suggestions
        - follow_up_question: engage them further
        - coach_insights: brief professional perspective
        """
        
        coach_result = coach.execute({
            "user_message": user_message,
            "context": context,
            "coaching_prompt": coaching_prompt
        })
        
        if coach_result.get("status") == "ok":
            coaching_data = coach_result.get("coaching", {})
            
            return {
                "status": "ok",
                "conversation": {
                    "user_message": user_message,
                    "coach_response": coaching_data.get("motivation_message", "I'm here to help with your health journey!"),
                    "quick_tips": coaching_data.get("daily_suggestions", ["Stay consistent with healthy habits"])[:3],
                    "follow_up_question": "What specific aspect of your health would you like to focus on next?",
                    "coach_insights": coaching_data.get("habit_recommendations", ["Focus on sustainable, small changes"])[:2]
                },
                "roma_metadata": {
                    "agent_used": "CoachingAgent",
                    "processing_type": "direct_coaching_conversation"
                }
            }
        else:
            # Fallback response
            return {
                "status": "ok",
                "conversation": {
                    "user_message": user_message,
                    "coach_response": f"Thank you for sharing that with me. {user_message} is definitely something we can work on together. Health is a journey, and every small step counts.",
                    "quick_tips": [
                        "Start with small, manageable changes",
                        "Track your progress to stay motivated", 
                        "Be patient and kind to yourself"
                    ],
                    "follow_up_question": "What's one small change you could make this week?",
                    "coach_insights": ["Consistency is more important than perfection", "Focus on building sustainable habits"]
                },
                "roma_metadata": {
                    "agent_used": "fallback",
                    "processing_type": "simple_response"
                }
            }
        
    except Exception as e:
        tb = traceback.format_exc()
        print(f"❌ Chat processing failed: {str(e)}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Chat processing failed: {str(e)}",
                "status": "error",
                "conversation": {
                    "user_message": chat_request.message,
                    "coach_response": "I apologize, but I'm having trouble processing your message right now. Please try again or rephrase your question.",
                    "quick_tips": ["Check your internet connection", "Try a simpler question", "Contact support if issues persist"],
                    "follow_up_question": "Is there anything else I can help you with?"
                },
                "trace_tail": tb[-800:]
            }
        )

@app.get("/test-roma")
async def test_roma_system():
    """
    Test endpoint to verify ROMA system functionality
    
    Runs a simple test through the full ROMA pipeline to ensure all components work.
    """
    if not roma_runner:
        raise HTTPException(status_code=503, detail="ROMA engine unavailable")
    
    # Simple test data
    test_payload = {
        "user_profile": {
            "age": 25,
            "sex": "M",
            "height_cm": 175,
            "weight_kg": 70, 
            "goal": "system test"
        },
        "targets": {
            "sleep_h": 8,
            "steps": 8000,
            "workouts_per_week": 3,
            "calories_in": 2200,
            "water_liters": 2.5
        },
        "daily_logs": [
            {
                "date": "2025-09-20",
                "sleep_hours": 7.5,
                "steps": 8500,
                "workouts": [{"type": "test", "minutes": 30, "intensity_1_5": 3}],
                "calories_in": 2100,
                "water_liters": 2.8,
                "mood_1_5": 4,
                "notes": "ROMA system test"
            }
        ]
    }
    
    try:
        print("🧪 Running ROMA system test...")
        start_time = time.time()
        
        result = roma_runner.run(test_payload)
        test_time = time.time() - start_time
        
        return {
            "test_status": "passed",
            "roma_execution": result.get("roma_execution", "unknown"),
            "test_duration_seconds": round(test_time, 2),
            "system_health": "operational",
            "agents_tested": result.get("agent_execution", {}),
            "framework_info": result.get("execution_metadata", {}),
            "sample_output": {
                "health_score": result.get("health_score", "not_calculated"),
                "executive_summary": result.get("executive_summary", "not_generated")[:100] + "..." if result.get("executive_summary") else "not_generated"
            }
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "test_status": "failed",
                "error": str(e),
                "system_health": "degraded",
                "troubleshooting": "Check AI API keys and agent configurations"
            }
        )

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    print("🚀 Sentient ROMA Health Tracker API starting up...")
    print(f"🤖 AI Provider: {ai_provider}")
    print(f"🔧 ROMA Status: {roma_status}")
    
    if roma_status == "active":
        print("✅ All systems ready for hierarchical health analysis!")
    else:
        print("⚠️  ROMA engine unavailable - check configuration")

# Shutdown event  
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🔄 Shutting down Sentient ROMA Health Tracker...")
    print("👋 Goodbye!")

if __name__ == "__main__":
    import uvicorn
    import time
    
    print("=" * 60)
    print("🚀 SENTIENT ROMA HEALTH TRACKER")
    print("=" * 60)
    print(f"🤖 Framework: Sentient AGI ROMA v0.1 (Beta)")
    print(f"🔧 AI Provider: {ai_provider}")
    print(f"🌐 API Documentation: http://127.0.0.1:8000/docs")
    print(f"📊 Example Payload: http://127.0.0.1:8000/example")
    print(f"🧪 System Test: http://127.0.0.1:8000/test-roma")
    print("=" * 60)
    
    if roma_status != "active":
        print("⚠️  WARNING: ROMA engine failed to initialize")
        print("   Check your AI API keys in .env file")
        print("   Some features may not be available")
        print()
    
    uvicorn.run(app, host="127.0.0.1", port=8000)
