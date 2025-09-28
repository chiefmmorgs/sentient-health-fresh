"""
Sentient ROMA Health Tracker - Main API Application
Properly organized with correct imports and initialization order
"""

# Core imports
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, Optional
import os
import time

# Setup logging first
from logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)

# Import ROMA engine
try:
    from roma_engine.sentient_roma_runner import ROMARunner
    roma_runner = ROMARunner()
    roma_status = "active"
    logger.info("✅ ROMA engine loaded successfully")
except Exception as e:
    roma_runner = None
    roma_status = "failed"
    logger.error(f"❌ ROMA engine failed to load: {e}")

# Import simple API endpoints
try:
    from api.simple_endpoints import simple_router
    SIMPLE_API_AVAILABLE = True
    logger.info("✅ Simple API endpoints available")
except ImportError as e:
    SIMPLE_API_AVAILABLE = False
    logger.warning(f"⚠️  Simple API endpoints not available: {e}")

# Initialize FastAPI app
app = FastAPI(
    title="Sentient ROMA Health Tracker",
    version="1.0.0",
    description="Advanced health analysis using Sentient AGI ROMA framework with LLM fallback support"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include simple API router if available
if SIMPLE_API_AVAILABLE:
    app.include_router(simple_router)
    logger.info("✅ Simple API endpoints included")

# Pydantic models
class WeeklyData(BaseModel):
    data: Dict[str, Any]

class HealthEntry(BaseModel):
    steps: Optional[int] = None
    sleep_hours: Optional[float] = None
    workouts: Optional[int] = None
    water_liters: Optional[float] = None
    notes: Optional[str] = None

class ChatMessage(BaseModel):
    message: str
    context: Optional[str] = None

# Main API endpoints
@app.get("/")
def root():
    """System information and status"""
    return {
        "service": "Sentient ROMA Health Tracker",
        "version": "1.0.0",
        "status": "🤖 Multi-agent health analysis system",
        "roma_status": roma_status,
        "simple_api": SIMPLE_API_AVAILABLE,
        "endpoints": {
            "main": ["/", "/health", "/weekly-report", "/analyze", "/chat", "/roma-info"],
            "simple": ["/api/simple/execute", "/api/simple/analysis", "/api/simple/research"] if SIMPLE_API_AVAILABLE else [],
            "docs": "/docs"
        }
    }

@app.get("/health")
def health():
    """System health check"""
    return {
        "status": "healthy" if roma_status == "active" else "degraded",
        "roma_engine": roma_status,
        "simple_api": "available" if SIMPLE_API_AVAILABLE else "unavailable",
        "timestamp": time.time()
    }

@app.get("/roma-info")
def roma_info():
    """ROMA system architecture information"""
    if roma_runner is None:
        raise HTTPException(status_code=503, detail="ROMA engine not available")
    
    return roma_runner.get_system_info()

@app.post("/weekly-report")
async def weekly_report(payload: WeeklyData):
    """
    Comprehensive weekly health analysis using ROMA
    
    Uses hierarchical multi-agent system for deep health insights
    """
    if roma_runner is None:
        raise HTTPException(status_code=503, detail="ROMA engine not available")
    
    logger.info("Processing weekly report with ROMA")
    
    try:
        start_time = time.time()
        result = roma_runner.run_weekly(payload.data)
        execution_time = time.time() - start_time
        
        # Add execution metadata
        if isinstance(result, dict):
            result["api_metadata"] = {
                "endpoint": "/weekly-report",
                "execution_time": execution_time,
                "roma_pattern": "hierarchical_decomposition"
            }
        
        logger.info(f"Weekly report completed in {execution_time:.2f}s")
        return {"report": result}
        
    except Exception as e:
        logger.error(f"Weekly report failed: {e}")
        raise HTTPException(status_code=500, detail=f"ROMA analysis failed: {str(e)}")

@app.post("/analyze")
async def analyze(entry: HealthEntry):
    """
    Quick single-entry health analysis
    
    Lightweight analysis for daily health tracking
    """
    if roma_runner is None:
        raise HTTPException(status_code=503, detail="ROMA engine not available")
    
    logger.info("Processing single entry analysis")
    
    try:
        # Convert HealthEntry to dict
        entry_data = entry.dict(exclude_none=True)
        
        result = roma_runner.analyze_single(entry_data)
        
        return {
            "analysis": result,
            "roma_pattern": "single_entry_analysis"
        }
        
    except Exception as e:
        logger.error(f"Single entry analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/chat")
async def chat(message: ChatMessage):
    """
    Chat with AI health coach
    
    Interactive health coaching using ROMA intelligence
    """
    if roma_runner is None:
        raise HTTPException(status_code=503, detail="ROMA engine not available")
    
    logger.info(f"Processing health coach chat: {message.message[:50]}...")
    
    try:
        chat_data = {
            "message": message.message,
            "context": message.context or ""
        }
        
        result = roma_runner.chat(chat_data)
        
        return {
            "chat_response": result,
            "roma_pattern": "health_coaching"
        }
        
    except Exception as e:
        logger.error(f"Health chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@app.post("/normalize")
async def normalize(payload: WeeklyData):
    """
    Normalize health data using ROMA data ingestion agent
    
    Validates and standardizes health data format
    """
    if roma_runner is None:
        raise HTTPException(status_code=503, detail="ROMA engine not available")
    
    logger.info("Processing data normalization")
    
    try:
        # Use ROMA's data ingestion agent for normalization
        from roma_agents.sentient_health_agents import DataIngestionAgent
        
        ingestion_agent = DataIngestionAgent()
        result = ingestion_agent.run({"data": payload.data})
        
        return {
            "normalized_data": result.get("normalized_data", {}),
            "validation_summary": result.get("validation_summary", {}),
            "warnings": result.get("warnings", []),
            "status": result.get("ok", False)
        }
        
    except Exception as e:
        logger.error(f"Data normalization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Normalization failed: {str(e)}")

@app.get("/example")
def example():
    """Example payload for testing"""
    return {
        "steps": 72000,
        "sleep_hours": 49,
        "workouts": 4,
        "water_liters": 14,
        "description": "Weekly health data example"
    }

@app.get("/api/status")
def api_status():
    """Complete API status including all subsystems"""
    return {
        "main_api": "active",
        "roma_engine": roma_status,
        "simple_api": SIMPLE_API_AVAILABLE,
        "components": {
            "roma_runner": roma_runner is not None,
            "fallback_llm": SIMPLE_API_AVAILABLE,
            "logging": True,
            "cors": True
        },
        "endpoints": {
            "main": [
                "/", "/health", "/weekly-report", "/analyze", 
                "/chat", "/roma-info", "/normalize", "/example"
            ],
            "simple": [
                "/api/simple/execute", "/api/simple/analysis", 
                "/api/simple/research", "/api/simple/test"
            ] if SIMPLE_API_AVAILABLE else [],
            "docs": ["/docs", "/redoc"]
        },
        "system_info": {
            "roma_max_depth": roma_runner.max_depth if roma_runner else None,
            "agents_available": 4 if roma_runner else 0
        }
    }

@app.get("/test-roma")
async def test_roma():
    """Test ROMA system functionality"""
    if roma_runner is None:
        raise HTTPException(status_code=503, detail="ROMA engine not available")
    
    logger.info("Running ROMA system test")
    
    test_data = {
        "steps": 8000,
        "sleep_hours": 7.5,
        "workouts": 1,
        "water_liters": 2.5
    }
    
    try:
        start_time = time.time()
        result = roma_runner.run_weekly(test_data)
        test_time = time.time() - start_time
        
        return {
            "test_status": "✅ PASSED",
            "roma_execution": result.get("roma_execution", "unknown"),
            "test_duration_seconds": round(test_time, 2),
            "health_score": result.get("summary", {}).get("health_score", "not_calculated"),
            "agents_executed": result.get("agent_execution", {}),
            "system_health": "operational"
        }
        
    except Exception as e:
        logger.error(f"ROMA test failed: {e}")
        return {
            "test_status": "❌ FAILED",
            "error": str(e),
            "system_health": "degraded"
        }

# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup"""
    logger.info("🚀 Sentient ROMA Health Tracker starting up...")
    logger.info(f"📊 ROMA Status: {roma_status}")
    logger.info(f"🔧 Simple API: {'Available' if SIMPLE_API_AVAILABLE else 'Unavailable'}")
    
    if roma_status == "active":
        logger.info("✅ All systems ready for health analysis!")
    else:
        logger.warning("⚠️  ROMA engine unavailable - limited functionality")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown"""
    logger.info("🔄 Shutting down Sentient ROMA Health Tracker...")

# Main execution
if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🤖 SENTIENT ROMA HEALTH TRACKER")
    print("=" * 60)
    print(f"🔧 ROMA Status: {roma_status}")
    print(f"🌐 API Docs: http://127.0.0.1:8000/docs")
    print(f"🧪 Test Endpoint: http://127.0.0.1:8000/test-roma")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=True
    )
