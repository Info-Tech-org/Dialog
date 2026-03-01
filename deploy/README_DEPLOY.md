# 家庭情绪系统 - 生产部署指南

## 📋 目录结构

```
/deploy
├── docker-compose.yml        # Docker Compose 编排文件
├── backend.Dockerfile        # 后端 Docker 镜像
├── frontend.Dockerfile       # 前端 Docker 镜像
├── nginx-frontend.conf       # 前端 Nginx 配置
├── Caddyfile                 # Caddy 反向代理配置（自动 HTTPS）
├── .env.example              # 环境变量模板
├── deploy.sh                 # 一键部署脚本
└── README_DEPLOY.md          # 本文档
```

## 🚀 快速部署

### 前置条件

- ✅ 服务器：阿里云 ECS (Ubuntu 24.04 LTS)
- ✅ 公网 IP：47.236.106.225
- ✅ 开放端口：80, 443 (需在阿里云安全组配置)

### 步骤 1: 连接服务器

```bash
ssh root@47.236.106.225
# 密码：Mp2,nj!uC#tR,!Y
```

### 步骤 2: 克隆项目

```bash
# 安装 Git（如果未安装）
apt update && apt install -y git

# 克隆项目
cd /opt
git clone <your-repo-url> info-tech
cd info-tech/deploy
```

### 步骤 3: 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量（填入真实的 API Keys）
nano .env
```

**必须配置的变量：**
```bash
# 腾讯云 COS（对象存储）
COS_SECRET_ID=<你的 COS Secret ID>
COS_SECRET_KEY=<你的 COS Secret Key>
COS_BUCKET=<你的 Bucket 名称>
COS_REGION=ap-guangzhou

# 腾讯云 ASR（语音识别）
TENCENT_SECRET_ID=<你的腾讯云 Secret ID>
TENCENT_SECRET_KEY=<你的腾讯云 Secret Key>

# OpenRouter（LLM 检测）
OPENROUTER_API_KEY=<你的 OpenRouter API Key>

# JWT 认证（生成一个随机字符串）
JWT_SECRET=<生成一个至少 32 位的随机字符串>
```

**生成随机 JWT Secret：**
```bash
openssl rand -base64 32
```

### 步骤 4: 运行部署脚本

```bash
# 赋予执行权限
chmod +x deploy.sh

# 执行部署
./deploy.sh
```

部署脚本会自动：
1. ✅ 安装 Docker 和 Docker Compose
2. ✅ 构建所有镜像
3. ✅ 启动所有服务
4. ✅ 配置自动重启
5. ✅ 显示访问链接

### 步骤 5: 访问应用

部署完成后，访问：
- **HTTPS**: https://47.236.106.225
- **HTTP**: http://47.236.106.225 (会自动重定向到 HTTPS)

---

## 🔧 服务管理

### 查看服务状态

```bash
cd /opt/info-tech/deploy
docker compose ps
```

### 查看日志

```bash
# 查看所有服务日志
docker compose logs -f

# 只看后端日志
docker compose logs -f backend

# 只看前端日志
docker compose logs -f frontend

# 只看 Caddy 日志
docker compose logs -f caddy
```

### 重启服务

```bash
# 重启所有服务
docker compose restart

# 重启单个服务
docker compose restart backend
docker compose restart frontend
```

### 停止服务

```bash
docker compose down
```

### 启动服务

```bash
docker compose up -d
```

---

## 🔄 更新代码

当你更新了代码后，重新部署：

```bash
cd /opt/info-tech

# 拉取最新代码
git pull origin master

# 进入 deploy 目录
cd deploy

# 重新构建并启动
docker compose up -d --build

# 查看日志确认
docker compose logs -f
```

---

## 👤 创建管理员账户

第一次部署后需要创建管理员账户：

```bash
# 进入后端容器
docker compose exec backend python create_admin_user.py

# 或者使用简化版
docker compose exec backend python simple_create_admin.py
```

按提示输入用户名和密码。

---

## 🌐 添加域名（可选）

### 步骤 1: 配置 DNS

在你的域名提供商处，添加 A 记录：
```
A    @    47.236.106.225
A    www  47.236.106.225
```

### 步骤 2: 修改 Caddyfile

编辑 `deploy/Caddyfile`：

```bash
nano Caddyfile
```

将 `47.236.106.225` 替换为你的域名：

```caddyfile
# 原来：
47.236.106.225 {
    ...
}

# 改为：
yourdomain.com {
    ...
}

# 添加 www 重定向
www.yourdomain.com {
    redir https://yourdomain.com{uri} permanent
}
```

### 步骤 3: 重启 Caddy

```bash
docker compose restart caddy
```

Caddy 会自动申请 Let's Encrypt SSL 证书。

---

## 🔍 故障排查

### 问题 1: 无法访问

**检查防火墙：**
```bash
# 阿里云控制台 → 安全组 → 添加规则
# 允许入方向：80/443 端口
```

**检查服务状态：**
```bash
docker compose ps
# 确保所有服务都是 "Up" 状态
```

### 问题 2: 后端启动失败

**查看日志：**
```bash
docker compose logs backend
```

**常见原因：**
- ❌ .env 文件未配置
- ❌ API Keys 错误
- ❌ 数据库权限问题

**解决方案：**
```bash
# 检查环境变量
docker compose exec backend env | grep COS

# 手动创建数据库目录
docker compose exec backend mkdir -p /app/data

