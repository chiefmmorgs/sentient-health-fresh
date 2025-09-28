# 🤖 Sentient ROMA Health Tracker

**Advanced AI-powered health analysis using the Sentient AGI ROMA framework.**  
This project demonstrates a practical multi-agent system for health tracking using the ROMA pattern:

**Atomizer → Planner → Executors (Ingest / Metrics / Coach / Report) → Aggregator**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688)](#)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](#)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

- **ROMA framework** for recursive task decomposition.
- **Agents**
  - **DataIngestionAgent** – validates and normalizes inputs.
  - **MetricsAnalysisAgent** – computes basic scores (activity, sleep, hydration) and asks an LLM for insights.
  - **CoachingAgent** – personalized tips via GPT (OpenRouter).
  - **ReportingAgent** – structured weekly summary, saved to SQLite.
- **FastAPI service** with clean REST endpoints.
- **SQLite persistence** for saved reports.
- **API key guard** for `/health` and `/reports`.
- **Dockerized** with Compose for one-command deploy.

---

## 🚀 Quick Start

### 1) Clone

```bash
git clone https://github.com/chiefmmorgs/Sentient-health-tracker-.git
cd Sentient-health-tracker-
```   

### 2) Environment

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=sk-your-openrouter-key
DEFAULT_MODEL=gpt-3.5-turbo
API_KEY=your-secret-key
DB_PATH=/app/data/db.sqlite
```  

Keep `.env` private (it’s already in `.gitignore`).


3) Run with Docker Compose
```bash
docker compose up -d --build

```

4) Test

Health (protected):

```bash

curl -H "X-API-Key: your-secret-key" http://127.0.0.1:8000/health

```
Weekly report:

```

curl -X POST http://127.0.0.1:8000/weekly-report \
  -H "Content-Type: application/json" \
  -d '{"data":{"steps":72000,"sleep_hours":49,"workouts":4,"water_liters":14}}'


```
Open docs in your browser:
http://127.0.0.1:8000/docs

🔗 Endpoints

GET /health — API+DB status (requires X-API-Key)

GET /roma-info — ROMA architecture summary

POST /analyze — Quick single-entry analysis

POST /weekly-report — Full ROMA pipeline (ingest → metrics → coach → report)

POST /chat — AI coaching on an input message

GET /reports — List saved reports (requires X-API-Key)

GET /reports/{id} — Retrieve a saved report (requires X-API-Key)



🧠 How It Works (ROMA)

```
flowchart LR
    A[User Request] --> B{Atomizer}
    B -- atomic --> E[Executor]
    B -- complex --> C[Planner]
    C --> E1[Ingest Agent]
    E1 --> E2[Metrics Agent]
    E2 --> E3[Coaching Agent]
    E3 --> E4[Reporting Agent]
    E & E1 & E2 & E3 & E4 --> F[Aggregator]
    F --> G[Response + (optional) Save to SQLite]
```
Atomizer: decides if the task is atomic or needs decomposition.

Planner: creates an ordered plan (ingest → metrics → coach → report).

Executors: domain agents perform their part; Metrics/Coach/Report can call GPT via OpenRouter.

Aggregator: merges results into the final response.


🧪 Example Use Cases

Personal Health Assistant – weekly summaries & advice.

Wellness App Backend – mobile/web apps can call these endpoints.

Research / Learning – a concrete example of multi-agent orchestration.

Fork & Repurpose – swap health agents for finance, study, productivity, etc.

🛠️ For Developers

Fork it → build your own agent set in roma_agents/.

Extend the planner/aggregator for new workflows.

Persist reports with SQLite (mounted volume via ./data).

Secure endpoints using the X-API-Key header.

Deploy on a VPS: Docker + .env + reverse proxy (optional).


Recommended contributions:

Real wearable integrations (Fitbit/HealthKit/Garmin).

Frontend dashboard (Next.js/React) calling this API.

More agents (nutrition, recovery, stress).

📦 Project Structure (core)
```
.
├── sentient_roma_api.py         # FastAPI entrypoint
├── roma_engine/
│   └── sentient_roma_runner.py  # ROMA runner/orchestration
├── roma_agents/
│   └── sentient_health_agents.py# Agents (ingest/metrics/coach/report)
├── storage/
│   └── db.py                    # SQLite helpers
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
├── data/                        # Mounted DB folder (persisted)
└── LICENSE

```

🔐 Security

Set API_KEY in .env to require X-API-Key for /health and /reports.

Keep .env out of version control.

If deploying publicly, put a reverse proxy (e.g., Nginx) with HTTPS.

🧾 License

MIT — free to use, modify, and distribute. 
