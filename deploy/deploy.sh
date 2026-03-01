#!/bin/bash

# ========================================
# Family Emotion System - Deployment Script
# ========================================
# This script automates the deployment process on Ubuntu 24.04

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Server info
SERVER_IP="47.236.106.225"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Family Emotion System - Auto Deploy${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}❌ Please do not run as root. Use sudo when needed.${NC}"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Install Docker if not present
echo -e "${YELLOW}[1/7] Checking Docker installation...${NC}"
if ! command_exists docker; then
    echo -e "${GREEN}Installing Docker...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${GREEN}✅ Docker installed successfully${NC}"
else
    echo -e "${GREEN}✅ Docker already installed${NC}"
fi

# Step 2: Install Docker Compose if not present
echo -e "${YELLOW}[2/7] Checking Docker Compose installation...${NC}"
if ! command_exists docker-compose && ! docker compose version >/dev/null 2>&1; then
    echo -e "${GREEN}Installing Docker Compose...${NC}"
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}✅ Docker Compose installed successfully${NC}"
else
    echo -e "${GREEN}✅ Docker Compose already installed${NC}"
fi

# Step 3: Navigate to deploy directory
echo -e "${YELLOW}[3/7] Navigating to deploy directory...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo -e "${GREEN}✅ Current directory: $(pwd)${NC}"

# Step 4: Setup environment variables
echo -e "${YELLOW}[4/7] Setting up environment variables...${NC}"
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}⚠️  Created .env from .env.example${NC}"
        echo -e "${RED}⚠️  IMPORTANT: Please edit .env file and add your API keys!${NC}"
        echo -e "${YELLOW}Run: nano .env${NC}"
        echo ""
        read -p "Press Enter after you've configured .env file..."
    else
        echo -e "${RED}❌ .env.example not found!${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi

# Step 5: Stop existing containers
echo -e "${YELLOW}[5/7] Stopping existing containers...${NC}"
docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true
echo -e "${GREEN}✅ Containers stopped${NC}"

# Step 6: Build and start services
echo -e "${YELLOW}[6/7] Building and starting services...${NC}"
echo -e "${BLUE}This may take 5-10 minutes for the first build...${NC}"

if docker compose version >/dev/null 2>&1; then
    docker compose up -d --build
else
    docker-compose up -d --build
fi

echo -e "${GREEN}✅ Services started successfully${NC}"

# Step 7: Wait for services to be healthy
echo -e "${YELLOW}[7/7] Waiting for services to be healthy...${NC}"
sleep 10

# Check service status
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Service Status:${NC}"
echo -e "${BLUE}========================================${NC}"
if docker compose version >/dev/null 2>&1; then
    docker compose ps
else
    docker-compose ps
fi

# Display access information
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Access your application at:${NC}"
echo -e "  ${GREEN}➜ HTTPS: https://${SERVER_IP}${NC}"
echo -e "  ${GREEN}➜ HTTP:  http://${SERVER_IP}${NC}"
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo -e "  View logs:      ${BLUE}docker compose logs -f${NC}"
echo -e "  Restart:        ${BLUE}docker compose restart${NC}"
echo -e "  Stop:           ${BLUE}docker compose down${NC}"
echo -e "  Update & restart: ${BLUE}git pull && docker compose up -d --build${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. Check logs: ${BLUE}docker compose logs -f backend${NC}"
echo -e "  2. Access the web interface at: ${GREEN}https://${SERVER_IP}${NC}"
echo -e "  3. Create admin user if needed (see README_DEPLOY.md)"
echo ""

# Optional: Show logs
read -p "Do you want to view logs now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if docker compose version >/dev/null 2>&1; then
        docker compose logs -f
    else
        docker-compose logs -f
    fi
fi
