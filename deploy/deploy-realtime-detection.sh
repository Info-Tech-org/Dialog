#!/bin/bash
#
# 部署实时语音识别 + 有害检测功能到服务器
# Deploy Realtime ASR + Harmful Detection to Server
#
# 使用方法: ./deploy-realtime-detection.sh
#

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
SERVER="play.devc.me"
USER="zhuang"
PASSWORD="jy901webyyds"
REMOTE_DIR="/home/zhuang/info-tech/backend"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}部署实时检测功能到服务器${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 sshpass 是否安装
if ! command -v sshpass &> /dev/null; then
    echo -e "${YELLOW}⚠️  sshpass 未安装，正在安装...${NC}"
    brew install hudochenkov/sshpass/sshpass
    echo -e "${GREEN}✅ sshpass 安装完成${NC}"
fi

# 测试连接
echo -e "${BLUE}📡 测试服务器连接...${NC}"
if sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 $USER@$SERVER "echo 'Connection test'" &> /dev/null; then
    echo -e "${GREEN}✅ 服务器连接成功${NC}"
else
    echo -e "${RED}❌ 无法连接到服务器，请检查：${NC}"
    echo -e "${RED}   1. 服务器是否在线${NC}"
    echo -e "${RED}   2. SSH 服务是否运行${NC}"
    echo -e "${RED}   3. 网络是否通畅${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}📦 准备上传文件...${NC}"

# 1. 上传新的 WebSocket 实时路由文件
echo -e "${YELLOW}上传 ws_realtime_routes.py...${NC}"
sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no \
    /Users/max/info-tech/backend/api/ws_realtime_routes.py \
    $USER@$SERVER:$REMOTE_DIR/api/ws_realtime_routes.py
echo -e "${GREEN}✅ ws_realtime_routes.py 上传完成${NC}"

# 2. 上传更新的 main.py
echo -e "${YELLOW}上传 main.py...${NC}"
sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no \
    /Users/max/info-tech/backend/main.py \
    $USER@$SERVER:$REMOTE_DIR/main.py
echo -e "${GREEN}✅ main.py 上传完成${NC}"

# 3. 检查文件是否上传成功
echo ""
echo -e "${BLUE}🔍 验证文件上传...${NC}"
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $USER@$SERVER << 'EOF'
cd /home/zhuang/info-tech/backend
if [ -f "api/ws_realtime_routes.py" ]; then
    echo "✅ ws_realtime_routes.py 存在"
    ls -lh api/ws_realtime_routes.py
else
    echo "❌ ws_realtime_routes.py 不存在"
    exit 1
fi

if [ -f "main.py" ]; then
    echo "✅ main.py 存在"
    ls -lh main.py
else
    echo "❌ main.py 不存在"
    exit 1
fi
EOF

# 4. 检查 Python 语法
echo ""
echo -e "${BLUE}🔍 检查 Python 语法...${NC}"
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $USER@$SERVER << 'EOF'
cd /home/zhuang/info-tech/backend
./venv/bin/python -m py_compile api/ws_realtime_routes.py
if [ $? -eq 0 ]; then
    echo "✅ ws_realtime_routes.py 语法正确"
else
    echo "❌ ws_realtime_routes.py 语法错误"
    exit 1
fi

./venv/bin/python -m py_compile main.py
if [ $? -eq 0 ]; then
    echo "✅ main.py 语法正确"
else
    echo "❌ main.py 语法错误"
    exit 1
fi
EOF

# 5. 重启后端服务
echo ""
echo -e "${BLUE}🔄 重启后端服务...${NC}"
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $USER@$SERVER << 'EOF'
# 杀死现有的 uvicorn 进程
echo "停止现有服务..."
pkill -9 -f "uvicorn main:app" || echo "没有运行中的服务"

sleep 2

# 启动新服务
echo "启动新服务..."
cd /home/zhuang/info-tech/backend
nohup ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 </dev/null >/tmp/backend.log 2>&1 &

sleep 3

# 检查进程是否启动
if pgrep -f "uvicorn main:app" > /dev/null; then
    echo "✅ 服务启动成功"
    pgrep -f "uvicorn main:app"
else
    echo "❌ 服务启动失败，查看日志:"
    tail -30 /tmp/backend.log
    exit 1
fi
EOF

# 6. 测试 API 端点
echo ""
echo -e "${BLUE}🧪 测试 API 端点...${NC}"

sleep 2

# 测试健康检查
echo -e "${YELLOW}测试 /api/health...${NC}"
HEALTH_RESPONSE=$(curl -s http://$SERVER:8000/api/health)
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo -e "${GREEN}✅ 健康检查通过: $HEALTH_RESPONSE${NC}"
else
    echo -e "${RED}❌ 健康检查失败${NC}"
fi

# 测试 WebSocket 路由是否注册
echo -e "${YELLOW}测试 /docs (查看 API 文档)...${NC}"
DOCS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://$SERVER:8000/docs)
if [ "$DOCS_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ API 文档可访问 (HTTP $DOCS_STATUS)${NC}"
    echo -e "${GREEN}   查看文档: http://$SERVER:8000/docs${NC}"
else
    echo -e "${RED}❌ API 文档访问失败 (HTTP $DOCS_STATUS)${NC}"
fi

# 7. 查看服务日志
echo ""
echo -e "${BLUE}📋 查看服务日志（最后 20 行）...${NC}"
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $USER@$SERVER \
    "tail -20 /tmp/backend.log"

# 完成
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📍 服务信息:${NC}"
echo -e "   网站: http://$SERVER:8000/"
echo -e "   API 文档: http://$SERVER:8000/docs"
echo -e "   实时检测 WebSocket: ws://$SERVER:8000/ws/realtime/stream"
echo ""
echo -e "${BLUE}📝 下一步:${NC}"
echo -e "   1. 查看 API 文档: http://$SERVER:8000/docs"
echo -e "   2. 测试实时检测:"
echo -e "      ${YELLOW}python3 tools/test_realtime_detection.py --url ws://$SERVER:8000${NC}"
echo ""
echo -e "${BLUE}📊 监控命令:${NC}"
echo -e "   查看日志: ${YELLOW}ssh $USER@$SERVER 'tail -f /tmp/backend.log'${NC}"
echo -e "   查看进程: ${YELLOW}ssh $USER@$SERVER 'ps aux | grep uvicorn'${NC}"
echo -e "   活跃会话: ${YELLOW}curl http://$SERVER:8000/ws/realtime/active${NC}"
echo ""
