# 部署前检查清单

## ☑️ 服务器准备

### 基础环境
- [ ] 服务器可访问 (SSH 连接成功)
  ```bash
  ssh root@47.236.106.225
  ```
- [ ] 服务器系统为 Ubuntu 24.04 LTS
  ```bash
  lsb_release -a
  ```
- [ ] 有足够的磁盘空间 (至少 10GB)
  ```bash
  df -h
  ```
- [ ] 内存至少 2GB
  ```bash
  free -h
  ```

### 网络配置
- [ ] 端口 80 已开放 (HTTP)
- [ ] 端口 443 已开放 (HTTPS)
- [ ] 端口 22 已开放 (SSH)
- [ ] 阿里云安全组已配置
  - 进入阿里云控制台
  - ECS → 安全组 → 配置规则
  - 添加入方向规则：80/443/22

### 域名配置 (可选)
- [ ] 域名已购买
- [ ] DNS A 记录已添加
  ```
  A    @    47.236.106.225
  A    www  47.236.106.225
  ```
- [ ] DNS 已生效 (可能需要等待 10-60 分钟)
  ```bash
  nslookup yourdomain.com
  ```

## ☑️ 代码准备

### 项目文件
- [ ] 项目已推送到 Git 仓库
- [ ] 所有代码已提交
  ```bash
  git status  # 确保没有未提交的更改
  ```
- [ ] 已测试最新代码
  ```bash
  npm run build  # 前端构建测试
  python -m pytest  # 后端测试（如有）
  ```

### 配置文件
- [ ] `backend/requirements.txt` 是最新的
- [ ] `frontend/package.json` 是最新的
- [ ] 没有硬编码的密钥或密码
- [ ] 本地 `.env` 文件不要提交到 Git

## ☑️ API 密钥准备

### 腾讯云 COS
- [ ] 已开通腾讯云对象存储服务
- [ ] 已创建存储桶 (Bucket)
- [ ] 已获取 Secret ID 和 Secret Key
- [ ] 存储桶权限已设置（公有读或签名访问）
- [ ] 记录以下信息：
  ```
  COS_SECRET_ID: __________________
  COS_SECRET_KEY: __________________
  COS_BUCKET: __________________
  COS_REGION: ap-guangzhou (或其他)
  ```

### 腾讯云 ASR
- [ ] 已开通语音识别服务
- [ ] 已获取 Secret ID 和 Secret Key
- [ ] 记录以下信息：
  ```
  TENCENT_SECRET_ID: __________________
  TENCENT_SECRET_KEY: __________________
  TENCENT_ASR_REGION: ap-guangzhou
  ```

### OpenRouter API
- [ ] 已注册 OpenRouter 账号
- [ ] 已获取 API Key
- [ ] 账户有足够余额
- [ ] 记录以下信息：
  ```
  OPENROUTER_API_KEY: __________________
  ```

### JWT Secret
- [ ] 已生成随机 JWT Secret (至少 32 位)
  ```bash
  # 生成命令
  openssl rand -base64 32
  ```
- [ ] 记录：
  ```
  JWT_SECRET: __________________
  ```

## ☑️ 部署文件检查

### 必需文件
- [ ] `deploy/docker-compose.yml` 存在
- [ ] `deploy/backend.Dockerfile` 存在
- [ ] `deploy/frontend.Dockerfile` 存在
- [ ] `deploy/nginx-frontend.conf` 存在
- [ ] `deploy/Caddyfile` 存在
- [ ] `deploy/.env.example` 存在
- [ ] `deploy/deploy.sh` 存在且可执行
- [ ] `deploy/README_DEPLOY.md` 存在

### 文件权限
```bash
chmod +x deploy/deploy.sh
chmod +x deploy/update.sh
chmod +x deploy/logs.sh
chmod +x deploy/backup.sh
chmod +x deploy/test-deployment.sh
```

## ☑️ 配置文件检查

### Dockerfile
- [ ] `backend.Dockerfile` 使用 Python 3.11
- [ ] `frontend.Dockerfile` 使用 Node 18
- [ ] 所有路径正确（相对于项目根目录）
- [ ] COPY 命令路径正确

### docker-compose.yml
- [ ] 所有服务定义完整
- [ ] 端口映射正确
- [ ] 卷挂载路径正确
- [ ] `env_file: .env` 已配置
- [ ] `restart: always` 已设置

### Caddyfile
- [ ] 域名或 IP 已配置
- [ ] Email 已修改（用于 Let's Encrypt）
- [ ] 反向代理路径正确
- [ ] WebSocket 支持已配置

## ☑️ 本地测试

### 前端
- [ ] 本地构建成功
  ```bash
  cd frontend
  npm install
  npm run build
  ```
- [ ] 构建产物在 `frontend/dist` 目录

### 后端
- [ ] 依赖安装成功
  ```bash
  cd backend
  pip install -r requirements.txt
  ```
- [ ] 可以本地运行
  ```bash
  uvicorn main:app --reload
  ```
- [ ] 健康检查端点可访问
  ```bash
  curl http://localhost:8000/api/health
  ```

## ☑️ 部署前最后确认

### 文档阅读
- [ ] 已阅读 `README_DEPLOY.md`
- [ ] 已阅读 `QUICK_REFERENCE.md`
- [ ] 了解常用命令
- [ ] 知道如何查看日志

### 备份计划
- [ ] 了解如何备份数据
- [ ] 已创建备份脚本 `backup.sh`
- [ ] 知道备份文件存放位置

### 回滚计划
- [ ] 知道如何停止服务 (`docker compose down`)
- [ ] 知道如何查看日志排查问题
- [ ] 了解如何恢复备份

### 监控计划
- [ ] 部署后会检查日志
- [ ] 会运行测试脚本 `test-deployment.sh`
- [ ] 会访问 Web 界面验证
- [ ] 会创建管理员账户测试登录

## ☑️ 准备部署

### 最终确认
- [ ] 所有检查项都已完成 ✅
- [ ] 所有 API 密钥已准备好
- [ ] `.env` 文件已配置
- [ ] 服务器已准备好
- [ ] 时间充足（首次部署约需 10-20 分钟）

---

## 🚀 开始部署

如果所有检查项都已完成，可以开始部署：

```bash
# 1. SSH 连接服务器
ssh root@47.236.106.225

# 2. 克隆项目
cd /opt
git clone <your-repo-url> info-tech

# 3. 进入部署目录
cd info-tech/deploy

# 4. 配置环境变量
cp .env.example .env
nano .env  # 填入所有 API 密钥

# 5. 执行部署
./deploy.sh

# 6. 运行测试
./test-deployment.sh

# 7. 查看日志
./logs.sh

# 8. 访问应用
# 浏览器打开: https://47.236.106.225
```

---

## 📞 遇到问题？

1. **查看日志**
   ```bash
   ./logs.sh
   ```

2. **运行测试**
   ```bash
   ./test-deployment.sh
   ```

3. **检查容器状态**
   ```bash
   docker compose ps
   ```

4. **查看详细文档**
   ```bash
   cat README_DEPLOY.md
   ```

---

**祝部署顺利！🎉**
