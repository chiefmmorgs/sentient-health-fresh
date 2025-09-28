from typing import Dict, Any

# ---- Validation & normalization ----
def validate_health_data(data: Dict[str, Any]) -> Dict[str, Any]:
    clean = {}
    # accept ints/floats/strings that look numeric, default to 0
    def to_float(x, default=0.0):
        try:
            if x is None: return default
            if isinstance(x, (int, float)): return float(x)
            return float(str(x).strip())
        except Exception:
            return default

    clean["steps"] = int(to_float(data.get("steps", 0), 0))
    clean["sleep_hours"] = to_float(data.get("sleep_hours", 0.0), 0.0)
    clean["workouts"] = int(to_float(data.get("workouts", 0), 0))
    clean["water_liters"] = to_float(data.get("water_liters", 0.0), 0.0)
    return clean

def normalize_data(data: Dict[str, Any]) -> Dict[str, Any]:
    n = dict(data)
    # clamp to sensible ranges
    n["steps"] = max(0, min(50000, int(n.get("steps", 0))))
    n["sleep_hours"] = max(0.0, min(24.0, float(n.get("sleep_hours", 0.0))))
    n["workouts"] = max(0, min(21, int(n.get("workouts", 0))))
    n["water_liters"] = max(0.0, min(10.0, float(n.get("water_liters", 0.0))))
    return n

# ---- Scoring helpers (0–100) ----
def _scale(value: float, target: float, max_value: float) -> float:
    if max_value <= 0: return 0.0
    ratio = min(value / target, 1.0)
    # smooth cap toward target, allow small bonus if above target (up to +10%)
    score = ratio * 100.0
    if value > target:
        bonus = min((value - target) / max_value, 0.1) * 100.0
        score = min(100.0, score + bonus)
    return round(score, 1)

def calc_activity_score(steps: int, workouts: int) -> float:
    # 10k steps target, 3 workouts target; 30k max considered for bonus
    steps_score = _scale(float(steps), 10000.0, 30000.0)
    wkt_score = _scale(float(workouts), 3.0, 10.0)
    return round(0.7 * steps_score + 0.3 * wkt_score, 1)

def calc_sleep_score(sleep_hours: float) -> float:
    # ideal 7.5h; penalize distance from 7.5 within [0,12]
    ideal = 7.5
    max_dev = 4.5  # from 7.5 to 3.0 or 12.0
    deviation = min(abs(sleep_hours - ideal), max_dev)
    score = (1.0 - deviation / max_dev) * 100.0
    return round(max(0.0, min(100.0, score)), 1)

def calc_hydration_score(water_liters: float) -> float:
    # target 2.5L, bonus up to 3.5L
    return _scale(water_liters, 2.5, 3.5)
