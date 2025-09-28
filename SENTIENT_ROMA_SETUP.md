# Sentient ROMA Health Tracker Setup

## 🤖 Advanced AI Health Analysis with Hierarchical Multi-Agent System

This implementation uses the **Sentient AGI ROMA framework** for sophisticated health analysis through recursive task decomposition and specialized AI agents.

## 🏗️ **ROMA Architecture**

**ROMA (Recursive Open Meta-Agent)** follows this pattern:

```python
def solve(task):
    if is_atomic(task):           # 1. Atomizer
        return execute(task)       # 2. Executor
    else:
        subtasks = plan(task)      # 2. Planner  
        results = []
        for subtask in subtasks:
            results.append(solve(subtask))  # Recursive!
        return aggregate(results)  # 3. Aggregator
```

### **🧠 Core Components:**

| Component | Role | Health Function |
|-----------|------|----------------|
| **🔍 Atomizer** | Task complexity analysis | Determines if analysis is simple or needs decomposition |
| **🗺️ Planner** | Task decomposition | Breaks complex health analysis into specialized subtasks |
| **⚙️ Executors** | Specialized agents | Data validation, metrics calculation, coaching, reporting |
| **🔄 Aggregator** | Results integration | Combines all insights into coherent final report |

## 📋 **Prerequisites**

- **Python 3.8+**
- **AI API Key** (choose one):
  - OpenAI API key (recommended: GPT-4o-mini)
  - OpenRouter API key (cheaper alternative)
  - Anthropic API key (Claude models)

## 🚀 **Quick Setup**

### 1. **Install Dependencies**

```bash
pip install -r requirements.txt
```

### 2. **Configure API Keys**

Create `.env` file:

```bash
# Copy example
cp .env.example .env

# Add your AI API key (choose one):
echo "OPENAI_API_KEY=sk-your-openai-key-here" >> .env
# OR
echo "OPENROUTER_API_KEY=sk-or-your-openrouter-key-here" >> .env  
# OR
echo "ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here" >> .env
```

### 3. **Get API Keys**

#### **Option A: OpenAI (Best Quality)**
- Go to https://platform.openai.com/api-keys
- Create new API key
- Cost: ~$0.15-0.75 per comprehensive health report

#### **Option B: OpenRouter (Most Cost-Effective)**  
- Go to https://openrouter.ai/keys
- Sign up and create API key
- Cost: ~$0.02-0.10 per health report
- Uses various models (Llama, Mistral, etc.)

#### **Option C: Anthropic (Claude Models)**
- Go to https://console.anthropic.com/
- Create API key
- Cost: ~$0.10-0.50 per health report

### 4. **Run the Application**

```bash
python sentient_roma_api.py
```

Server starts at: `http://127.0.0.1:8000`

## 🔧 **API Endpoints**

### **📊 Main Feature: Comprehensive Health Analysis**

**Endpoint:** `POST /weekly-report`

**ROMA Process:**
1. **Atomizer** analyzes your data complexity
2. **Planner** creates execution strategy with specialized subtasks
3. **Executors** run in dependency order:
   - Data validation & normalization
   - Health metrics calculation (BMI, TDEE, adherence)
   - Personalized coaching recommendations  
   - Comprehensive report generation
4. **Aggregator** integrates all results into final insights

**Example:**
```bash
# Get example data and run full ROMA analysis
curl -X POST http://127.0.0.1:8000/weekly-report \
  -H "Content-Type: application/json" \
  -d "$(curl -s http://127.0.0.1:8000/example)"
```

**Response includes:**
- Executive summary with key health insights
- Health score (0-100) with detailed explanation
- Personalized coaching recommendations
- Weekly action plan with specific next steps
- Long-term health strategy recommendations
- ROMA execution metadata and agent performance

### **🔍 Quick Single-Entry Analysis**

**Endpoint:** `POST /analyze`

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "meal_log": "Quinoa bowl with roasted vegetables",
    "exercise_log": "45 min strength training", 
    "sleep_log": "7.5h",
    "mood_log": "Energetic and focused",
    "water_intake_l": 3.2,
    "notes": "Great energy today"
  }'
```

### **💬 AI Health Coach Chat**

**Endpoint:** `POST /chat`

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I struggle with consistency in my workout routine. Any advice?",
    "context": "I work from home and have been sedentary recently"
  }'
```

### **🧪 System Testing**

**Endpoint:** `GET /test-roma`

