from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx, os, logging, json

# ----------------- App setup -----------------
log = logging.getLogger("health")
app = FastAPI(title="Health Tracker")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Serve a lightweight UI if you have static/index.html
if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

ROMA_BASE = os.getenv("ROMA_URL", "http://roma:5000") + "/api/simple"

# Optional API key (protect /health and /reports, and you can enable for others)
API_KEY = os.getenv("API_KEY", "")  # set in .env to activate protection

def require_api_key(x_api_key: str = Header(default=None, alias="X-API-Key")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

# ----------------- DB (SQLite via SQLAlchemy) -----------------
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session

DB_URL = os.getenv("DB_URL", "sqlite:///./health.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class ReportDB(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    kind = Column(String(50), index=True)               # "weekly", "analyze", "chat", etc.
    input_json = Column(Text, nullable=True)            # raw input
    output_text = Column(Text, nullable=True)           # narrative/text
    metrics_json = Column(Text, nullable=True)          # computed metrics JSON

Base.metadata.create_all(bind=engine)

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- Schemas -----------------
class HealthData(BaseModel):
    data: Dict[str, Any]

class ChatMessage(BaseModel):
    message: str
    save: Optional[bool] = False  # save chat as a report?

# ----------------- ROMA helpers -----------------
def _bad(text: Optional[str]) -> bool:
    if not isinstance(text, str):
        return True
    t = text.strip().lower()
    return (t == "" or t.startswith("echo:") or t == "placeholder" or t == "ok")

async def _roma_analysis(data: Dict[str, Any], desc: str, goal: Optional[str] = None) -> Optional[str]:
    payload: Dict[str, Any] = {"data": data, "data_description": desc}
    if goal:
        payload["goal"] = goal
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{ROMA_BASE}/analysis", json=payload)
            if r.status_code == 200:
                js = r.json()
                if isinstance(js, dict):
                    out = js.get("final_output") or js.get("analysis") or js.get("summary")
                    if isinstance(out, str) and not _bad(out):
                        return out
                    if out and not isinstance(out, str):
                        return str(out)
    except Exception as e:
        log.debug(f"/analysis failed: {e}")
    return None

async def _roma_execute(goal: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{ROMA_BASE}/execute", json={"goal": goal})
            if r.status_code == 200:
                js = r.json()
                out = js.get("final_output")
                if isinstance(out, str) and not _bad(out):
                    return out
    except Exception as e:
        log.debug(f"/execute failed: {e}")
    return None

# ----------------- Local analysis helpers -----------------
def analyze_health_locally(d: dict) -> dict:
    """Return structured insights for typical metrics."""
    out = {"insights": [], "flags": [], "summary": {}}

    # Resting heart rate (rHR)
    rhr = d.get("resting_hr")
    if isinstance(rhr, (int, float)):
        if rhr < 50:
            out["insights"].append("Very low resting HR; could be athletic or bradycardia—interpret in context.")
        elif 50 <= rhr <= 60:
            out["insights"].append("Excellent resting HR (well-trained range).")
        elif 61 <= rhr <= 70:
            out["insights"].append("Good resting HR.")
        elif 71 <= rhr <= 80:
            out["insights"].append("Slightly elevated resting HR—watch stress, sleep, hydration.")
        else:
            out["insights"].append("High resting HR—consider recovery, hydration, or check with a clinician if persistent.")
            out["flags"].append("resting_hr_high")
        out["summary"]["resting_hr"] = rhr

    # HRV
    hrv = d.get("hrv")
    if isinstance(hrv, (int, float)):
        if hrv >= 70:
            out["insights"].append("HRV looks strong—good recovery signal.")
        elif 50 <= hrv < 70:
            out["insights"].append("HRV is moderate—keep sleep and stress in check.")
        else:
            out["insights"].append("Low HRV—prioritize sleep, light activity, and hydration.")
            out["flags"].append("hrv_low")
        out["summary"]["hrv"] = hrv

    # Calories
    cals = d.get("calories")
    if isinstance(cals, (int, float)):
        out["summary"]["calories_week"] = cals
        if cals < 10000:
            out["insights"].append("Weekly calorie burn seems low—more daily movement or longer sessions could help.")
            out["flags"].append("calories_low")

    # Runs
    runs = d.get("runs")
    if isinstance(runs, (int, float)):
        runs = int(runs)
        out["summary"]["runs"] = runs
        if runs >= 3:
            out["insights"].append("Great running frequency—maintain 1 easy + 1 quality + 1 long structure.")
        else:
            out["insights"].append("Consider aiming for 3 runs/week (easy, quality, long).")
            out["flags"].append("runs_low")

    # Score: reward positives, penalize flags
    positives = 0
    if isinstance(rhr, (int, float)) and 50 <= rhr <= 60:
        positives += 1
    if isinstance(hrv, (int, float)) and hrv >= 70:
        positives += 1
    if isinstance(runs, int) and runs >= 3:
        positives += 1
    score = 70 + 5 * positives - 10 * len(out["flags"])
    score = max(0, min(100, score))
    out["score"] = score

    # Recommendations: fill to 3 unique lines
    recs = []
    if "hrv_low" in out["flags"]:
        recs.append("Prioritize 7–8h sleep, add a 10–15 min evening wind-down.")
    if "resting_hr_high" in out["flags"]:
        recs.append("Add low-intensity walks and hydration; check caffeine late-day.")
    if "calories_low" in out["flags"]:
        recs.append("Sneak in 2k extra steps/day with short walks.")
    if "runs_low" in out["flags"]:
        recs.append("Block 3 runs in your calendar to build consistency.")
    generic = [
        "Keep up hydration and consistent bed/wake times.",
        "Add 5–10 minutes of mobility after workouts.",
        "Take a short walk after meals when possible.",
    ]
    for g in generic:
        if len(recs) >= 3:
            break
        if g not in recs:
            recs.append(g)

    out["recommendations"] = recs[:3]
    return out


def _fallback_weekly(data: Dict[str, Any]) -> str:
    steps = float(data.get("steps", 0))
    sleep = float(data.get("sleep_hours", 0))
    workouts = int(data.get("workouts", 0))
    water = float(data.get("water_liters", 0))
    avg_steps = steps / 7 if steps else 0
    avg_sleep = sleep / 7 if sleep else 0
    assess_steps = "✅ On track" if avg_steps >= 10000 else "⚠️ Aim for 10k/day"
    assess_sleep = "✅ On track" if avg_sleep >= 7 else "⚠️ Target 7–8h/night"
    assess_ex = "✅ ≥3 sessions" if workouts >= 3 else "⚠️ Try to reach 3+/week"

    rec1 = "Maintain your walking habit" if avg_steps >= 10000 else "Add a 15–20 min brisk walk after lunch"
    rec2 = "Keep consistent bedtime" if avg_sleep >= 7 else "Move bedtime earlier by ~30 minutes"
    rec3 = "Nice training cadence" if workouts >= 3 else "Schedule workouts on calendar to lock them in"

    return (
        "Weekly Health Report\n"
        "--------------------\n"
        f"• Daily Steps Avg: {avg_steps:.0f}\n"
        f"• Daily Sleep Avg: {avg_sleep:.1f}h\n"
        f"• Workouts: {workouts}\n"
        f"• Water: {water} L/week\n\n"
        "Assessment:\n"
        f"- Steps: {assess_steps}\n"
        f"- Sleep: {assess_sleep}\n"
        f"- Exercise: {assess_ex}\n\n"
        "Recommendations:\n"
        f"1) {rec1}\n"
        f"2) {rec2}\n"
        f"3) {rec3}\n"
    )

# ----------------- Endpoints -----------------
@app.get("/health", dependencies=[Depends(require_api_key)] if API_KEY else None)
async def health():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{ROMA_BASE}/status")
            roma_ok = r.status_code == 200
    except Exception:
        roma_ok = False
    return {"status": "healthy", "roma_available": roma_ok, "timestamp": datetime.utcnow().isoformat()}

@app.post("/weekly-report")
async def weekly_report(request: HealthData, save: bool = Query(False), db: Session = Depends(get_db)):
    d = request.data
    goal = ("Summarize the week, compute daily averages, give a short health assessment, "
            "and 2–3 specific, actionable recommendations. Keep it concise. Do NOT repeat my prompt.")
    a1 = await _roma_analysis(d, "weekly health metrics", goal=goal)
    if a1:
        text = a1
    else:
        goal_exec = f"""
You are a helpful health coach. Do NOT echo my instructions.
Using the following weekly data, write a brief report with:
- Daily averages
- Health assessment
- 2–3 concrete recommendations

Data:
- Steps: {d.get('steps', 0)} total
- Sleep: {d.get('sleep_hours', 0)} hours total
- Workouts: {d.get('workouts', 0)} sessions
- Water: {d.get('water_liters', 0)} liters
"""
        a2 = await _roma_execute(goal_exec)
        text = a2 if a2 else _fallback_weekly(d)

    metrics = {
        "daily_steps_avg": round(d.get("steps", 0)/7, 0) if d.get("steps") else 0,
        "daily_sleep_avg": round(d.get("sleep_hours", 0)/7, 1) if d.get("sleep_hours") else 0.0,
        "workouts": int(d.get("workouts", 0) or 0),
        "water_liters": float(d.get("water_liters", 0) or 0.0),
    }

    report_id = None
    if save:
        rec = ReportDB(
            kind="weekly",
            input_json=json.dumps(d),
            output_text=text,
            metrics_json=json.dumps(metrics)
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        report_id = rec.id

    return {"status": "success", "report": text, "metrics": metrics, "data_analyzed": d, "report_id": report_id}

@app.post("/analyze")
async def analyze(request: HealthData, save: bool = Query(False), db: Session = Depends(get_db)):
    d = request.data
    a1 = await _roma_analysis(d, "health metrics",
                              goal="Provide key observations, areas of concern, positive trends. Return brief text.")
    if a1 and isinstance(a1, str):
        text = a1
    else:
        a2 = await _roma_execute(f"You are a health data analyst. Analyze these metrics (concise, no echo): {d}")
        if a2 and isinstance(a2, str):
            text = a2
        else:
            struct = analyze_health_locally(d)
            text = json.dumps(struct, indent=2)

    report_id = None
    if save:
        rec = ReportDB(kind="analyze", input_json=json.dumps(d), output_text=text, metrics_json=None)
        db.add(rec); db.commit(); db.refresh(rec); report_id = rec.id

    return {"status": "success", "analysis": text if isinstance(text, str) else str(text), "report_id": report_id}

# -------- NEW: /chat (AI coaching) --------
@app.post("/chat")
async def chat(msg: ChatMessage, save: bool = Query(False), db: Session = Depends(get_db)):
    prompt = (
        "You are a supportive, concise health coach. Answer helpfully in 2–4 sentences. "
        "Avoid repeating the user's message. Respond to:\n\n"
        f"{msg.message}"
    )
    out = await _roma_execute(prompt)
    reply = out or "I'm here. Can you clarify your goal for this week (sleep, steps, workouts, or recovery)?"

    report_id = None
    if save or msg.save:
        rec = ReportDB(kind="chat", input_json=json.dumps({"message": msg.message}), output_text=reply, metrics_json=None)
        db.add(rec); db.commit(); db.refresh(rec); report_id = rec.id

    return {"status": "success", "reply": reply, "report_id": report_id}

# -------- NEW: /reports (CRUD, protected) --------
class ReportIn(BaseModel):
    kind: str
    input: Optional[Dict[str, Any]] = None
    output_text: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None

class ReportOut(BaseModel):
    id: int
    created_at: datetime
    kind: str
    input: Optional[Dict[str, Any]]
    output_text: Optional[str]
    metrics: Optional[Dict[str, Any]]

def _to_out(rec: ReportDB) -> ReportOut:
    return ReportOut(
        id=rec.id,
        created_at=rec.created_at,
        kind=rec.kind,
        input=json.loads(rec.input_json) if rec.input_json else None,
        output_text=rec.output_text,
        metrics=json.loads(rec.metrics_json) if rec.metrics_json else None,
    )

@app.get("/reports", response_model=List[ReportOut], dependencies=[Depends(require_api_key)] if API_KEY else None)
def list_reports(limit: int = 20, offset: int = 0, kind: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(ReportDB).order_by(ReportDB.created_at.desc())
    if kind:
        q = q.filter(ReportDB.kind == kind)
    rows = q.offset(offset).limit(limit).all()
    return [_to_out(r) for r in rows]

@app.get("/reports/{report_id}", response_model=ReportOut, dependencies=[Depends(require_api_key)] if API_KEY else None)
def get_report(report_id: int, db: Session = Depends(get_db)):
    rec = db.get(ReportDB, report_id)
    if not rec: raise HTTPException(404, "Report not found")
    return _to_out(rec)

@app.post("/reports", response_model=ReportOut, dependencies=[Depends(require_api_key)] if API_KEY else None)
def create_report(body: ReportIn, db: Session = Depends(get_db)):
    rec = ReportDB(
        kind=body.kind,
        input_json=json.dumps(body.input or {}),
        output_text=body.output_text,
        metrics_json=json.dumps(body.metrics or {})
    )
    db.add(rec); db.commit(); db.refresh(rec)
    return _to_out(rec)

@app.delete("/reports/{report_id}", dependencies=[Depends(require_api_key)] if API_KEY else None)
def delete_report(report_id: int, db: Session = Depends(get_db)):
    rec = db.get(ReportDB, report_id)
    if not rec: raise HTTPException(404, "Report not found")
    db.delete(rec); db.commit()
    return {"status": "deleted", "id": report_id}

# ----------------- Entrypoint -----------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
