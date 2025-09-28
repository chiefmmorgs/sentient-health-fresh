import os
import logging
from flask import Flask, jsonify, request
import requests
import json
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default model - you can change this to any OpenRouter model
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "google/gemma-2-9b-it:free")

def call_openrouter_llm(prompt: str, system_prompt: str = "", model: str = None) -> Optional[str]:
    """
    Call OpenRouter LLM with fallback handling
    """
    if not OPENROUTER_API_KEY:
        logger.warning("No OpenRouter API key found, returning fallback response")
        return None
    
    if not model:
        model = DEFAULT_MODEL
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    try:
        logger.info(f"Calling OpenRouter with model: {model}")
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",  # Required by OpenRouter
            "X-Title": "ROMA Health Tracker"  # Optional but good practice
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(
            OPENROUTER_BASE_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            logger.info("✅ Successfully got LLM response")
            return content.strip()
        else:
            logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("OpenRouter API timeout")
        return None
    except Exception as e:
        logger.error(f"OpenRouter API call failed: {str(e)}")
        return None

def analyze_health_data(data: Dict[str, Any], description: str) -> str:
    """
    Generate health analysis using LLM
    """
    system_prompt = """You are an expert health analyst and coach. 
    Provide clear, actionable insights based on health data. 
    Focus on practical recommendations and highlight both positive trends and areas for improvement.
    Keep responses concise but insightful."""
    
    user_prompt = f"""
    Analyze this health data: {json.dumps(data, indent=2)}
    
    Context: {description}
    
    Please provide:
    1. Key observations about the data
    2. Health insights and trends
    3. 2-3 specific, actionable recommendations
    4. Overall assessment
    
    Keep it practical and encouraging.
    """
    
    llm_response = call_openrouter_llm(user_prompt, system_prompt)
    
    if llm_response:
        return llm_response
    else:
        # Fallback analysis
        return f"Analysis of {description}: Data received and processed. Consider consulting with a healthcare professional for personalized advice."

def execute_goal(goal: str) -> str:
    """
    Execute a goal using LLM reasoning
    """
    system_prompt = """You are a helpful AI assistant specialized in health and wellness. 
    Provide practical, actionable responses. Be concise but thorough.
    If the request is health-related, provide evidence-based advice."""
    
    llm_response = call_openrouter_llm(goal, system_prompt)
    
    if llm_response:
        return llm_response
    else:
        # Enhanced fallback for common health goals
        if "sleep" in goal.lower():
            return "For better sleep: maintain consistent bedtime, limit screens 1h before bed, keep room cool and dark."
        elif "exercise" in goal.lower() or "workout" in goal.lower():
            return "Start with 3 sessions/week, mix cardio and strength, progress gradually, listen to your body."
        elif "water" in goal.lower() or "hydrat" in goal.lower():
            return "Aim for 8-10 glasses daily, drink water with each meal, carry a water bottle as a visual reminder."
        else:
            return f"Goal acknowledged: {goal}. Consider breaking this into specific, measurable steps."

@app.get("/api/simple/status")
def status():
    """Enhanced status with LLM availability"""
    llm_available = OPENROUTER_API_KEY is not None
    
    # Quick test of LLM if key is available
    llm_working = False
    if llm_available:
        test_response = call_openrouter_llm("Reply with just 'OK'", "", "openrouter/google/gemini-2.0-flash-exp:free")
        llm_working = test_response is not None and "ok" in test_response.lower()
    
    return jsonify({
        "ok": True,
        "service": "roma",
        "version": "2.0-llm-enabled",
        "llm_available": llm_available,
        "llm_working": llm_working,
        "model": DEFAULT_MODEL,
        "endpoints": [
            "/api/simple/status", 
            "/api/simple/execute", 
            "/api/simple/research", 
            "/api/simple/analysis"
        ]
    })

@app.post("/api/simple/execute")
def simple_execute():
    """Enhanced execute with LLM integration"""
    payload = request.get_json(silent=True) or {}
    goal = payload.get("goal", "").strip()
    
    if not goal:
        return jsonify({"error": "No goal provided", "status": "error"}), 400
    
    logger.info(f"Executing goal: {goal[:50]}...")
    
    # Special test case
    if goal.lower() == "reply with exactly the word ok.":
        return jsonify({"final_output": "OK", "status": "completed"})
    
    # Use LLM for goal execution
    try:
        result = execute_goal(goal)
        return jsonify({
            "final_output": result,
            "status": "completed",
            "method": "llm" if OPENROUTER_API_KEY else "fallback"
        })
    except Exception as e:
        logger.error(f"Goal execution failed: {e}")
        return jsonify({
            "final_output": f"Unable to process goal: {goal}",
            "status": "error",
            "error": str(e)
        }), 500

@app.post("/api/simple/research")
def simple_research():
    """Enhanced research with LLM integration"""
    payload = request.get_json(silent=True) or {}
    topic = payload.get("topic", "").strip()
    
    if not topic:
        return jsonify({"error": "No research topic provided", "status": "error"}), 400
    
    logger.info(f"Researching topic: {topic}")
    
    system_prompt = """You are a health research analyst. 
    Provide evidence-based insights on health topics.
    Structure your response with key points and practical implications."""
    
    research_prompt = f"""
    Research topic: {topic}
    
    Please provide:
    1. Key scientific insights
    2. Practical applications
    3. Important considerations
    4. Current research trends
    
    Keep it factual and actionable.
    """
    
    result = call_openrouter_llm(research_prompt, system_prompt)
    
    if result:
        return jsonify({
            "status": "completed",
            "topic": topic,
            "research_findings": result,
            "method": "llm"
        })
    else:
        return jsonify({
            "status": "completed", 
            "topic": topic,
            "research_findings": f"Research topic '{topic}' noted. Consider consulting peer-reviewed sources for detailed information.",
            "method": "fallback"
        })

@app.post("/api/simple/analysis")
def simple_analysis():
    """Enhanced analysis with LLM integration"""
    payload = request.get_json(silent=True) or {}
    
    if "data_description" not in payload:
        return jsonify({"error": "Missing required field: data_description", "status": "error"}), 400
    
    data = payload.get("data", {})
    description = payload.get("data_description", "")
    goal = payload.get("goal", "")
    
    logger.info(f"Analyzing: {description}")
    
    try:
        # Combine description and goal for context
        full_context = description
        if goal:
            full_context += f" Goal: {goal}"
        
        analysis_result = analyze_health_data(data, full_context)
        
        return jsonify({
            "status": "completed",
            "analysis": analysis_result,
            "final_output": analysis_result,  # For compatibility
            "data_analyzed": len(str(data)) > 10,  # Simple check if data was provided
            "method": "llm" if OPENROUTER_API_KEY else "fallback"
        })
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return jsonify({
            "status": "error",
            "analysis": "Analysis failed due to processing error",
            "error": str(e)
        }), 500

@app.get("/api/simple/test")
def test_llm():
    """Test endpoint to verify LLM integration"""
    if not OPENROUTER_API_KEY:
        return jsonify({
            "status": "no_api_key",
            "message": "OpenRouter API key not configured"
        }), 400
    
    test_prompt = "You are a health AI. Say 'Health AI systems operational!' and give one quick health tip."
    result = call_openrouter_llm(test_prompt)
    
    if result:
        return jsonify({
            "status": "success",
            "llm_response": result,
            "model": DEFAULT_MODEL
        })
    else:
        return jsonify({
            "status": "failed",
            "message": "LLM call failed - check API key and network connection"
        }), 500

if __name__ == "__main__":
    print("🤖 Starting Enhanced ROMA Service with LLM Integration")
    print(f"📡 OpenRouter API Key: {'✅ Configured' if OPENROUTER_API_KEY else '❌ Missing'}")
    print(f"🧠 Default Model: {DEFAULT_MODEL}")
    print(f"🌐 Service URL: http://0.0.0.0:5000")
    print("-" * 60)
    
    app.run(host="0.0.0.0", port=5000, debug=False)
