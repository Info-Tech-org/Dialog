# 家庭情绪系统 - 部署文件夹

> 🚀 生产环境自动化部署方案

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | Docker Compose 编排文件（定义所有服务） |
| `backend.Dockerfile` | 后端 Docker 镜像构建文件 |
| `frontend.Dockerfile` | 前端 Docker 镜像构建文件 |
| `nginx-frontend.conf` | 前端 Nginx 服务器配置 |
| `Caddyfile` | Caddy 反向代理配置（自动 HTTPS） |
| `.env.example` | 环境变量模板 |
| `deploy.sh` | 🔥 **一键部署脚本** |
| `update.sh` | 快速更新脚本 |
| `logs.sh` | 日志查看脚本 |
| `backup.sh` | 数据备份脚本 |
| `test-deployment.sh` | 部署测试脚本 |

## 📚 文档说明

| 文档 | 说明 |
|------|------|
| `README_DEPLOY.md` | 📖 **完整部署指南**（必读） |
| `QUICK_REFERENCE.md` | ⚡ 快速参考（常用命令） |
| `PRE_DEPLOY_CHECKLIST.md` | ✅ 部署前检查清单 |
| `README.md` | 本文档 |

## 🚀 快速开始

### 1️⃣ 部署前准备

阅读检查清单：
```bash
cat PRE_DEPLOY_CHECKLIST.md
```

### 2️⃣ 一键部署

```bash
# 在服务器上执行
cd /opt/info-tech/deploy
./deploy.sh
```

### 3️⃣ 验证部署

```bash
./test-deployment.sh
```

### 4️⃣ 访问应用

浏览器打开：`https://47.236.106.225`

## 📖 详细文档

完整的部署步骤、配置说明、故障排查，请查看：

```bash
cat README_DEPLOY.md
```

## ⚡ 常用命令

```bash
# 查看服务状态
docker compose ps

# 查看日志
./logs.sh

# 更新代码
./update.sh

# 备份数据
./backup.sh

# 重启服务
docker compose restart
```

更多命令请查看：`QUICK_REFERENCE.md`

## 🏗️ 架构说明

```
Internet
   ↓
Caddy (443) → 自动 HTTPS (Let's Encrypt)
   ├─→ /api/*  → Backend (FastAPI:8000)
   ├─→ /ws/*   → Backend (WebSocket)
   └─→ /*      → Frontend (Nginx:80)
```

## 🔧 服务组件

| 服务 | 容器名 | 端口 | 技术栈 |
|------|--------|------|--------|
| Backend | family-backend | 8000 | FastAPI + Uvicorn (4 workers) |
| Frontend | family-frontend | 80 | React + Vite + Nginx |
| Caddy | family-caddy | 80/443 | Caddy 2 (自动 HTTPS) |

## 📊 数据持久化

| 卷名 | 用途 |
|------|------|
| `backend-data` | SQLite 数据库 |
| `backend-audio` | 上传的音频文件 |
| `caddy-data` | SSL 证书等 |
| `caddy-config` | Caddy 配置 |

## 🔐 安全特性

- ✅ 自动 HTTPS (Let's Encrypt)
- ✅ JWT Token 认证
- ✅ CORS 跨域保护
- ✅ 密码 bcrypt 加密
- ✅ 环境变量隔离
- ✅ Docker 网络隔离

## 📈 生产优化

- ✅ Uvicorn 多进程 (4 workers)
- ✅ Nginx gzip 压缩
- ✅ 静态资源缓存
- ✅ 健康检查
- ✅ 自动重启
- ✅ 日志轮转

## 🆘 需要帮助？

1. **查看完整文档**
   ```bash
   cat README_DEPLOY.md
   ```

2. **查看日志**
   ```bash
   ./logs.sh
   ```

3. **运行测试**
   ```bash
   ./test-deployment.sh
   ```

4. **检查状态**
   ```bash
   docker compose ps
   ```

## 📞 联系信息

- **服务器 IP**: 47.236.106.225
- **访问地址**: https://47.236.106.225
- **项目路径**: /opt/info-tech

---

**开始部署：** `./deploy.sh` 🚀
