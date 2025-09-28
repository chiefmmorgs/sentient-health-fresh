#!/bin/bash
# fix_health_tracker.sh

echo "�� Diagnosing Health Tracker Issues..."
echo "======================================="

# 1. Check what's running
echo -e "\n1. Current Docker containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 2. Check if health-tracker container exists but stopped
echo -e "\n2. All containers (including stopped):"
docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep -E "health|roma"

# 3. Check Docker Compose status
echo -e "\n3. Docker Compose status:"
docker-compose ps

# 4. Check for port conflicts
echo -e "\n4. Checking port 8000:"
lsof -i :8000 2>/dev/null || echo "Port 8000 is free"

# 5. Fix attempt 1: Start with docker-compose
echo -e "\n5. Starting services with docker-compose..."
docker-compose up -d

# Wait for services
sleep 3

# 6. Check logs
echo -e "\n6. Health-tracker logs (last 20 lines):"
docker-compose logs --tail=20 health-tracker 2>&1 || echo "No health-tracker container found"

# 7. Alternative: Run health-tracker locally
echo -e "\n7. Alternative - Run locally (if Docker fails):"
echo "   cd ~/Sentient-health-tracker-/fresh"
echo "   python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

# 8. Test endpoints
echo -e "\n8. Testing services:"
echo -n "   ROMA (5000): "
curl -sS http://localhost:5000/api/simple/status &>/dev/null && echo "✅ Working" || echo "❌ Not working"

echo -n "   Health-tracker (8000): "
curl -sS http://localhost:8000/health &>/dev/null && echo "✅ Working" || echo "❌ Not working"

echo -e "\n======================================="
echo "📊 Summary:"
if curl -sS http://localhost:8000/health &>/dev/null; then
    echo "✅ Health-tracker is now running!"
    echo "Test with: curl http://localhost:8000/health"
else
    echo "❌ Health-tracker still not running"
    echo "See troubleshooting steps below"
fi
