from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict

try:
    from roma_engine.sentient_roma_runner import solve as roma_solve
except Exception:
    roma_solve = None

app = FastAPI(title="Sentient Health Tracker (ROMA)")

class WeeklyData(BaseModel):
    data: Dict[str, Any]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/weekly-report")
async def weekly_report(payload: WeeklyData):
    if roma_solve is None:
        raise HTTPException(status_code=500, detail="ROMA runtime not available")
    try:
        result = await roma_solve("health_weekly_report", {"data": payload.data})
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/normalize")
async def normalize(payload: WeeklyData):
    if roma_solve is None:
        raise HTTPException(status_code=500, detail="ROMA runtime not available")
    return await roma_solve("health_weekly_report", {"data": payload.data})
