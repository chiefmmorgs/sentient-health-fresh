#!/bin/bash

echo "Testing Health Tracker with OpenDeepSearch Integration"
echo "======================================================="
echo

echo "1. Testing search service..."
curl -s -X POST http://localhost:5001/search \
  -H "Content-Type: application/json" \
  -d '{"query": "optimal heart rate for fitness"}' | jq .

echo
echo "2. Testing research endpoint..."
curl -s -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "How much sleep do adults need?"}' | jq .

echo
echo "3. Testing chat with health question..."
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are signs of overtraining?"}' | jq .

echo
echo "4. Testing chat with heart rate question..."
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "My resting heart rate is 75 and HRV is 45. What does this mean?"}' | jq .

echo
echo "Done!"
