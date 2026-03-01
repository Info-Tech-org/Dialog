#!/usr/bin/env python3
"""
Remote Server Executor - 为 Vibe Coding 设计的服务器连接工具

功能：
- 非交互式 SSH 执行命令
- 安全的凭据管理
- 支持多服务器配置
- AI 友好的输出格式

使用方法：
    # 执行单条命令
    python remote_exec.py exec "ls -la"
    
    # 执行多条命令
    python remote_exec.py exec "cd /root && pwd && ls"
    
    # 上传文件
    python remote_exec.py upload local_file.txt /remote/path/
    
    # 下载文件
    python remote_exec.py download /remote/file.txt ./local/
    
    # 测试连接
    python remote_exec.py test
    
    # 查看服务器信息
    python remote_exec.py info
"""

import paramiko
import json
import sys
import os
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# ============== 配置区域 ==============
# 推荐使用配置文件或环境变量来存储敏感信息

def load_config():
    """从配置文件或环境变量加载服务器配置"""
    # 优先级：config.json > 环境变量 > 默认配置

    # 尝试从 config.json 加载
    config_file = Path("config.json")
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                return config_data.get("servers", {}), config_data.get("default_server", "default")
        except Exception as e:
            print(f"[WARNING] Failed to load config.json: {e}", file=sys.stderr)

    # 从环境变量加载
    if os.getenv("REMOTE_HOST"):
        return {
            "default": {
                "host": os.getenv("REMOTE_HOST"),
                "port": int(os.getenv("REMOTE_PORT", "22")),
                "username": os.getenv("REMOTE_USER", "root"),
                "password": os.getenv("REMOTE_PASSWORD"),
                "key_file": os.getenv("REMOTE_KEY_FILE"),
                "description": os.getenv("REMOTE_DESCRIPTION", "Environment Server")
            }
        }, "default"

    # 默认配置（示例）
    return {
        "example": {
            "host": "your-server-ip",
            "port": 22,
            "username": "your-username",
            "password": "your-password",  # 不要在这里写真实密码！
            # 或者使用密钥文件：
            # "key_file": "~/.ssh/id_rsa",
            "description": "Example Server - Please configure in config.json"
        }
    }, "example"

SERVERS, DEFAULT_SERVER = load_config()

# ============== 核心类 ==============

@dataclass
class ExecResult:
    """命令执行结果"""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    command: str
    server: str
    
    def to_dict(self):
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "command": self.command,
            "server": self.server
        }
    
    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    def __str__(self):
        if self.success:
            return self.stdout
        else:
            return f"[ERROR] Exit code: {self.exit_code}\n{self.stderr}"


class RemoteExecutor:
    """远程服务器执行器"""
    
    def __init__(self, server_name: str = DEFAULT_SERVER):
        if server_name not in SERVERS:
            raise ValueError(f"Unknown server: {server_name}. Available: {list(SERVERS.keys())}")
        
        self.server_name = server_name
        self.config = SERVERS[server_name]
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
    
    def connect(self) -> bool:
        """建立 SSH 连接"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_params = {
                "hostname": self.config["host"],
                "port": self.config.get("port", 22),
                "username": self.config["username"],
                "timeout": 60,
                "banner_timeout": 200,
                "auth_timeout": 60,
                "look_for_keys": False,
                "allow_agent": False,
            }

            # 优先使用密钥，其次使用密码
            if "key_file" in self.config:
                key_path = os.path.expanduser(self.config["key_file"])
                connect_params["key_filename"] = key_path
            elif "password" in self.config:
                connect_params["password"] = self.config["password"]

            print(f"[INFO] Connecting to {self.config['host']}:{connect_params['port']}...", file=sys.stderr)
            self.client.connect(**connect_params)
            print(f"[INFO] Connected successfully!", file=sys.stderr)
            return True

        except Exception as e:
            print(f"[ERROR] Connection failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.sftp:
            self.sftp.close()
            self.sftp = None
        if self.client:
            self.client.close()
            self.client = None
    
    def exec(self, command: str, timeout: int = 60) -> ExecResult:
        """执行远程命令"""
        if not self.client:
            if not self.connect():
                return ExecResult(
                    success=False,
                    stdout="",
                    stderr="Failed to connect to server",
                    exit_code=-1,
                    duration_ms=0,
                    command=command,
                    server=self.server_name
                )
        
        start_time = datetime.now()
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            
            stdout_text = stdout.read().decode('utf-8', errors='replace')
            stderr_text = stderr.read().decode('utf-8', errors='replace')
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ExecResult(
                success=(exit_code == 0),
                stdout=stdout_text,
                stderr=stderr_text,
                exit_code=exit_code,
                duration_ms=duration_ms,
                command=command,
                server=self.server_name
            )
            
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return ExecResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_ms=duration_ms,
                command=command,
                server=self.server_name
            )
    
    def get_sftp(self) -> paramiko.SFTPClient:
        """获取 SFTP 客户端"""
        if not self.client:
            self.connect()
        if not self.sftp:
            self.sftp = self.client.open_sftp()
        return self.sftp
    
    def upload(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        """上传文件到服务器"""
        try:
            sftp = self.get_sftp()
            local_path = os.path.expanduser(local_path)
            
            if os.path.isdir(local_path):
                return False, "Directory upload not supported yet. Please use tar/zip."
            
            sftp.put(local_path, remote_path)
            return True, f"Uploaded: {local_path} -> {remote_path}"
            
        except Exception as e:
            return False, str(e)
    
    def download(self, remote_path: str, local_path: str) -> Tuple[bool, str]:
        """从服务器下载文件"""
        try:
            sftp = self.get_sftp()
            local_path = os.path.expanduser(local_path)
            
            # 如果本地路径是目录，使用远程文件名
            if os.path.isdir(local_path):
                filename = os.path.basename(remote_path)
                local_path = os.path.join(local_path, filename)
            
            sftp.get(remote_path, local_path)
            return True, f"Downloaded: {remote_path} -> {local_path}"
            
        except Exception as e:
            return False, str(e)
    
    def get_server_info(self) -> dict:
        """获取服务器信息"""
        info = {
            "server": self.server_name,
            "host": self.config["host"],
            "description": self.config.get("description", ""),
        }
        
        # 获取系统信息
        result = self.exec("uname -a && cat /etc/os-release | head -5 && df -h / | tail -1 && free -h | head -2")
        if result.success:
            info["system_info"] = result.stdout
        
        return info
    
    def test_connection(self) -> Tuple[bool, str]:
        """测试连接"""
        if self.connect():
            result = self.exec("echo 'Connection OK' && hostname")
            self.disconnect()
            if result.success:
                return True, f"[OK] Connected to {self.config['host']}\nHostname: {result.stdout.strip()}"
            return False, f"[FAIL] Connected but command failed: {result.stderr}"
        return False, f"[FAIL] Failed to connect to {self.config['host']}"


# ============== 命令行接口 ==============

def print_help():
    """打印帮助信息"""
    help_text = """
