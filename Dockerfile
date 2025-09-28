# Dockerfile (health-tracker)
FROM python:3.11-slim

# (optional but handy for debugging)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first for better build caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code
COPY . /app

# Documented port (compose will do the actual mapping)
EXPOSE 8000

# Default command (compose can override)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port",  "8000"]
