#!/bin/bash
set -e

# Start uvicorn (FastAPI) in the background
echo "Starting uvicorn on port 8000..."
cd /app/backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 &

# Start Next.js standalone server in the background
echo "Starting Next.js on port 3000..."
cd /app/frontend
node server.js &

# Give services a moment to start
sleep 2

# Start nginx in the foreground (PID 1 for proper signal handling)
echo "Starting nginx on port 8080..."
exec nginx -g "daemon off;"
