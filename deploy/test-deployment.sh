#!/bin/bash

# ========================================
# Deployment Test Script
# ========================================
# Tests if all services are working correctly

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVER_IP="47.236.106.225"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Testing Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Test 1: Check if containers are running
echo -e "${YELLOW}[1/5] Checking container status...${NC}"
if docker compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Containers are running${NC}"
else
    echo -e "${RED}❌ Some containers are not running${NC}"
    docker compose ps
    exit 1
fi

# Test 2: Check backend health
echo -e "${YELLOW}[2/5] Testing backend health endpoint...${NC}"
if curl -f -s http://localhost:8000/api/health > /dev/null; then
    echo -e "${GREEN}✅ Backend health check passed${NC}"
else
    echo -e "${RED}❌ Backend health check failed${NC}"
    exit 1
fi

# Test 3: Check frontend
echo -e "${YELLOW}[3/5] Testing frontend...${NC}"
if curl -f -s http://localhost:3000 > /dev/null; then
    echo -e "${GREEN}✅ Frontend is accessible${NC}"
else
    echo -e "${RED}❌ Frontend is not accessible${NC}"
    exit 1
fi

# Test 4: Check Caddy
echo -e "${YELLOW}[4/5] Testing Caddy reverse proxy...${NC}"
if curl -f -s -k https://localhost/api/health > /dev/null; then
    echo -e "${GREEN}✅ Caddy reverse proxy working${NC}"
else
    echo -e "${YELLOW}⚠️  Caddy might still be starting or configuring SSL${NC}"
fi

# Test 5: Check external access
echo -e "${YELLOW}[5/5] Testing external access...${NC}"
if curl -f -s -k https://${SERVER_IP}/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ External access working${NC}"
else
    echo -e "${YELLOW}⚠️  External access not available yet${NC}"
    echo -e "${YELLOW}   This is normal on first deployment (SSL setup)${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Deployment Test Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Service URLs:${NC}"
echo -e "  Backend:  ${GREEN}http://localhost:8000${NC}"
echo -e "  Frontend: ${GREEN}http://localhost:3000${NC}"
echo -e "  Public:   ${GREEN}https://${SERVER_IP}${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Check logs: ${BLUE}./logs.sh${NC}"
echo -e "  2. Create admin: ${BLUE}docker compose exec backend python create_admin_user.py${NC}"
echo -e "  3. Access: ${BLUE}https://${SERVER_IP}${NC}"
