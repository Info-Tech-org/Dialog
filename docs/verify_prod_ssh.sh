#!/bin/bash
# 生产服务器只读验证脚本
# 用法: ./verify_prod_ssh.sh
# 连接时会提示输入密码，请手动输入

set -e
SERVER="ubuntu@43.142.49.126"

echo "连接 $SERVER ... (如需密码请手动输入)"
echo ""

ssh -o StrictHostKeyChecking=no "$SERVER" '
echo "=== 1️⃣ 基本确认 ==="
whoami
hostname
pwd

echo ""
echo "=== 2️⃣ 后端健康检查 ==="
echo "--- HTTP 头 ---"
curl -sS -D - http://127.0.0.1:9000/api/health -o /dev/null | head -n 20
echo "--- 响应体 ---"
curl -sS http://127.0.0.1:9000/api/health
echo ""

echo ""
echo "=== 3️⃣ Docker 状态 ==="
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=== 4️⃣ Backend 最近日志 ==="
CONTAINER=$(sudo docker ps --format "{{.Names}}" | grep -i backend | head -1)
if [ -z "$CONTAINER" ]; then
  CONTAINER=$(sudo docker ps --format "{{.Names}}" | head -1)
fi
echo "容器: $CONTAINER"
sudo docker logs "$CONTAINER" --tail 200 2>/dev/null || echo "无法获取日志"

echo ""
echo "=== 5️⃣ Ingest Token (需手动打码中间6位) ==="
grep DEVICE_INGEST_TOKEN /opt/info-tech/.env 2>/dev/null || true
grep DEVICE_INGEST_TOKEN /opt/info-tech/deploy/.env 2>/dev/null || true
echo "(输出时请将中间6位替换为 ******)"
'
