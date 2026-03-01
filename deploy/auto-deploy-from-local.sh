#!/bin/bash

# ========================================
# 一键自动部署脚本（从本地执行）
# ========================================
# 这个脚本会从你的本地电脑自动部署到服务器

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVER_IP="47.236.106.225"
SERVER_USER="root"
SERVER_PASSWORD="Mp2,nj!uC#tR,!Y"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}家庭情绪系统 - 一键自动部署${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: 打包项目
echo -e "${YELLOW}[1/8] 打包项目文件...${NC}"
cd "$(dirname "$0")/.."
tar --exclude='node_modules' --exclude='.git' --exclude='backend/data' \
    --exclude='*.pyc' --exclude='__pycache__' --exclude='frontend/dist' \
    -czf /tmp/info-tech-deploy.tar.gz .
echo -e "${GREEN}✅ 项目已打包${NC}"

# Step 2: 上传到服务器
echo -e "${YELLOW}[2/8] 上传到服务器...${NC}"
sshpass -p "$SERVER_PASSWORD" scp -o StrictHostKeyChecking=no \
    /tmp/info-tech-deploy.tar.gz ${SERVER_USER}@${SERVER_IP}:/tmp/
echo -e "${GREEN}✅ 文件已上传${NC}"

# Step 3: 在服务器上解压并配置
echo -e "${YELLOW}[3/8] 解压并配置...${NC}"
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no \
    ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
# 创建目录
mkdir -p /opt/info-tech
cd /opt/info-tech

# 解压
tar -xzf /tmp/info-tech-deploy.tar.gz
rm /tmp/info-tech-deploy.tar.gz

echo "✅ 项目已解压到 /opt/info-tech"
ENDSSH
echo -e "${GREEN}✅ 项目已配置${NC}"

# Step 4: 配置环境变量
echo -e "${YELLOW}[4/8] 配置环境变量...${NC}"
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no \
    ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /opt/info-tech/deploy

# 生成 JWT Secret
JWT_SECRET=$(openssl rand -base64 32)

# 创建 .env 文件
cat > .env << 'EOF'
# Tencent Cloud COS
COS_SECRET_ID=YOUR_COS_SECRET_ID
COS_SECRET_KEY=YOUR_COS_SECRET_KEY
COS_BUCKET=your-bucket-name
COS_REGION=ap-guangzhou

# Tencent Cloud ASR
TENCENT_SECRET_ID=YOUR_TENCENT_SECRET_ID
TENCENT_SECRET_KEY=YOUR_TENCENT_SECRET_KEY
TENCENT_ASR_REGION=ap-guangzhou

# OpenRouter API
OPENROUTER_API_KEY=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
OPENROUTER_MODEL=google/gemma-2-27b-it

# JWT Authentication
EOF

echo "JWT_SECRET=${JWT_SECRET}" >> .env

cat >> .env << 'EOF'
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=43200

# Database
DATABASE_URL=sqlite:///./data/family.db

# Application
APP_NAME=Family Emotion System
APP_VERSION=1.0.0
DEBUG=false
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=https://47.236.106.225,http://47.236.106.225,http://localhost:3000

# File Upload
MAX_UPLOAD_SIZE=104857600
ALLOWED_AUDIO_FORMATS=m4a,mp3,wav,flac

# Audio Storage
AUDIO_UPLOAD_DIR=/app/audio/uploads
EOF

echo "✅ 环境变量已配置"
cat .env
ENDSSH
echo -e "${GREEN}✅ 环境变量已创建${NC}"

# Step 5: 安装 Docker
echo -e "${YELLOW}[5/8] 安装 Docker 和 Docker Compose...${NC}"
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no \
    ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "安装 Docker..."
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh
    rm /tmp/get-docker.sh
    echo "✅ Docker 已安装"
else
    echo "✅ Docker 已存在"
fi

# 检查 Docker Compose
if ! docker compose version &> /dev/null; then
    echo "安装 Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose 已安装"
else
    echo "✅ Docker Compose 已存在"
fi
ENDSSH
echo -e "${GREEN}✅ Docker 环境已准备${NC}"

# Step 6: 构建并启动服务
echo -e "${YELLOW}[6/8] 构建并启动服务（需要 5-10 分钟）...${NC}"
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no \
    ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /opt/info-tech/deploy

# 赋予脚本执行权限
chmod +x *.sh

# 停止旧容器（如果有）
docker compose down 2>/dev/null || true

# 构建并启动
echo "开始构建镜像..."
docker compose up -d --build

echo "等待服务启动..."
sleep 15
ENDSSH
echo -e "${GREEN}✅ 服务已启动${NC}"

# Step 7: 检查状态
echo -e "${YELLOW}[7/8] 检查服务状态...${NC}"
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no \
    ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /opt/info-tech/deploy
docker compose ps
ENDSSH

# Step 8: 创建管理员账户
echo -e "${YELLOW}[8/8] 创建管理员账户...${NC}"
sshpass -p "$SERVER_PASSWORD" ssh -o StrictHostKeyChecking=no \
    ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
cd /opt/info-tech/deploy

# 创建默认管理员
docker compose exec -T backend python -c "
from models import User, engine
from sqlmodel import Session, select
from api.auth import get_password_hash

with Session(engine) as db:
    # 检查是否已存在
    existing = db.exec(select(User).where(User.username == 'admin')).first()
    if not existing:
        admin = User(
            username='admin',
            hashed_password=get_password_hash('Admin123!')
        )
        db.add(admin)
        db.commit()
        print('✅ 管理员账户已创建')
        print('   用户名: admin')
        print('   密码: Admin123!')
    else:
        print('✅ 管理员账户已存在')
"
ENDSSH

# 完成
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}访问地址：${NC}"
echo -e "  ${GREEN}➜ https://${SERVER_IP}${NC}"
echo -e "  ${GREEN}➜ http://${SERVER_IP}${NC}"
echo ""
echo -e "${BLUE}管理员账户：${NC}"
echo -e "  ${YELLOW}用户名: admin${NC}"
echo -e "  ${YELLOW}密码: Admin123!${NC}"
echo ""
echo -e "${YELLOW}常用命令（SSH 到服务器后）：${NC}"
echo -e "  ${BLUE}cd /opt/info-tech/deploy${NC}"
echo -e "  ${BLUE}./logs.sh              # 查看日志${NC}"
echo -e "  ${BLUE}docker compose ps      # 查看状态${NC}"
echo -e "  ${BLUE}docker compose restart # 重启服务${NC}"
echo ""
