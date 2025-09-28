# migration/hybrid_transition.py
import os
from typing import Dict, Any
from roma_bridge.roma_config import RomaBridge

class LegacyRomaRunner:
    async def execute_task(self, task_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "legacy_ok", "task_type": task_type, "data": data}

class HybridTransition:
    def __init__(self):
        self.use_roma = os.getenv("USE_ROMA_FRAMEWORK", "false").lower() == "true"
        self.legacy_runner = LegacyRomaRunner()
        self.roma_bridge = RomaBridge()

    async def execute_task(self, task_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if self.use_roma:
            return await self.roma_bridge.execute_health_task(task_type, data)
        else:
            return await self.legacy_runner.execute_task(task_type, data)