╔══════════════════════════════════════════════════════════════════╗
║           Remote Executor - Vibe Coding 服务器工具                ║
╚══════════════════════════════════════════════════════════════════╝

用法: python remote_exec.py <command> [args...]

命令:
  exec <cmd>              执行远程命令
  upload <local> <remote> 上传文件到服务器
  download <remote> <local> 下载文件到本地
  test                    测试服务器连接
  info                    显示服务器信息
  servers                 列出所有配置的服务器
  help                    显示此帮助

选项:
  --server=<name>         指定服务器 (默认: default)
  --json                  以 JSON 格式输出
  --quiet                 静默模式，只输出结果

示例:
  python remote_exec.py exec "ls -la /root"
  python remote_exec.py exec "docker ps"
  python remote_exec.py upload ./app.py /root/app.py
  python remote_exec.py download /var/log/syslog ./logs/
  python remote_exec.py test --server=production
"""
    print(help_text)


def main():
    if len(sys.argv) < 2:
        print_help()
        return
    
    # 解析参数
    args = sys.argv[1:]
    server_name = DEFAULT_SERVER
    json_output = False
    quiet = False
    
    # 提取选项
    remaining_args = []
    for arg in args:
        if arg.startswith("--server="):
            server_name = arg.split("=")[1]
        elif arg == "--json":
            json_output = True
        elif arg == "--quiet":
            quiet = True
        else:
            remaining_args.append(arg)
    
    if not remaining_args:
        print_help()
        return
    
    cmd = remaining_args[0]
    
    # 处理命令
    if cmd == "help":
        print_help()
        return
    
    if cmd == "servers":
        print("配置的服务器列表:")
        for name, config in SERVERS.items():
            marker = " (default)" if name == DEFAULT_SERVER else ""
            print(f"  • {name}{marker}: {config['host']} - {config.get('description', '')}")
        return
    
    # 需要连接服务器的命令
    executor = RemoteExecutor(server_name)
    
    try:
        if cmd == "test":
            success, msg = executor.test_connection()
            print(msg)
            sys.exit(0 if success else 1)
        
        elif cmd == "info":
            info = executor.get_server_info()
            if json_output:
                print(json.dumps(info, ensure_ascii=False, indent=2))
            else:
                print(f"服务器: {info['server']} ({info['host']})")
                print(f"描述: {info['description']}")
                print(f"\n系统信息:\n{info.get('system_info', 'N/A')}")
        
        elif cmd == "exec":
            if len(remaining_args) < 2:
                print("用法: python remote_exec.py exec <command>")
                sys.exit(1)
            
            command = " ".join(remaining_args[1:])
            result = executor.exec(command)
            
            if json_output:
                print(result.to_json())
            elif quiet:
                print(result.stdout, end="")
            else:
                if result.success:
                    print(result.stdout, end="")
                else:
                    print(f"[ERROR] Exit code: {result.exit_code}", file=sys.stderr)
                    print(result.stderr, file=sys.stderr)
            
            sys.exit(result.exit_code)
        
        elif cmd == "upload":
            if len(remaining_args) < 3:
                print("用法: python remote_exec.py upload <local_path> <remote_path>")
                sys.exit(1)
            
            success, msg = executor.upload(remaining_args[1], remaining_args[2])
            print(msg)
            sys.exit(0 if success else 1)
        
        elif cmd == "download":
            if len(remaining_args) < 3:
                print("用法: python remote_exec.py download <remote_path> <local_path>")
                sys.exit(1)
            
            success, msg = executor.download(remaining_args[1], remaining_args[2])
            print(msg)
            sys.exit(0 if success else 1)
        
        else:
            print(f"未知命令: {cmd}")
            print_help()
            sys.exit(1)
    
    finally:
        executor.disconnect()


if __name__ == "__main__":
    main()

