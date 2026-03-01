#!/bin/bash

# ========================================
# Quick Update Script
# ========================================
# Updates code and restarts services

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Updating Family Emotion System${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Pull latest code
echo -e "${YELLOW}[1/3] Pulling latest code...${NC}"
git pull origin master
echo -e "${GREEN}✅ Code updated${NC}"

# Rebuild and restart
echo -e "${YELLOW}[2/3] Rebuilding containers...${NC}"
cd deploy
docker compose up -d --build
echo -e "${GREEN}✅ Containers rebuilt${NC}"

# Show status
echo -e "${YELLOW}[3/3] Checking status...${NC}"
sleep 5
docker compose ps
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Update Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}View logs: ${BLUE}docker compose logs -f${NC}"
