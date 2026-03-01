#!/bin/bash
#
# 快速部署脚本（简化版）
# Quick Deploy Script
#

SERVER="play.devc.me"
USER="zhuang"
PASSWORD="jy901webyyds"

echo "🚀 开始部署..."

# 上传文件
echo "📤 上传文件..."
cd /Users/max/info-tech/tools
python3 remote_exec.py upload ../backend/api/ws_realtime_routes.py /home/zhuang/info-tech/backend/api/ws_realtime_routes.py
python3 remote_exec.py upload ../backend/main.py /home/zhuang/info-tech/backend/main.py

# 重启服务
echo "🔄 重启服务..."
python3 remote_exec.py exec "pkill -9 -f uvicorn && sleep 2 && cd /home/zhuang/info-tech/backend && nohup ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 </dev/null >/tmp/backend.log 2>&1 &"

sleep 3

# 测试
echo "🧪 测试服务..."
curl -s http://$SERVER:8000/api/health

echo ""
echo "✅ 部署完成！"
echo "查看日志: python3 remote_exec.py exec 'tail -30 /tmp/backend.log'"
