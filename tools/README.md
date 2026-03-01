# Remote Executor

一个为 AI 编程环境（Vibe Coding）设计的 SSH 远程服务器管理工具，支持命令执行、文件传输等功能。

## 特性

- 🚀 **非交互式执行** - 适合 AI 助手和自动化脚本使用
- 🔐 **安全凭据管理** - 支持密码和 SSH 密钥认证
- 🌐 **多服务器支持** - 轻松管理多台服务器
- 📊 **友好的输出格式** - 支持纯文本和 JSON 输出
- 📁 **文件传输** - 内置 SFTP 上传/下载功能
- ⚡ **快速响应** - 优化的超时和连接参数

## 安装

### 1. 克隆项目

```bash
git clone https://github.com/your-username/remote-executor.git
cd remote-executor
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置服务器

复制配置示例文件并编辑：

```bash
cp config.example.json config.json
```

或者直接在 `remote_exec.py` 中修改 `SERVERS` 配置：

```python
SERVERS = {
    "default": {
        "host": "your-server-ip",
        "port": 22,
        "username": "your-username",
        "password": "your-password",  # 或使用 key_file
        "description": "My Server"
    }
}
```

**⚠️ 安全提示**: 不要将包含真实密码的配置文件提交到 Git！

## 使用方法

### 基本命令

#### 测试连接

```bash
python remote_exec.py test
```

#### 执行命令

```bash
python remote_exec.py exec "ls -la"
python remote_exec.py exec "docker ps"
python remote_exec.py exec "cd /var/www && pwd"
```

#### 查看服务器信息

```bash
python remote_exec.py info
```

#### 上传文件

```bash
python remote_exec.py upload local_file.txt /remote/path/file.txt
```

#### 下载文件

```bash
python remote_exec.py download /remote/file.txt ./local/
```

### 高级选项

#### 使用特定服务器

```bash
python remote_exec.py exec "hostname" --server=production
```

#### JSON 格式输出

```bash
python remote_exec.py exec "uptime" --json
```

#### 静默模式（仅输出结果）

```bash
python remote_exec.py exec "date" --quiet
```

### 多服务器管理

列出所有配置的服务器：

```bash
python remote_exec.py servers
```

## 配置详解

### 密码认证

```python
{
    "host": "192.168.1.100",
    "port": 22,
    "username": "root",
    "password": "your-password",
    "description": "Production Server"
}
```

### SSH 密钥认证（推荐）

```python
{
    "host": "192.168.1.100",
    "port": 22,
    "username": "root",
    "key_file": "~/.ssh/id_rsa",
    "description": "Production Server"
}
```

### 使用环境变量

为了更安全，建议使用环境变量：

```python
import os

SERVERS = {
    "default": {
        "host": os.getenv("SERVER_HOST"),
        "username": os.getenv("SERVER_USER"),
        "password": os.getenv("SERVER_PASSWORD"),
    }
}
```

## 与 AI 助手集成

这个工具专门设计用于 AI 编程助手（如 Claude Code）。AI 可以直接调用这个工具来管理远程服务器。

### Claude Code 配置示例

在 `.claude/settings.local.json` 中添加权限：

```json
{
  "permissions": {
    "allow": [
      "Bash(python remote_exec.py:*)",
      "Bash(python remote_exec.py exec:*)"
    ]
  }
}
```

### 使用示例

用户：帮我检查服务器上的 Docker 容器状态

AI 执行：
```bash
python remote_exec.py exec "docker ps -a"
```

## 常见问题

### Q: 连接超时怎么办？

A: 检查以下几点：
1. 服务器 IP 和端口是否正确
2. 防火墙是否允许 SSH 连接
3. 服务器 SSH 服务是否运行
4. 调整 `timeout` 参数（默认 60 秒）

### Q: 认证失败？

A: 确认：
1. 用户名和密码正确
2. 如果使用密钥，检查文件路径和权限
3. 服务器是否允许密码/密钥登录

### Q: 如何禁用主机密钥检查？

A: 工具已默认使用 `AutoAddPolicy`，会自动接受未知主机密钥。

## 安全建议

1. ✅ **使用 SSH 密钥** 代替密码认证
2. ✅ **使用环境变量** 存储敏感信息
3. ✅ **添加 config.json 到 .gitignore**
4. ✅ **限制 SSH 访问** IP 白名单
5. ✅ **定期轮换凭据**
6. ✅ **最小权限原则** - 只授予必要的权限

## 开发

### 运行测试

```bash
python remote_exec.py test
```

### 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

本项目采用 Apache License 2.0 许可证 - 详见 [LICENSE](LICENSE) 文件

## 致谢

- [Paramiko](https://www.paramiko.org/) - Python SSH 库
- 灵感来源于 Vibe Coding 和 Claude Code

## 作者

- 庄炎 (Max Zhuang)

## 更新日志

查看 [CHANGELOG.md](CHANGELOG.md) 了解版本历史。

---

如果觉得有用，请给个 ⭐ Star！
