# =============================================================================
# Stage 1: Build Next.js Frontend
# =============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# Copy package files and install dependencies
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend source code
COPY frontend/ .

# Build the Next.js application (standalone output)
ENV NEXT_PUBLIC_API_URL=""
RUN npm run build

# =============================================================================
# Stage 2: Install Python Backend Dependencies
# =============================================================================
FROM python:3.11-slim AS backend-builder

WORKDIR /app

# Install system dependencies required for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# =============================================================================
# Stage 3: Production Image (nginx + uvicorn in one container)
# =============================================================================
FROM python:3.11-slim AS production

# Install nginx and runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    libpq5 \
    libmagic1 \
    clamav \
    && rm -rf /var/lib/apt/lists/* \
    && freshclam || true

# Copy Python packages from backend-builder
COPY --from=backend-builder /install /usr/local

# ----- Backend -----
WORKDIR /app/backend
COPY backend/ .

# Create uploads directory
RUN mkdir -p /app/uploads

# ----- Frontend (static files) -----
# Copy the standalone Next.js build output
COPY --from=frontend-builder /app/.next/standalone /app/frontend
COPY --from=frontend-builder /app/.next/static /app/frontend/.next/static
COPY --from=frontend-builder /app/public /app/frontend/public

# ----- Nginx -----
# Remove default nginx config
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf

# Copy production nginx config
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# ----- Startup Script -----
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose Cloud Run required port
EXPOSE 8080

# Start both services
CMD ["/app/start.sh"]
