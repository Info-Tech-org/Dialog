# Skill: PlatformIO + Serial（本项目 Windows/COM3 实战版）

这份 skill 文件记录在本仓库里如何**稳定调用 PlatformIO 编译/烧录**，以及如何用串口工具（serial daemon）**抓日志、发交互命令**。

> 适用环境：Windows + PlatformIO Core 已安装，但 `pio` 可能不在 PATH。

---

## 1) PlatformIO（使用绝对路径，避免 PATH 问题）

### 1.1 固定 CLI 路径

本机可用：

- `C:\Users\charlie\.platformio\penv\Scripts\pio.exe`

若不确定路径，可在 PowerShell 中验证：

- `Test-Path "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe"`
- `& "$env:USERPROFILE\.platformio\penv\Scripts\pio.exe" --version`

### 1.2 编译（build）

在项目根目录（含 platformio.ini）执行：

- `Push-Location "c:\Users\charlie\Documents\platformIO\Projects\Info-tech"`
- `& "C:\Users\charlie\.platformio\penv\Scripts\pio.exe" run`
- `Pop-Location`

### 1.3 烧录（upload）

> 前置条件：**COM 口不能被任何串口监视器占用**（包括本仓库的 serial daemon、PuTTY、Arduino Serial Monitor、VS Code Monitor）。

- `Push-Location "c:\Users\charlie\Documents\platformIO\Projects\Info-tech"`
- `& "C:\Users\charlie\.platformio\penv\Scripts\pio.exe" run -t upload`
- `Pop-Location`

如果需要减少输出（仍会返回成功/失败码）：

- `& "C:\Users\charlie\.platformio\penv\Scripts\pio.exe" run -t upload -s`

### 1.4 常见失败：`Could not open COM3 (PermissionError 13)`

原因：COM3 被占用。

处理顺序：

1. 断开/关闭所有串口监控工具
2. 如果使用 serial daemon（见下文），必须先 `disconnect`
3. 重试 `pio run -t upload`

---

## 2) Serial（串口 daemon：抓日志 + 发命令）

本仓库的调试流程依赖一个“串口监控 daemon”，优点是可脚本化：

- 连接到指定端口（例：`COM3`）
- `tail`/`recent` 读取最近日志
- `send_data` 往设备发送交互命令（本固件有 `r/s/st/h/...`）

### 2.1 关键原则：烧录前必须释放串口

- 烧录前：`serial_daemon_disconnect()`
- 烧录后：再 `serial_daemon_connect(port="COM3", baudrate=115200)`

否则 `pio upload` 会报端口 busy。

### 2.2 串口 daemon 常用操作（概念 API）

> 下面是“技能清单/操作意图”，具体调用方式取决于你当前的自动化工具封装。

- 启动 daemon：`serial_daemon_start()`
- 查看状态：`serial_daemon_status()`
- 连接设备：`serial_daemon_connect(port="COM3", baudrate=115200)`
- 断开连接（释放 COM3）：`serial_daemon_disconnect()`
- 关闭 daemon：`serial_daemon_stop()`

日志读取：

- 最近 N 行：`serial_tail(lines=100, port="COM3")`
- 最近 N 秒：`serial_recent(seconds=30, port="COM3", limit=200)`

发送命令：

- 发送：`serial_send_data("st")`、`serial_send_data("r")`、`serial_send_data("s")`、`serial_send_data("h")`

可选：关闭实时回显（避免刷屏）：

- `serial_set_echo(enabled=false)`

### 2.3 与本固件配套的串口命令

固件在串口交互中提供：

- `h`：显示命令列表
- `st`：状态（heap / 队列深度 / WiFi）
- `r`：开始录音并上传
- `s`：停止录音并触发 final
- `tcp` / `http`：连通性测试

推荐调试闭环（最短路径）：

1. `st`（确认 Idle + heap/队列正常）
2. `r` 录 2~3 秒
3. `s` 停止
4. `tail` 观察是否出现 `WS final audio_url:`

上传协议参考：

- WebSocket PCM 流式协议（v1.0）：`docs/WS_PCM_STREAMING_PROTOCOL_v1.0.md`

---

## 3) 推荐工作流（不浪费时间版）

1. **断开串口监控**（释放 COM3）
2. `pio.exe run` 编译
3. `pio.exe run -t upload` 烧录
4. **重新连接串口监控**
5. `h` / `st` 确认固件启动
6. `r` → `s` → 观察 `audio_url`

---

## 4) 备注

- VS Code 的 C/C++ IntelliSense 报 `Arduino.h not found` 不等于编译失败；以 PlatformIO 构建结果为准。
- 如果 ACK 很慢导致超时，要优先提高 ACK timeout，避免无意义的重发/断线抖动。

> 提醒：执行 `pio.exe run -t upload` 前必须释放 COM3（关闭/断开串口监视器）。
