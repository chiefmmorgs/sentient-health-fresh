# ==== create repo root ====
proj="sentient-roma-health-tracker"
mkdir -p "$proj" && cd "$proj"

# ==== core files ====
cat > README.md <<'EOF'
Sentient ROMA Health Tracker
Advanced AI health analysis with hierarchical multi-agent ROMA pattern.
Files contain PASTE_HERE markers. Replace those blocks with your final code.
EOF

cat > .gitignore <<'EOF'
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.so
.venv/
venv/
.env
.env.*
dist/
build/
*.egg-info/
.pytest_cache/
.cache/
.mypy_cache/
.coverage
htmlcov/
# Editors
.vscode/
.idea/
# Docker
*.log
EOF

cat > .env.example <<'EOF'
# copy to .env and fill in values
OPENAI_API_KEY=
OPENROUTER_API_KEY=
ANTHROPIC_API_KEY=

# server
HOST=0.0.0.0
PORT=8000

# optional model routing
DEFAULT_MODEL=gpt-4o-mini

# any app specific keys
EOF

cat > requirements.txt <<'EOF'
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-dotenv>=1.0.0
pydantic>=2.5.0
agno>=2.0.0
litellm>=1.44.0
requests>=2.31.0
aiohttp>=3.9.0
asyncio-throttle>=1.0.2
EOF

cat > sentient_roma_api.py <<'EOF'
"""
FastAPI entrypoint wired to ROMA engine and agents.

Replace PASTE_HERE blocks with your full implementations.
"""

from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import Any, Dict
import os

# local imports
from roma_engine.sentient_roma_runner import ROMARunner  # PASTE_HERE: ensure class exists

app = FastAPI(title="Sentient ROMA Health Tracker", version="0.1.0")
runner = ROMARunner()  # PASTE_HERE: init with config if needed

class WeeklyPayload(BaseModel):
    data: Dict[str, Any]

@app.get("/")
def root():
    return {"ok": True, "service": "sentient-roma-health-tracker"}

@app.get("/roma-info")
def roma_info():
    # PASTE_HERE: return detailed architecture if desired
    return {"roma": "Atomizer -> Planner -> Executor -> Aggregator"}

@app.post("/analyze")
def analyze(payload: Dict[str, Any] = Body(...)):
    # PASTE_HERE: call runner.single_entry_analysis
    result = runner.analyze_single(payload)
    return {"analysis": result}

@app.post("/weekly-report")
def weekly_report(payload: WeeklyPayload):
    # PASTE_HERE: call runner.full_weekly_report
    result = runner.run_weekly(payload.data)
    return {"report": result}

@app.post("/chat")
def chat(message: Dict[str, Any] = Body(...)):
    # PASTE_HERE: wire to a CoachingAgent or chat chain
    reply = runner.chat(message)
    return {"reply": reply}

@app.get("/example")
def example():
    # minimal example payload
    return {"steps": 72000, "sleep_hours": 49, "workouts": 4, "water_liters": 14}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("sentient_roma_api:app",
                host=os.getenv("HOST","0.0.0.0"),
                port=int(os.getenv("PORT","8000")),
                reload=True)
EOF

# ==== engine ====
mkdir -p roma_engine
cat > roma_engine/__init__.py <<'EOF'
# package init
EOF

cat > roma_engine/sentient_roma_runner.py <<'EOF'
"""
ROMA Orchestrator. Implements recursive task handling.

PASTE_HERE: replace stubs with your full logic from Claudia.
"""

from typing import Any, Dict, List

# PASTE_HERE: import your agents
from roma_agents.sentient_health_agents import (
    Atomizer, Planner, MetricsAnalysisAgent,
    DataIngestionAgent, CoachingAgent, ReportingAgent, Aggregator
)

