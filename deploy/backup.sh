#!/bin/bash

# ========================================
# Database Backup Script
# ========================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BACKUP_DIR="$SCRIPT_DIR/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.tar.gz"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo -e "${BLUE}Creating backup...${NC}"

# Backup database and audio files
docker compose exec -T backend tar -czf - /app/data /app/audio 2>/dev/null > "$BACKUP_FILE"

echo -e "${GREEN}✅ Backup created: $BACKUP_FILE${NC}"
echo -e "${BLUE}Size: $(du -h "$BACKUP_FILE" | cut -f1)${NC}"

# Keep only last 7 backups
cd "$BACKUP_DIR"
ls -t backup_*.tar.gz | tail -n +8 | xargs -r rm
echo -e "${GREEN}✅ Old backups cleaned${NC}"