# 重启后端
docker compose restart backend
```

### 问题 3: 前端无法访问后端 API

**检查 Caddy 配置：**
```bash
docker compose logs caddy
```

**测试后端连接：**
```bash
curl http://localhost:8000/api/sessions
```

### 问题 4: HTTPS 证书问题

Caddy 会自动申请证书，但需要：
- ✅ 域名已正确解析到服务器 IP
- ✅ 80 和 443 端口已开放
- ✅ Caddyfile 中 email 已配置

**查看证书状态：**
```bash
docker compose exec caddy caddy list-certificates
```

---

## 🧹 清理与维护

### 清理未使用的镜像

```bash
# 清理悬空镜像
docker image prune -f

# 清理所有未使用的镜像
docker image prune -a -f
```

### 清理容器

```bash
# 清理停止的容器
docker container prune -f
```

### 清理数据卷（慎用！会删除数据）

```bash
# 列出所有卷
docker volume ls

# 删除特定卷
docker volume rm deploy_backend-data

# 清理未使用的卷
docker volume prune -f
```

### 备份数据库

```bash
# 备份 SQLite 数据库
docker compose exec backend tar -czf /tmp/backup.tar.gz /app/data
docker cp family-backend:/tmp/backup.tar.gz ./backup-$(date +%Y%m%d).tar.gz
```

### 恢复数据库

```bash
# 解压备份
tar -xzf backup-20241203.tar.gz

# 复制回容器
docker cp app/data family-backend:/app/

# 重启服务
docker compose restart backend
```

---

## 📊 监控与日志

### 实时监控资源使用

```bash
# 查看容器资源使用
docker stats

# 查看磁盘使用
df -h

# 查看 Docker 磁盘使用
docker system df
```

### 日志轮转

Docker 默认会记录所有日志，可能占用大量空间。建议配置日志轮转：

编辑 `/etc/docker/daemon.json`：
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

重启 Docker：
```bash
systemctl restart docker
```

---

## 🔐 安全建议

1. **修改默认密码**
   - 修改服务器 root 密码
   - 创建非 root 用户进行操作

2. **配置防火墙**
   ```bash
   # 安装 ufw
   apt install ufw

   # 允许 SSH
   ufw allow 22

   # 允许 HTTP/HTTPS
   ufw allow 80
   ufw allow 443

   # 启用防火墙
   ufw enable
   ```

3. **定期更新**
   ```bash
   # 更新系统
   apt update && apt upgrade -y

   # 更新 Docker 镜像
   docker compose pull
   docker compose up -d
   ```

4. **配置自动备份**
   创建 cron 任务自动备份数据库：
   ```bash
   # 编辑 crontab
   crontab -e

   # 添加每天凌晨 3 点备份
   0 3 * * * cd /opt/info-tech/deploy && docker compose exec backend tar -czf /tmp/backup-$(date +\%Y\%m\%d).tar.gz /app/data
   ```

---

## 📞 技术支持

### 服务架构

```
Internet
   ↓
Caddy (443) → HTTPS 自动证书
   ├─→ /api/* → Backend (FastAPI:8000)
   ├─→ /ws/*  → Backend (WebSocket)
   └─→ /*     → Frontend (Nginx:80)
```

### 服务说明

| 服务 | 容器名 | 端口 | 作用 |
|------|--------|------|------|
| backend | family-backend | 8000 | FastAPI 后端 API |
| frontend | family-frontend | 80 | React 前端静态文件 |
| caddy | family-caddy | 80/443 | 反向代理 + HTTPS |

### 数据持久化

| 卷名 | 映射路径 | 说明 |
|------|----------|------|
| backend-data | /app/data | SQLite 数据库 |
| backend-audio | /app/audio | 上传的音频文件 |
| caddy-data | /data | Caddy 数据（证书等） |
| caddy-config | /config | Caddy 配置 |

---

## 📝 常见任务

### 添加新用户

```bash
docker compose exec backend python create_user_direct.py
```

### 查看所有用户

```bash
docker compose exec backend python check_users.py
```

### 测试有害内容检测

```bash
docker compose exec backend python test_harmful_detection.py
```

### 重新分析历史数据

```bash
docker compose exec backend python reanalyze_harmful.py
```

---

## 🎯 性能优化

### 1. 增加 Backend Workers

编辑 `deploy/backend.Dockerfile`，修改 CMD：
```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "8"]
```

### 2. 启用 Redis 缓存（未来）

在 `docker-compose.yml` 中添加 Redis 服务：
```yaml
redis:
  image: redis:7-alpine
  restart: always
  ports:
    - "6379:6379"
```

### 3. 数据库优化

如果数据量大，考虑迁移到 PostgreSQL：
```yaml
postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: family
    POSTGRES_USER: family
    POSTGRES_PASSWORD: secure_password
  volumes:
    - postgres-data:/var/lib/postgresql/data
```

---

## 📚 参考资料

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Caddy 文档](https://caddyserver.com/docs/)
- [FastAPI 部署指南](https://fastapi.tiangolo.com/deployment/)
- [Nginx 配置参考](https://nginx.org/en/docs/)

---

## ✅ 部署检查清单

部署前确认：
- [ ] 服务器可访问（SSH 连接成功）
- [ ] 端口 80/443 已开放
- [ ] Git 已安装
- [ ] 代码已克隆到服务器
- [ ] .env 文件已配置
- [ ] 所有 API Keys 已填写

部署后确认：
- [ ] 所有容器都在运行（docker compose ps）
- [ ] 可以访问前端页面
- [ ] 可以访问后端 API（/api/sessions）
- [ ] 管理员账户已创建
- [ ] 日志无报错信息
- [ ] HTTPS 证书自动申请成功

---

**祝部署顺利！🎉**

如有问题，请检查日志：`docker compose logs -f`
