#!/bin/bash

# ========================================
# Quick Logs Viewer
# ========================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE=$1

if [ -z "$SERVICE" ]; then
    echo "Usage: ./logs.sh [service]"
    echo "Available services: backend, frontend, caddy"
    echo "Or leave empty to view all logs"
    echo ""
    docker compose logs -f
else
    docker compose logs -f $SERVICE
fi
