# 安装和运行指南

## 快速开始

### 1. 安装依赖

**后端依赖：**

```bash
# 进入项目根目录
cd E:\Innox-SZ\info-tech

# 使用当前的 Python 解释器安装依赖
python -m pip install -r backend/requirements.txt
```

**重要**: 确保使用的是实际运行后端的 Python 解释器（如 `C:\Espressif\tools\idf-python\3.11.2\python.exe`）

**前端依赖：**

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install
```

### 2. 创建测试数据

```bash
# 确保在项目根目录
cd E:\Innox-SZ\info-tech

# 先启动后端（在一个终端）
python -m backend.main

# 在另一个终端创建测试数据
python backend/scripts/create_test_data.py
```

### 3. 运行系统

**启动后端：**

```bash
# 方式 1: 使用启动脚本
start_backend.bat

# 方式 2: 手动启动
python -m backend.main
```

后端将在 http://localhost:8000 启动

**启动前端：**

```bash
# 方式 1: 使用启动脚本
start_frontend.bat

# 方式 2: 手动启动
cd frontend
npm run dev
```

前端将在 http://localhost:3000 启动

### 4. 访问系统

打开浏览器访问: http://localhost:3000

**测试账号：**
- 用户名：`admin`
- 密码：`admin123`

## 完整依赖列表

### Python 依赖 (backend/requirements.txt)

```
fastapi==0.104.1              # Web 框架
uvicorn[standard]==0.24.0     # ASGI 服务器
websockets==12.0              # WebSocket 支持
aiofiles==23.2.1              # 异步文件操作
sqlmodel==0.0.14              # ORM
sqlalchemy==2.0.23            # 数据库引擎
httpx==0.25.1                 # HTTP 客户端
python-dotenv==1.0.0          # 环境变量
pydantic==2.5.0               # 数据验证
pydantic-settings==2.1.0      # 设置管理
tencentcloud-sdk-python==3.0.1090  # 腾讯云 SDK
openai==1.12.0                # OpenAI/OpenRouter 客户端
python-jose[cryptography]==3.3.0   # JWT 认证
passlib[bcrypt]==1.7.4        # 密码加密
python-multipart==0.0.9       # 文件上传支持
```

### Node.js 依赖 (frontend/package.json)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.0.8"
  }
}
```

## 故障排查

### 后端问题

#### ModuleNotFoundError: No module named 'xxx'

**原因**: 依赖未安装或使用了错误的 Python 解释器

**解决方案**:
```bash
# 检查当前 Python 版本
python --version

# 重新安装依赖
python -m pip install -r backend/requirements.txt --force-reinstall
```

#### 端口 8000 被占用

**解决方案**:
```bash
# Windows: 查找占用端口的进程
netstat -ano | findstr :8000

# 结束进程（替换 PID）
taskkill /F /PID <PID>
```

#### 数据库错误

**解决方案**:
```bash
# 删除旧数据库
del familymvp.db

# 重新启动后端（会自动创建）
python -m backend.main
```

### 前端问题

#### npm install 失败

**解决方案**:
```bash
# 清理缓存
npm cache clean --force

# 删除 node_modules
rmdir /s /q node_modules

# 重新安装
npm install
```

#### 连接后端失败 (ECONNREFUSED)

**检查清单**:
1. 后端是否正在运行？访问 http://localhost:8000
2. 防火墙是否阻止？
3. 代理设置是否正确？

### 常见问题

#### Q: 如何更改端口？

**后端**:
编辑 `backend/config/settings.py`:
```python
ws_port: int = 8001  # 改成其他端口
```

**前端**:
编辑 `frontend/vite.config.js`:
```javascript
server: {
  port: 3001,  // 改成其他端口
  proxy: {
    '/api': {
      target: 'http://localhost:8001',  // 对应后端端口
    }
  }
}
```

#### Q: 如何重置数据库？

```bash
# 删除数据库文件
del familymvp.db

# 重新创建测试数据
python backend/scripts/create_test_data.py
```

#### Q: 如何更新 API 密钥？

编辑 `backend/config/settings.py` 或创建 `.env` 文件：

```bash
# .env
TENCENT_SECRET_ID=your_secret_id
TENCENT_SECRET_KEY=your_secret_key
OPENROUTER_API_KEY=your_api_key
```

## 开发提示

### 启用调试模式

**后端**:
```python
# backend/main.py
logging.basicConfig(level=logging.DEBUG)  # 改为 DEBUG
```

**前端**:
```bash
# 开发模式已经自动启用 hot reload
npm run dev
```

### API 文档

访问 http://localhost:8000/docs 查看完整的 API 文档（Swagger UI）

### 数据库管理

使用 SQLite 浏览器查看数据库：
- [DB Browser for SQLite](https://sqlitebrowser.org/)
- 数据库文件：`familymvp.db`

## 性能优化

### 生产环境部署

**后端**:
```bash
# 使用 gunicorn
pip install gunicorn
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

**前端**:
```bash
# 构建生产版本
npm run build

# 部署 dist/ 目录到 Nginx 或其他服务器
```

## 系统要求

- Python 3.10+
- Node.js 16+
- 至少 2GB RAM
- 1GB 可用磁盘空间

## 更新日志

查看 Git 提交历史获取详细更新日志：
```bash
git log --oneline
```

## 获取帮助

遇到问题？
1. 查看本文档的故障排查部分
2. 查看 README.md 获取更多信息
3. 检查 GitHub Issues
