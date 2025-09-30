# 🤖 Sentient ROMA Health Tracker

**AI-powered health analysis using the Sentient AGI ROMA framework.**  
An intelligent health tracking system combining the ROMA agent framework with OpenDeepSearch for evidence-based medical insights. Features automated research, health coaching, and comprehensive weekly reports backed by authoritative medical sources.

**3 Microservices**: Health API, ROMA orchestration, Search service
- **ROMA Pattern**: Atomizer → Planner → Executors → Aggregator
- **Specialized Agents**: Research, Metrics, Coaching, Reporting

DataIngestionAgent - validates/normalizes inputs
MetricsAnalysisAgent - computes health scores
CoachingAgent - generates personalized recommendations
ReportingAgent - creates comprehensive weekly summaries

 Health Analysis
- **Weekly Reports**: Comprehensive analysis with metrics assessment and personalized recommendations
- **Health Chat**: Natural language Q&A with evidence-based responses
- **Direct Research**: Query medical databases on-demand

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688)](#)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](#)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

**Features**

AI-Powered Analysis: Get intelligent health insights from your weekly metrics

Personal Health Coaching: Chat interface for health advice and motivation

Weekly Reports: Comprehensive analysis with actionable recommendations

Data Persistence: Save and retrieve historical health reports

Fault Tolerance: Works with local algorithms when LLM is unavailable

Secure API: API key protection for sensitive operations


**Prerequisites**

Docker and Docker Compose
OpenRouter API key (free tier available at https://openrouter.ai/keys)

Serper - For Google search (free tier: 2,500 queries) (https://serper.dev/signup)

Jina - For web scraping (free tier: 20,000 requests) (https://jina.ai/)


---

## 🚀 Quick Start

### 1) Clone

```bash
git clone https://github.com/chiefmmorgs/sentient-health-fresh.git
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



4. Access Application
```
Open in browser: http://localhost:8000
```


🔧 API Endpoints
Core Endpoints

GET / - Web interface
GET /health - Service health check
POST /weekly-report - Generate comprehensive health report
POST /chat - Health assistant conversation
POST /research - Direct medical research

Search Service

POST /search - Search health information
GET /cache/stats - Cache statistics
POST /cache/clear - Clear cache

ROMA Service

POST /analyze - ROMA orchestration
POST /execute - Direct executor call
GET /agents - List available agents




🧠 How It Works (ROMA)

```
┌─────────────────────────────────────────────────┐
│           Health Tracker Frontend               │
│        (http://localhost:8000)                  │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│         Health API Service (Port 8000)          │
│  • Weekly Reports    • Chat    • Research       │
└────────┬────────────────────────────┬───────────┘
         │                            │
         ▼                            ▼
┌──────────────────┐         ┌──────────────────┐
│  ROMA Service    │         │  Search Service  │
│  (Port 5000)     │         │  (Port 5001)     │
│                  │         │                  │
│  • Atomizer      │         │  • Serper API    │
│  • Planner       │         │  • Jina Reader   │
│  • Executors     │         │  • 24h Cache     │
│  • Aggregator    │         │  • OpenDeepSearch│
└──────────────────┘         └──────────────────┘
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



sentient-health-fresh/
├── main.py                 # Health API service
├── search_service.py       # OpenDeepSearch integration
├── cache_manager.py        # Result caching
├── roma_service.py         # ROMA orchestration
├── roma_engine/            # ROMA framework
├── roma_agents/
│   ├── research_agent.py   # Medical research
│   ├── metrics_agent.py    # Health calculations
│   ├── coaching_agent.py   # Recommendations
│   └── reporting_agent.py  # Report generation
├── static/
│   ├── index.html          # Frontend UI
│   └── chiefmmorgs.png     # Branding
├── Dockerfile.health       # Health service container
├── Dockerfile.roma         # ROMA service container
├── Dockerfile.search       # Search service container
├── docker-compose.yml      # Service orchestration
└── requirements-*.txt      # Dependencies

```
# Run integration tests
```
./test_integration.sh
```

# Test specific endpoint
```
curl http://localhost:8000/health
```

# Check service logs
```
docker compose logs -f health
docker compose logs -f roma
docker compose logs -f search
```

# Check status
```
docker compose ps
```

# View logs
```
docker compose logs health
```

# Rebuild
```
docker compose down
docker compose build --no-cache
docker compose up -d
```


# Clear cache
```
curl -X POST http://localhost:5001/cache/clear
```

# Check cache stats
```
curl http://localhost:5001/cache/stats


```
Local Development

# Install dependencies
```
pip install -r requirements-base.txt

```
# Run health service
```
uvicorn main:app --reload --port 8000

```
# Run ROMA service (separate terminal)
```
python roma_service.py

```
# Run search service (separate terminal)
```
uvicorn search_service:app --reload --port 5001

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
# Clear cache
```
curl -X POST http://localhost:5001/cache/clear

```
# Check cache stats

```
curl http://localhost:5001/cache/statsl

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
