FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with retries
RUN pip install --no-cache-dir --retries 10 -r requirements.txt

# Copy ALL source code (including llm_fallback.py)
COPY . .

# Ensure llm_fallback.py is in Python path
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Create data directory
RUN mkdir -p /app/data

# Environment variables
ENV HOST=0.0.0.0 
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "sentient_roma_api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
