#!/bin/bash
set -e

echo "=== Starting Recon PMS Container ==="

# Start uvicorn (FastAPI) in the background on port 8000
# Redirect stderr to stdout so Cloud Run captures all logs
echo "Starting FastAPI (uvicorn) on port 8000..."
cd /app/backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 2>&1 &
UVICORN_PID=$!

# Start Next.js standalone server in the background on port 3000
echo "Starting Next.js on port 3000..."
cd /app/frontend
PORT=3000 HOSTNAME=127.0.0.1 node server.js 2>&1 &
NEXTJS_PID=$!

# Wait for services to initialize and verify they're running
echo "Waiting for services to start..."
sleep 5

# Check if uvicorn is still running
if ! kill -0 $UVICORN_PID 2>/dev/null; then
    echo "ERROR: uvicorn (FastAPI) failed to start! PID $UVICORN_PID is dead."
    echo "Attempting to start uvicorn again with verbose logging..."
    cd /app/backend
    uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level debug 2>&1 &
    UVICORN_PID=$!
    sleep 5
    if ! kill -0 $UVICORN_PID 2>/dev/null; then
        echo "FATAL: uvicorn failed to start on second attempt. Check database connection and imports."
    fi
fi

# Check if Next.js is still running
if ! kill -0 $NEXTJS_PID 2>/dev/null; then
    echo "ERROR: Next.js failed to start! PID $NEXTJS_PID is dead."
fi

echo "FastAPI PID: $UVICORN_PID"
echo "Next.js PID: $NEXTJS_PID"

# Start nginx in the foreground on port 8080 (PID 1 for Cloud Run signal handling)
echo "Starting nginx on port 8080..."
exec nginx -g "daemon off;"