Tests the full ROMA pipeline to ensure all components work:

```bash
curl http://127.0.0.1:8000/test-roma
```

## 📈 **ROMA vs Traditional Systems**

| Feature | Traditional Health Apps | Sentient ROMA Framework |
|---------|------------------------|-------------------------|
| **Analysis Depth** | Basic rule-based metrics | Hierarchical AI reasoning |
| **Personalization** | Generic recommendations | Multi-agent personalized insights |
| **Task Handling** | Single-pass processing | Recursive task decomposition |
| **Adaptability** | Fixed workflows | Dynamic planning based on complexity |
| **Insights Quality** | Surface-level | Deep, contextualized analysis |
| **Scalability** | Limited by predefined rules | Scales with task complexity |

## 🛠️ **Advanced Configuration**

### **Environment Variables**

```env
# AI Provider (choose one)
OPENAI_API_KEY=sk-your-openai-key
OPENROUTER_API_KEY=sk-or-your-openrouter-key  
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Optional: Model selection
AGNO_DEFAULT_MODEL=gpt-4o-mini
# Or for OpenRouter: openrouter/meta-llama/llama-3.2-3b-instruct:free

# Optional: Debug settings
ROMA_DEBUG=true
ROMA_LOG_LEVEL=INFO
```

### **Custom Agent Configuration**

You can customize agent prompts and behavior by modifying:

- `roma_agents/sentient_health_agents.py` - Agent definitions and instructions
- `roma_engine/sentient_roma_runner.py` - ROMA execution logic and workflow

## 🧪 **Testing & Verification**

### **1. System Health Check**
```bash
curl http://127.0.0.1:8000/health
```

### **2. ROMA System Information**
```bash  
curl http://127.0.0.1:8000/roma-info
```

### **3. Complete System Test**
```bash
curl http://127.0.0.1:8000/test-roma
```

### **4. Interactive API Documentation**
Visit: `http://127.0.0.1:8000/docs`

## 💰 **Cost Analysis**

### **Typical Usage Costs:**

| Provider | Weekly Report | Quick Analysis | Chat Session |
|----------|---------------|----------------|--------------|
| **OpenRouter** | $0.02-0.10 | $0.005-0.02 | $0.002-0.01 |
| **OpenAI GPT-4o-mini** | $0.15-0.75 | $0.03-0.15 | $0.01-0.05 |
| **Anthropic Claude** | $0.10-0.50 | $0.02-0.10 | $0.01-0.05 |

### **What Affects Cost:**
- **Data complexity**: More logs = more analysis = higher cost
- **Agent interactions**: Complex tasks requiring multiple agents
- **Model choice**: Premium models cost more but provide better insights

## 🔧 **Troubleshooting**

### **Common Issues:**

#### **❌ "ROMA engine unavailable"**
```bash
# Check API keys
cat .env

# Verify dependencies
pip install -r requirements.txt

# Test API key
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

#### **❌ Agent execution failures**
- Check API rate limits
- Verify sufficient API credits
- Review agent logs for specific errors

#### **❌ Slow response times**
- Normal for comprehensive analysis (30-90 seconds)
- Use `/analyze` for faster single-entry processing
- Consider OpenRouter for cost-effective scaling

### **Debug Mode:**
```bash
# Enable detailed logging
export ROMA_DEBUG=true
python sentient_roma_api.py
```

## 🚀 **Next Steps**

1. **Test the system** with the example payload
2. **Integrate your data** by customizing the payload format
3. **Enhance agents** by modifying their instructions and capabilities
4. **Scale up** by adding new specialized agents (nutrition, mental health, etc.)
5. **Deploy** using Docker or cloud platforms

## 📚 **Learn More**

- **Sentient AGI ROMA**: https://github.com/sentient-agi/ROMA
- **ROMA Paper**: "Beyond Outlining: Hierarchical Recursive Planning" 
- **Agno Framework**: https://docs.agno.com
- **API Documentation**: http://127.0.0.1:8000/docs (when running)

---

## 🎯 **Ready to Experience Hierarchical AI Health Analysis?**

```bash
# Start the system
python sentient_roma_api.py

# Test with example data  
curl -X POST http://127.0.0.1:8000/weekly-report \
  -H "Content-Type: application/json" \
  -d "$(curl -s http://127.0.0.1:8000/example)"
```

🤖 **Welcome to the future of personalized health analysis with Sentient ROMA!**
