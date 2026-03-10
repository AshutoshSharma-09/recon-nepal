#!/bin/bash
# Update Deployment Script

# Ensure we are in the project root
# This allows the script to be run from anywhere, but assumes it's in scripts/
cd "$(dirname "$0")/.." || exit

# Check if .env exists, if not, warn
if [ ! -f .env ]; then
    echo "WARNING: .env file not found! Please create one based on .env.example or set environment variables."
fi

# Detect Docker Compose command
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker-compose"
else
    echo "Error: Docker Compose not found. Please install Docker and Docker Compose."
    exit 1
fi

# Determine if sudo is needed
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run with sudo to prevent permission timeouts during long builds."
    echo "Please run: sudo ./scripts/update_deployment.sh"
    exit 1
fi

SUDO=""

# Build and start services (--no-cache ensures fresh rebuild with latest code)
echo "Building and starting services using $DOCKER_COMPOSE_CMD (no cache)..."
$SUDO $DOCKER_COMPOSE_CMD build --no-cache
$SUDO $DOCKER_COMPOSE_CMD up -d

# Restart Nginx to ensure it picks up the new backend IP
echo "Restarting Nginx..."
$SUDO $DOCKER_COMPOSE_CMD restart nginx

# Prune unused images to save space
echo "Pruning unused images..."
$SUDO docker image prune -f

echo "Deployment updated successfully!"
