# roma_agents/research_agent.py
import requests
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ResearchAgent:
    """
    Health Research Agent that uses OpenDeepSearch microservice
    to find evidence-based medical information
    """
    
    def __init__(self):
        self.search_service_url = os.getenv("SEARCH_SERVICE_URL", "http://search:5001")
        self.name = "ResearchAgent"
        
    def is_service_available(self) -> bool:
        """Check if search service is available"""
        try:
            response = requests.get(f"{self.search_service_url}/health", timeout=5)
            return response.status_code == 200 and response.json().get("initialized", False)
        except:
            return False
    
    def search(self, query: str, deep_mode: bool = False) -> Dict[str, Any]:
        """
        Search for health information
        
        Args:
            query: The health question or topic
            deep_mode: Use deep search for complex queries
            
        Returns:
            Dict with search results
        """
        try:
            if not self.is_service_available():
                logger.warning("Search service not available, returning fallback")
                return {
                    "success": False,
                    "result": "Search service temporarily unavailable. Please consult healthcare professional.",
                    "fallback": True
                }
            
            response = requests.post(
                f"{self.search_service_url}/search",
                json={"query": query, "deep_mode": deep_mode},
                timeout=30 if not deep_mode else 60
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "result": data["result"],
                    "query": data["query"],
                    "mode": data["mode"],
                    "fallback": False
                }
            else:
                logger.error(f"Search failed: {response.status_code}")
                return {
                    "success": False,
                    "result": "Unable to retrieve information at this time.",
                    "fallback": True
                }
                
        except requests.Timeout:
            logger.error("Search request timed out")
            return {
                "success": False,
                "result": "Search timed out. Please try a simpler query.",
                "fallback": True
            }
        except Exception as e:
            logger.error(f"Research error: {e}")
            return {
                "success": False,
                "result": "Error conducting research. Please try again.",
                "fallback": True
            }
    
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute research task (ROMA framework compatible)
        
        Args:
            task: Task dict with 'query' and optional 'deep_mode'
            
        Returns:
            Execution result
        """
        query = task.get("query", "")
        deep_mode = task.get("deep_mode", False)
        
        if not query:
            return {
                "agent": self.name,
                "success": False,
                "result": "No query provided"
            }
        
        search_result = self.search(query, deep_mode)
        
        return {
            "agent": self.name,
            "success": search_result["success"],
            "result": search_result["result"],
            "query": query,
            "mode": search_result.get("mode", "unknown"),
            "fallback_used": search_result.get("fallback", False)
        }

if __name__ == "__main__":
    agent = ResearchAgent()
    result = agent.execute({
        "query": "What are the health benefits of drinking water?",
        "deep_mode": False
    })
    print(result)
