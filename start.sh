#!/bin/bash
set -e

echo "=== Starting Recon PMS Container ==="

# Start uvicorn (FastAPI) in the background on port 8000
echo "Starting FastAPI (uvicorn) on port 8000..."
cd /app/backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

# Start Next.js standalone server in the background on port 3000
echo "Starting Next.js on port 3000..."
cd /app/frontend
PORT=3000 HOSTNAME=127.0.0.1 node server.js &
NEXTJS_PID=$!

# Give services a moment to initialize
sleep 3

echo "FastAPI PID: $UVICORN_PID"
echo "Next.js PID: $NEXTJS_PID"

# Start nginx in the foreground on port 8080 (PID 1 for Cloud Run signal handling)
echo "Starting nginx on port 8080..."
exec nginx -g "daemon off;"
