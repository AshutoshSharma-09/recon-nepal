#!/bin/bash
set -e

echo "=== Starting Recon PMS Container ==="

# Start uvicorn (FastAPI) in the background on port 8000
echo "Starting FastAPI (uvicorn) on port 8000..."
cd /app/backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info 2>&1 &
UVICORN_PID=$!

# Start Next.js standalone server in the background on port 3000
echo "Starting Next.js on port 3000..."
cd /app/frontend
PORT=3000 HOSTNAME=127.0.0.1 node server.js 2>&1 &
NEXTJS_PID=$!

# Wait for uvicorn — the DB retry loop can take up to 15+ seconds
echo "Waiting for services to start (up to 30s)..."
for i in $(seq 1 30); do
    # Check if uvicorn process is still alive
    if ! kill -0 $UVICORN_PID 2>/dev/null; then
        echo "ERROR: uvicorn crashed! (PID $UVICORN_PID exited after ${i}s)"
        echo "Restarting uvicorn with debug logging..."
        cd /app/backend
        uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level debug 2>&1 &
        UVICORN_PID=$!
        sleep 10
        break
    fi
    # Check if port 8000 is accepting connections
    if curl -s -o /dev/null http://127.0.0.1:8000/health 2>/dev/null; then
        echo "uvicorn is ready on port 8000 (after ${i}s)"
        break
    fi
    sleep 1
done

# Final status check
if ! kill -0 $UVICORN_PID 2>/dev/null; then
    echo "FATAL: uvicorn is not running. API requests will return 502."
else
    echo "FastAPI PID: $UVICORN_PID (alive)"
fi

if ! kill -0 $NEXTJS_PID 2>/dev/null; then
    echo "FATAL: Next.js is not running. Frontend requests will return 502."
else
    echo "Next.js PID: $NEXTJS_PID (alive)"
fi

# Start nginx in the foreground on port 8080 (PID 1 for Cloud Run signal handling)
echo "Starting nginx on port 8080..."
exec nginx -g "daemon off;"
