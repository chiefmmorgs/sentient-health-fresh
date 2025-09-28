import os
from typing import Dict, Any
from agents.roma_health_agents import (
    validate_health_data, normalize_data,
    calc_activity_score, calc_sleep_score, calc_hydration_score
)

class RomaBridge:
    """
    Temporary fallback bridge that mimics ROMA flows locally.
    Keeps the same execute_health_task() signature so we can
    swap in the real ROMA call once we confirm the export name.
    """
    def __init__(self):
        self.config_path = os.getenv("ROMA_CONFIG_PATH", "./roma_config/health_agents.yaml")
        self.model_id = os.getenv("DEFAULT_MODEL", "openrouter/deepseek/deepseek-chat-v3.1:free")
        self.api_key = os.getenv("OPENROUTER_API_KEY")

    async def execute_health_task(self, task_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        v = validate_health_data(data or {})
        n = normalize_data(v)

        if task_type == "quick_analysis":
            activity = calc_activity_score(n["steps"], n["workouts"])
            sleep = calc_sleep_score(n["sleep_hours"])
            hydration = calc_hydration_score(n["water_liters"])
            overall = round((activity + sleep + hydration) / 3.0, 1)
            return {
                "status": "success",
                "agent": "metrics_analysis(local)",
                "metrics": {
                    "activity_score": activity,
                    "sleep_score": sleep,
                    "hydration_score": hydration,
                    "overall_score": overall
                },
                "insights": {
                    "activity": "Keep steps near 10k and 2–4 workouts/week.",
                    "sleep": "Aim for ~7.5h; keep a consistent bedtime.",
                    "hydration": "Target ~2.5L daily, spread through the day."
                }
            }

        if task_type == "coaching_session":
            return {
                "status": "success",
                "agent": "coaching(local)",
                "coaching": [
                    "Walk 20–30 minutes after lunch today.",
                    "Lights out by 11pm; no screens 30 minutes before.",
                    "Fill a 1L bottle and finish it twice by 6pm."
                ]
            }

        if task_type == "weekly_health_analysis":
            activity = calc_activity_score(n["steps"], n["workouts"])
            sleep = calc_sleep_score(n["sleep_hours"])
            hydration = calc_hydration_score(n["water_liters"])
            overall = round((activity + sleep + hydration) / 3.0, 1)
            return {
                "status": "success",
                "agent": "reporting(local)",
                "report": {
                    "trends": {
                        "activity_score": activity,
                        "sleep_score": sleep,
                        "hydration_score": hydration,
                        "overall_score": overall
                    },
                    "wins": [
                        "Consistent steps this week",
                        "Kept sleep near the optimal window"
                    ],
                    "risks": [
                        "Hydration slightly off the 2.5L target on 2 days"
                    ],
                    "next_steps": [
                        "Two focused workouts, 45 minutes each",
                        "Bedtime alarm 30 minutes before lights out",
                        "1 glass of water with each meal"
                    ]
                }
            }

        return {"status": "error", "detail": f"Unknown task_type '{task_type}'"}
