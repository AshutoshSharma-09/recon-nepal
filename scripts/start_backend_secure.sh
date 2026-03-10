#!/bin/bash
# Secure Startup Script for PMS-RECON Backend
# Binds to localhost only to ensure NGINX proxy usage.

# Ensure strict secrets
if [ -z "$DATABASE_URL" ] || [ -z "$API_KEYS" ]; then
  echo "CRITICAL: Required environment variables are missing!"
  exit 1
fi

# Run Gunicorn with Uvicorn workers
# Binding to 127.0.0.1 ONLY (No public exposure)
exec gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