class ROMARunner:
    def __init__(self):
        # PASTE_HERE: model router, config, dependencies
        self.atomizer = Atomizer()
        self.planner = Planner()
        self.ingest = DataIngestionAgent()
        self.metrics = MetricsAnalysisAgent()
        self.coach = CoachingAgent()
        self.report = ReportingAgent()
        self.aggregator = Aggregator()

    def _solve(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # Atomizer
        atomic = self.atomizer.is_atomic(task)
        if atomic:
            return self._execute(task)

        # Planner
        subtasks = self.planner.plan(task)
        results: List[Dict[str, Any]] = []
        for sub in subtasks:
            results.append(self._solve(sub))
        return self.aggregator.combine(results)

    def _execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # naive router example - replace with your logic
        kind = task.get("kind")
        if kind == "ingest":
            return self.ingest.run(task)
        if kind == "metrics":
            return self.metrics.run(task)
        if kind == "coach":
            return self.coach.run(task)
        if kind == "report":
            return self.report.run(task)
        return {"ok": False, "error": "unknown atomic task"}

    # public API
    def run_weekly(self, data: Dict[str, Any]) -> Dict[str, Any]:
        task = {"kind": "weekly_root", "data": data}
        return self._solve(task)

    def analyze_single(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        task = {"kind": "metrics", "data": entry}
        return self._execute(task)

    def chat(self, message: Dict[str, Any]) -> Dict[str, Any]:
        task = {"kind": "coach", "data": message}
        return self._execute(task)
EOF

# ==== agents ====
mkdir -p roma_agents
cat > roma_agents/__init__.py <<'EOF'
# package init
EOF

cat > roma_agents/sentient_health_agents.py <<'EOF'
"""
All ROMA agents for health tracking.

PASTE_HERE: replace stubs with Claudia's full implementations.
"""

from typing import Any, Dict, List

class Atomizer:
    def is_atomic(self, task: Dict[str, Any]) -> bool:
        # PASTE_HERE: smarter logic
        return task.get("kind") in {"ingest","metrics","coach","report"}

class Planner:
    def plan(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        # PASTE_HERE: decompose into ordered subtasks with deps
        data = task.get("data", {})
        return [
            {"kind": "ingest", "data": data},
            {"kind": "metrics", "data": data},
            {"kind": "coach", "data": data},
            {"kind": "report", "data": data},
        ]

class DataIngestionAgent:
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # PASTE_HERE
        return {"stage": "ingest", "ok": True}

class MetricsAnalysisAgent:
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # PASTE_HERE
        data = task.get("data", {})
        return {"stage": "metrics", "ok": True, "summary": {"mock": True, "data_seen": bool(data)}}

class CoachingAgent:
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # PASTE_HERE
        return {"stage": "coach", "ok": True, "advice": ["hydrate", "walk", "sleep 7-8h"]}

class ReportingAgent:
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # PASTE_HERE
        return {"stage": "report", "ok": True, "report": "Weekly report PASTE_HERE"}

class Aggregator:
    def combine(self, parts: List[Dict[str, Any]]) -> Dict[str, Any]:
        # PASTE_HERE
        return {"ok": True, "parts": parts}
EOF

# ==== docs ====
mkdir -p docs
cat > docs/API_GUIDE.md <<'EOF'
API Guide
- POST /weekly-report
- POST /analyze
- POST /chat
- GET /roma-info
- GET /docs
EOF

cat > docs/ROMA_ARCHITECTURE.md <<'EOF'
ROMA Architecture
Atomizer -> Planner -> Executor -> Aggregator.
Replace with your detailed writeup.
EOF

cat > docs/COST_ANALYSIS.md <<'EOF'
Cost Analysis
Add your token estimates per endpoint and model.
EOF

cat > docs/EXAMPLES.md <<'EOF'
Examples
See /examples folder for payloads.
EOF

# ==== examples ====
mkdir -p examples
cat > examples/test_data.json <<'EOF'
{
  "steps": 72000,
  "sleep_hours": 49,
  "workouts": 4,
  "water_liters": 14
}
EOF

cat > examples/sample_requests.json <<'EOF'
{
  "weekly-report": {
    "data": {
      "steps": 72000,
      "sleep_hours": 49,
      "workouts": 4,
      "water_liters": 14
    }
  },
  "analyze": {
    "heart_rate": [65, 72, 70],
    "calories": 14500
  },
  "chat": {
    "message": "Help me improve sleep"
  }
}
EOF

cat > examples/sample_responses.json <<'EOF'
{
  "report": {"ok": true},
  "analysis": {"ok": true},
  "reply": {"text": "Example"}
}
EOF

# ==== scripts ====
mkdir -p scripts
cat > scripts/setup.sh <<'EOF'
#!/usr/bin/env bash
set -e
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "Create .env from .env.example and run:"
echo "uvicorn sentient_roma_api:app --reload --host 0.0.0.0 --port 8000"
EOF
chmod +x scripts/setup.sh

cat > scripts/test_all.py <<'EOF'
import subprocess, sys

def run(cmd):
    print(">>", " ".join(cmd))
    subprocess.check_call(cmd)

run([sys.executable, "-m", "pytest", "-q"])
EOF

cat > scripts/benchmark.py <<'EOF'
# PASTE_HERE: simple timing harness for runner.run_weekly
EOF

# ==== tests ====
cat > test_roma.py <<'EOF'
from roma_engine.sentient_roma_runner import ROMARunner

def test_weekly_flow():
    r = ROMARunner()
    out = r.run_weekly({"steps": 10000})
    assert out and "ok" in out
EOF

# ==== docker ====
mkdir -p docker
cat > docker/Dockerfile <<'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["uvicorn", "sentient_roma_api:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

cat > docker/.dockerignore <<'EOF'
__pycache__/
.venv/
.env
.git/
*.log
EOF

cat > docker/docker-compose.yml <<'EOF'
services:
  api:
    build: .
    image: sentient-roma-health:latest
    ports:
      - "8000:8000"
    env_file:
      - ../.env
    restart: unless-stopped
EOF

echo "Scaffold ready in $PWD"
