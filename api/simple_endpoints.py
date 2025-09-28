"""
Simple API Endpoints - Fixed Version

Addresses the hanging and error issues with simple endpoints
"""

from fastapi import APIRouter, Body, HTTPException
from typing import Dict, Any, Optional
import asyncio
import time
from logging_config import get_logger

# Import fallback system
try:
    from llm_fallback import call_llm_with_fallback, get_fallback_status
    FALLBACK_AVAILABLE = True
except ImportError:
    FALLBACK_AVAILABLE = False

logger = get_logger(__name__)

# Create router for simple endpoints
simple_router = APIRouter(prefix="/api/simple", tags=["simple"])

@simple_router.get("/status")
async def simple_status():
    """Check simple API status"""
    status = {
        "simple_api": "active",
        "fallback_available": FALLBACK_AVAILABLE,
        "timestamp": time.time()
    }
    
    if FALLBACK_AVAILABLE:
        status["llm_fallback"] = get_fallback_status()
    
    return status

@simple_router.post("/execute")
async def simple_execute(
    prompt: str = Body(..., embed=True),
    timeout: Optional[int] = Body(30, embed=True)
):
    """
    Simple LLM execution with timeout protection
    
    Fixed version that prevents hanging
    """
    logger.info(f"Simple execute request: {prompt[:100]}...")
    
    if not FALLBACK_AVAILABLE:
        raise HTTPException(status_code=503, detail="LLM fallback system not available")
    
    try:
        # Add timeout protection
        start_time = time.time()
        
        # Use asyncio timeout to prevent hanging
        async def execute_with_timeout():
            loop = asyncio.get_event_loop()
            # Run LLM call in thread pool to avoid blocking
            result = await loop.run_in_executor(
                None, 
                call_llm_with_fallback,
                prompt,
                "You are a helpful AI assistant. Provide clear, concise responses."
            )
            return result
        
        # Execute with timeout
        result = await asyncio.wait_for(execute_with_timeout(), timeout=timeout)
        
        execution_time = time.time() - start_time
        
        logger.info(f"Simple execute completed in {execution_time:.2f}s")
        
        return {
            "result": result,
            "execution_time": execution_time,
            "status": "success"
        }
        
    except asyncio.TimeoutError:
        logger.warning(f"Simple execute timed out after {timeout}s")
        raise HTTPException(
            status_code=408, 
            detail=f"Request timed out after {timeout} seconds"
        )
    except Exception as e:
        logger.error(f"Simple execute failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

@simple_router.post("/analysis")
async def simple_analysis(
    data: Dict[str, Any] = Body(...),
    data_description: Optional[str] = Body(None, embed=True)
):
    """
    Simple data analysis with optional description
    
    Fixed version that handles missing data_description gracefully
    """
    logger.info("Simple analysis request received")
    
    if not FALLBACK_AVAILABLE:
        raise HTTPException(status_code=503, detail="LLM fallback system not available")
    
    # Handle missing data_description gracefully
    if not data_description:
        data_description = "general data analysis"
        logger.info("No data_description provided, using default")
    
    try:
        # Create analysis prompt
        prompt = f"""
        Analyze this data for {data_description}:
        
        Data: {data}
        
        Provide insights, patterns, and recommendations in a clear format.
        """
        
        system_prompt = "You are a data analyst. Provide clear, actionable insights from data."
        
        # Execute analysis with timeout
        start_time = time.time()
        
        async def analyze_with_timeout():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                call_llm_with_fallback,
                prompt,
                system_prompt
            )
            return result
        
        analysis_result = await asyncio.wait_for(analyze_with_timeout(), timeout=30)
        
        execution_time = time.time() - start_time
        
        return {
            "analysis": analysis_result,
            "data_description": data_description,
            "execution_time": execution_time,
            "status": "success"
        }
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Analysis timed out after 30 seconds")
    except Exception as e:
        logger.error(f"Simple analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@simple_router.post("/research")
async def simple_research(
    query: str = Body(..., embed=True),
    research_type: Optional[str] = Body("general", embed=True)
):
    """
    Simple research query
    
    Fixed version with proper error handling
    """
    logger.info(f"Simple research request: {query[:100]}...")
    
    if not FALLBACK_AVAILABLE:
        raise HTTPException(status_code=503, detail="LLM fallback system not available")
    
    try:
        # Create research prompt
        prompt = f"""
        Research query: {query}
        Research type: {research_type}
        
        Provide a comprehensive response with:
        1. Key findings
        2. Important considerations
        3. Recommendations or next steps
        
        Base your response on general knowledge and provide practical insights.
        """
        
        system_prompt = "You are a research assistant. Provide thorough, well-structured research responses."
        
        start_time = time.time()
        
        async def research_with_timeout():
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                call_llm_with_fallback,
                prompt,
                system_prompt
            )
            return result
        
        research_result = await asyncio.wait_for(research_with_timeout(), timeout=45)
        
        execution_time = time.time() - start_time
        
        return {
            "research_result": research_result,
            "query": query,
            "research_type": research_type,
            "execution_time": execution_time,
            "status": "success"
        }
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Research timed out after 45 seconds")
    except Exception as e:
        logger.error(f"Simple research failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Research failed: {str(e)}")

@simple_router.get("/test")
async def simple_test():
    """
    Simple test endpoint to verify functionality
    """
    logger.info("Simple test endpoint called")
    
    test_results = {
        "api_status": "active",
        "timestamp": time.time(),
        "fallback_available": FALLBACK_AVAILABLE
    }
    
    if FALLBACK_AVAILABLE:
        try:
            # Test LLM fallback with simple prompt
            test_prompt = "Say 'Hello from the simple API!' in exactly those words."
            result = call_llm_with_fallback(test_prompt, "", temperature=0.1)
            test_results["llm_test"] = "success"
            test_results["llm_response"] = result[:100] + "..." if len(result) > 100 else result
        except Exception as e:
            test_results["llm_test"] = "failed"
            test_results["llm_error"] = str(e)
    else:
        test_results["llm_test"] = "fallback_not_available"
    
    return test_results
