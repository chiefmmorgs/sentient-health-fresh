from __future__ import annotations
from typing import Any, Dict
import importlib

def _load_registry() -> Dict[str, Any]:
    mapping = {
        "health.ingest": "roma_agents.health_executors:DataIngestionExecutor",
        "health.metrics": "roma_agents.health_executors:MetricsAnalysisExecutor",
        "health.coach": "roma_agents.health_executors:CoachingExecutor",
        "health.aggregate": "roma_agents.health_executors:WeeklyReportAggregator",
    }
    resolved: Dict[str, Any] = {}
    for key, target in mapping.items():
        mod_name, cls_name = target.split(":")
        mod = importlib.import_module(mod_name)
        resolved[key] = getattr(mod, cls_name)
    return resolved

async def solve(skill: str, task: Dict[str, Any]) -> Dict[str, Any]:
    if skill != "health_weekly_report":
        raise ValueError(f"Unknown skill: {skill}")
    reg = _load_registry()

    # Atomizer heuristic
    if "data" in task and isinstance(task["data"], dict) and task["data"].get("week"):
        mode = "plan"
    else:
        mode = "execute:health.ingest"

    state: Dict[str, Any] = dict(task)

    if mode == "plan":
        ingest = reg["health.ingest"]()
        state.update(await ingest.execute(state))
        metrics = reg["health.metrics"]()
        state.update(await metrics.execute(state))
        coach = reg["health.coach"]()
        state.update(await coach.execute(state))
        agg = reg["health.aggregate"]()
        result = await agg.aggregate(state)
        return result
    else:
        _, ref = mode.split(":")
        exe = reg[ref]()
        return await exe.execute(state)
