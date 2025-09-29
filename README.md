# 🤖 Sentient ROMA Health Tracker

**AI-powered health analysis using the Sentient AGI ROMA framework.**  
This Health Tracker is a thoughtful, modular approach to health data analysis and coaching using agent orchestration. By pairing a local, self-hosted architecture with an AI meta-agent layer, it balances privacy, flexibility, and intelligence.
This project demonstrates a practical multi-agent system for health tracking using the ROMA pattern

**Atomizer → Planner → Executors (Ingest / Metrics / Coach / Report) → Aggregator**
With specialized health agents:

DataIngestionAgent - validates/normalizes inputs
MetricsAnalysisAgent - computes health scores
CoachingAgent - generates personalized recommendations
ReportingAgent - creates comprehensive weekly summaries

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688)](#)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](#)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

Features

AI-Powered Analysis: Get intelligent health insights from your weekly metrics
Personal Health Coaching: Chat interface for health advice and motivation
Weekly Reports: Comprehensive analysis with actionable recommendations
Data Persistence: Save and retrieve historical health reports
Fault Tolerance: Works with local algorithms when LLM is unavailable
Secure API: API key protection for sensitive operations



Prerequisites

Docker and Docker Compose
OpenRouter API key (free tier available at https://openrouter.ai/keys)



---

## 🚀 Quick Start

### 1) Clone

```bash
git clone https://github.com/chiefmmorgs/Sentient-health-tracker-.git
cd sentient-health-fresh
```   

### 2) Environment

Create a `.env` file in the project root:

```env
cp .env.example .env
  echo "OPENROUTER_API_KEY=sk-or-v1-your-key-here" >> .env

 # to check 
nano .env

 # you can change the health key, health key is a self made key 
 echo "HEALTH_API_KEY=$(openssl rand -hex 32)" >> .env
```  

Keep `.env` private


3) Run with Docker Compose
```bash
docker compose up -d --build

```

 # Check status
 ```
   docker compose ps
 ```

   # Test connectivity
```
   curl http://127.0.0.1:8000/health
```

4) Test

Health (protected):

```bash

curl -H "X-API-Key: your-secret-key" http://127.0.0.1:8000/health

```
Test Weekly Report:

```
curl -sS -X POST http://127.0.0.1:8000/weekly-report \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "steps": 85000,
      "sleep_hours": 56,
      "workouts": 5,
      "water_liters": 18
    }
  }' | jq '.report'
```


2. Test Chat:
```
curl -sS -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I have been feeling tired lately and struggling with my morning routine. Any advice?"
  }' | jq '.reply'

```


3. Test Analysis:
```
bashcurl -sS -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "steps": 8500,
      "sleep_hours": 6.5,
      "workouts": 2,
      "water_liters": 2.5
    }
  }' | jq '.analysis'


```

  Save and Retrieve Reports
```
# Save a report (requires API key)
curl -X POST "http://127.0.0.1:8000/weekly-report?save=true" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"data": {"steps": 75000, "sleep_hours": 49, "workouts": 4, "water_liters": 16}}'

# List saved reports
curl -H "X-API-Key: YOUR_API_KEY" http://127.0.0.1:8000/reports

# Get specific report
curl -H "X-API-Key: YOUR_API_KEY" http://127.0.0.1:8000/reports/REPORT_ID
```





Environment Variables
bash# Required
OPENROUTER_API_KEY=sk-or-v1-your-key-here
HEALTH_API_KEY=your-secure-random-key

# Optional
DEFAULT_MODEL=meta-llama/llama-3.2-3b-instruct:free
ROMA_BASE_URL=http://roma:5000
DATABASE_URL=sqlite:///./health_reports.db


```
Open docs in your browser:
http://127.0.0.1:8000/docs

# Core functionality
POST /weekly-report    # Comprehensive ROMA analysis

POST /analyze         # Quick health insights 

POST /chat           # AI health coaching

GET /reports         # Browse saved reports

# System status
GET /health          # Service health check

GET /roma-info       # ROMA architecture info



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

🛠️ For Developers
i am just vibe coding use as u want 

Recommended contributions:

Real wearable integrations (Fitbit/HealthKit/Garmin).

Frontend dashboard (Next.js/React) calling this API.

More agents (nutrition, recovery, stress).

```
Project Structure


sentient-health-tracker/
├── main.py                 # FastAPI health tracker service
├── roma_service.py         # ROMA meta-agent service  
├── roma_engine/            # ROMA framework
├── roma_agents/            # Specialized health agents
├── Dockerfile.health       # Health tracker container
├── Dockerfile.roma         # ROMA service container
├── compose.yml             # Docker composition
├── requirements.txt        # Python dependencies
└── .env                    # Environment configuration



Local Development

# Install dependencies
```
pip install -r requirements.txt
```

# Run health tracker locally
```
uvicorn main:app --host 0.0.0.0 --port 8000
```

# Run ROMA service locally
```
python roma_service.py


```

Troubleshooting
Common Issues
ROMA service not responding (port 5000)
# Check if port is mapped correctly
```
docker compose ps
```

# Check logs
```
docker compose logs roma
```

# Rebuild if needed
```
docker compose build roma
```
LLM not working ("llm_working": false)
# Verify API key
```
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" https://openrouter.ai/api/v1/models
```
# Test different model

```
echo "DEFAULT_MODEL=google/gemma-2-9b-it:free" >> .env
docker compose restart roma
```
Database errors


# Check database file permissions
```
ls -la health_reports.db
```

# Reset database
```
docker compose down -v
docker compose up -d
```
🔐 Security

Set API_KEY in .env to require X-API-Key for /health and /reports.

Keep .env out of version control.

🧾 License

MIT — free to use, modify, and distribute. 
