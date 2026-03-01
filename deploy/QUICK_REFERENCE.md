# 快速参考 - 常用命令

## 🚀 部署命令

```bash
# 首次部署
cd /opt/info-tech/deploy
./deploy.sh

# 更新代码并重新部署
./update.sh

# 测试部署是否成功
./test-deployment.sh
```

## 📊 服务管理

```bash
# 查看服务状态
docker compose ps

# 启动所有服务
docker compose up -d

# 停止所有服务
docker compose down

# 重启所有服务
docker compose restart

# 重启单个服务
docker compose restart backend
docker compose restart frontend
docker compose restart caddy
```

## 📝 日志查看

```bash
# 查看所有日志
./logs.sh

# 查看特定服务日志
./logs.sh backend
./logs.sh frontend
./logs.sh caddy

# 或直接使用 docker compose
docker compose logs -f
docker compose logs -f backend
docker compose logs -f --tail=100 backend
```

## 💾 数据备份

```bash
# 创建备份
./backup.sh

# 备份文件位置
ls backups/

# 手动备份
docker compose exec backend tar -czf /tmp/backup.tar.gz /app/data
docker cp family-backend:/tmp/backup.tar.gz ./backup-$(date +%Y%m%d).tar.gz
```

## 👤 用户管理

```bash
# 创建管理员账户
docker compose exec backend python create_admin_user.py

# 快速创建管理员
docker compose exec backend python simple_create_admin.py

# 查看所有用户
docker compose exec backend python check_users.py

# 创建普通用户
docker compose exec backend python create_user_direct.py
```

## 🔧 维护命令

```bash
# 重建所有镜像
docker compose up -d --build

# 只重建后端
docker compose up -d --build backend

# 进入容器 shell
docker compose exec backend bash
docker compose exec frontend sh

# 查看容器资源使用
docker stats

# 清理未使用的镜像
docker image prune -a -f

# 查看磁盘使用
docker system df
```

## 🌐 网络测试

```bash
# 测试后端健康检查
curl http://localhost:8000/api/health

# 测试前端
curl http://localhost:3000

# 测试外部访问
curl -k https://47.236.106.225/api/health

# 测试 WebSocket
wscat -c ws://localhost:8000/ws
```

## 📦 环境变量

```bash
# 查看当前环境变量
docker compose exec backend env | grep COS
docker compose exec backend env | grep JWT

# 修改环境变量
nano .env
docker compose restart backend
```

## 🔍 故障排查

```bash
# 检查容器状态
docker compose ps

# 查看容器详细信息
docker inspect family-backend

# 查看最近的错误日志
docker compose logs --tail=50 backend | grep ERROR

# 重启服务
docker compose restart

# 完全重建
docker compose down
docker compose up -d --build
```

## 📊 监控命令

```bash
# 实时资源使用
docker stats

# 查看容器日志大小
docker ps -a --format "table {{.Names}}\t{{.Size}}"

# 查看网络连接
docker compose exec backend netstat -tuln

# 查看进程
docker compose exec backend ps aux
```

## 🔐 安全检查

```bash
# 检查开放端口
ss -tuln | grep LISTEN

# 查看防火墙状态
sudo ufw status

# 查看 SSL 证书
docker compose exec caddy caddy list-certificates

# 查看 Caddy 配置
docker compose exec caddy cat /etc/caddy/Caddyfile
```

## 📈 性能优化

```bash
# 查看数据库大小
docker compose exec backend ls -lh /app/data/

# 清理数据库（谨慎使用）
docker compose exec backend sqlite3 /app/data/family.db "VACUUM;"

# 查看 Nginx 配置
docker compose exec frontend cat /etc/nginx/conf.d/default.conf
```

## 🎯 快捷操作

```bash
# 一键重启
docker compose restart

# 一键查看所有日志
docker compose logs -f

# 一键更新
git pull && docker compose up -d --build

# 一键备份
./backup.sh

# 一键测试
./test-deployment.sh
```

## 📞 紧急操作

```bash
# 立即停止所有服务
docker compose down

# 强制停止容器
docker stop family-backend family-frontend family-caddy

# 查看系统资源
htop
df -h
free -m

# 重启 Docker 服务
sudo systemctl restart docker
```

## 🔗 有用的路径

```bash
# 项目根目录
cd /opt/info-tech

# 部署目录
cd /opt/info-tech/deploy

# 后端代码
cd /opt/info-tech/backend

# 前端代码
cd /opt/info-tech/frontend

# 备份目录
cd /opt/info-tech/deploy/backups
```

## 📱 访问地址

- **生产环境**: https://47.236.106.225
- **后端 API**: https://47.236.106.225/api
- **健康检查**: https://47.236.106.225/api/health
- **WebSocket**: wss://47.236.106.225/ws

## 📞 支持

遇到问题？
1. 查看日志: `./logs.sh`
2. 运行测试: `./test-deployment.sh`
3. 查看文档: `cat README_DEPLOY.md`
4. 检查容器: `docker compose ps`
