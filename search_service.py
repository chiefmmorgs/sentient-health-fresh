# search_service.py
from cache_manager import search_cache
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from opendeepsearch import OpenDeepSearchTool
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Health Search Service")

# Initialize OpenDeepSearch
search_agent = None

class SearchRequest(BaseModel):
    query: str
    deep_mode: bool = False  # False = quick, True = deep search

class SearchResponse(BaseModel):
    query: str
    result: str
    sources: list = []
    mode: str

@app.on_event("startup")
async def startup_event():
    """Initialize OpenDeepSearch on startup"""
    global search_agent
    
    try:
        logger.info("Initializing OpenDeepSearch...")
        
        # Check for required API keys
        if not os.getenv("SERPER_API_KEY"):
            logger.error("SERPER_API_KEY not found in environment")
            raise ValueError("Missing SERPER_API_KEY")
        
        if not os.getenv("JINA_API_KEY"):
            logger.error("JINA_API_KEY not found in environment")
            raise ValueError("Missing JINA_API_KEY")
        
        # Initialize with health-focused settings
        search_agent = OpenDeepSearchTool(
            model_name="openrouter/google/gemini-2.0-flash-001",
            reranker="jina",
            search_provider="serper"
        )
        
        if not search_agent.is_initialized:
            search_agent.setup()
        
        logger.info("OpenDeepSearch initialized successfully!")
        
    except Exception as e:
        logger.error(f"Failed to initialize OpenDeepSearch: {e}")
        search_agent = None

@app.get("/health")
async def health_check():
    """Check if search service is ready"""
    return {
        "status": "healthy" if search_agent else "initializing",
        "service": "OpenDeepSearch Health Service",
        "initialized": search_agent is not None
    }

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Perform health-related search with caching
    """
    if not search_agent:
        raise HTTPException(
            status_code=503, 
            detail="Search service not initialized. Check API keys."
        )
    
    try:
        # Check cache first
        cached_result = search_cache.get(request.query, request.deep_mode)
        if cached_result:
            logger.info(f"Cache hit for: {request.query}")
            return SearchResponse(**cached_result)
        
        logger.info(f"Cache miss, searching: {request.query} (deep_mode={request.deep_mode})")
        
        # Add health context to query for better results
        enhanced_query = f"{request.query} site:nih.gov OR site:who.int OR site:mayoclinic.org OR site:cdc.gov OR site:ncbi.nlm.nih.gov"
        
        # Perform search
        result = search_agent.forward(
            enhanced_query if not request.deep_mode else request.query
        )
        
        response_data = {
            "query": request.query,
            "result": result,
            "sources": [],
            "mode": "deep" if request.deep_mode else "quick"
        }
        
        # Cache the result
        search_cache.set(request.query, response_data, request.deep_mode)
        
        return SearchResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/info")
async def service_info():
    """Get information about the search service"""
    return {
        "service": "OpenDeepSearch Health Service",
        "version": "1.0.0",
        "description": "Medical information search powered by OpenDeepSearch",
        "modes": {
            "quick": "Fast search for simple queries",
            "deep": "Comprehensive search for complex medical questions"
        },
        "trusted_sources": [
            "NIH (National Institutes of Health)",
            "WHO (World Health Organization)",
            "CDC (Centers for Disease Control)",
            "Mayo Clinic",
            "PubMed/NCBI"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)

@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    return search_cache.get_stats()

@app.post("/cache/clear")
async def clear_cache():
    """Clear the search cache"""
    search_cache.clear()
    return {"status": "success", "message": "Cache cleared"}
