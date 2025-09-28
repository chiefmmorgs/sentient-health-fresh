from __future__ import annotations
from typing import Any, Dict, List
import statistics

def _weekly_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    steps = raw.get("steps", 0)
    sleep_hours = raw.get("sleep_hours", 0)
    workouts = raw.get("workouts", 0)
    water_liters = raw.get("water_liters", 0.0)
    return {
        "steps": int(steps),
        "sleep_hours": float(sleep_hours),
        "workouts": int(workouts),
        "water_liters": float(water_liters),
    }

class DataIngestionExecutor:
    name = "health.ingest"
    description = "Validate & normalize raw health metrics."

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        data = task.get("data", {})
        if not isinstance(data, dict):
            raise ValueError("Expected 'data' to be an object with weekly values.")
        normalized = _weekly_summary(data)
        return {"normalized": normalized}

class MetricsAnalysisExecutor:
    name = "health.metrics"
    description = "Compute basic scores and summaries."

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        norm = task.get("normalized") or task.get("data")
        if not norm:
            raise ValueError("No normalized data provided to metrics executor.")
        steps = norm["steps"]
        sleep = norm["sleep_hours"]
        workouts = norm["workouts"]
        water = norm["water_liters"]

        step_target = 70000.0    # ~10k/day
        sleep_target = 56.0      # 8h/day
        workout_target = 4.0     # 4/week
        water_target = 14.0      # 2L/day

        step_score = min(100, int((steps / step_target) * 100)) if step_target else 0
        sleep_score = min(100, int((sleep / sleep_target) * 100)) if sleep_target else 0
        workout_score = min(100, int((workouts / workout_target) * 100)) if workout_target else 0
        hydration_score = min(100, int((water / water_target) * 100)) if water_target else 0
        total = int(statistics.mean([step_score, sleep_score, workout_score, hydration_score]))

        return {
            "scores": {
                "steps": step_score,
                "sleep": sleep_score,
                "workouts": workout_score,
                "hydration": hydration_score,
                "overall": total,
            },
            "normalized": norm,
        }

class CoachingExecutor:
    name = "health.coach"
    description = "Turn metrics into human-readable coaching tips."

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        scores = task.get("scores", {})
        norm = task.get("normalized", {})
        tips: List[str] = []
        if scores.get("steps", 0) < 80:
            tips.append("Aim for short walks after meals to increase daily steps.")
        if scores.get("sleep", 0) < 80:
            tips.append("Try a consistent bedtime and limit screens 60 minutes before sleep.")
        if scores.get("workouts", 0) < 80:
            tips.append("Schedule two 30–40 min strength sessions this week.")
        if scores.get("hydration", 0) < 80:
            tips.append("Keep a water bottle visible; sip regularly to reach ~2L/day.")
        if not tips:
            tips.append("Great week! Keep your current routine and consider a recovery day.")
        return {"coaching": tips, "scores": scores, "normalized": norm}

class WeeklyReportAggregator:
    name = "health.aggregate"
    description = "Aggregate metrics & coaching into a weekly report payload."

    async def aggregate(self, parts: Dict[str, Any]) -> Dict[str, Any]:
        scores = parts.get("scores", {})
        norm = parts.get("normalized", {})
        coaching = parts.get("coaching", [])
        report = {
            "week": norm,
            "scores": scores,
            "coaching": coaching,
            "summary": f"Overall score {scores.get('overall', 0)}/100.",
        }
        return {"report": report}
