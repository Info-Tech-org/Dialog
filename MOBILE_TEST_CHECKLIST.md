# 移动端音频播放诊断 - 真机测试清单

**Phase 4 (P0-1)**: 移动端播放诊断功能验证

---

## 测试环境要求

- **生产环境 API**: http://47.236.106.225:9000
- **网络要求**: 关闭 VPN，确保能访问生产 API
- **移动设备**: Android 或 iOS 真机（不推荐模拟器）
- **App 环境**: Expo Go + 生产配置

---

## 前置准备

### 1. 生成测试音频

在电脑上运行以下命令生成测试 session:

```bash
# 设置 device token
export DEVICE_INGEST_TOKEN=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw

# 或 Windows PowerShell:
$env:DEVICE_INGEST_TOKEN="KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw"

# 生成 2 秒 440Hz 正弦波测试音频
python tools/test_pcm_ingest.py --base http://47.236.106.225:9000 --duration 2.0
```

**记录返回的 session_id（后续步骤需要）**

预期输出示例:
```
Using device token: KWOtrTMs...
Final chunk response time: 218ms
Polling status for session d8537fbc-3d2c-44c0-b6af-e78222ec689b...
  [0] Status transition: processing (+200ms)
  [6] Status transition: completed (+7351ms)
OK session_id=d8537fbc-3d2c-44c0-b6af-e78222ec689b
audio_url=http://47.236.106.225:9000/media/d8537fbc-3d2c-44c0-b6af-e78222ec689b.wav
head_status=200 content_length=64044
```

### 2. 配置移动端环境变量

确认 `mobile/.env` 文件配置正确:

```env
EXPO_PUBLIC_API_BASE_URL=http://47.236.106.225:9000
```

### 3. 启动移动端 App

```bash
cd mobile
npm start
```

使用手机扫描二维码打开 Expo Go。

---

## 测试步骤

### 步骤 1: 登录

- 打开 App
- 使用以下凭证登录:
  - 用户名: `admin`
  - 密码: `Admin123!`

**预期结果**: ✅ 成功登录，进入会话列表页

---

### 步骤 2: 进入会话详情页

- 点击会话列表中的测试 session（使用前置准备生成的 session_id）
- 滚动到页面顶部

**预期结果**: ✅ 显示以下信息:
- 会话 ID (前 8 位)
- 设备 ID: esp32
- 开始/结束时间
- 有害句数: 0
- **音频 URL**: `http://47.236.106.225:9000/media/xxx.wav`
- 两个按钮: "检查音频链接" 和 "播放音频"

---

### 步骤 3: 测试"检查音频链接"功能

- 点击绿色按钮 **"检查音频链接"**
- 等待 1-2 秒

**预期结果**: ✅ 诊断面板自动展开，显示:

```
诊断信息                         [复制]
===================================
音频链接检查:
URL: http://47.236.106.225:9000/media/...
状态码: 200 ✓
Content-Type: audio/x-wav (或 audio/wav)
Content-Length: 64,044 bytes
Accept-Ranges: bytes
检查时间: HH:MM:SS
```

**✅ 成功条件**:
- 状态码是 200 或 206（带 ✓ 标记）
- Content-Type 包含 "audio"（不是 text/html）
- Content-Length > 10,000 bytes
- 无错误提示

**❌ 失败情况（需反馈）**:
- 状态码非 200/206 → **记录实际状态码和 URL**
- Content-Type 是 text/html → **说明 Caddy 配置问题**
- Content-Length < 10000 → **文件太小或损坏**
- 出现网络错误 → **记录错误信息**

---

### 步骤 4: 测试"播放音频"功能

- 点击蓝色按钮 **"播放音频"**
- 观察按钮状态变化
- 听音频播放

**预期结果（成功情况）**: ✅
1. 按钮立即变为 **"播放中..."** 并禁用
2. 听到 2 秒的 440Hz 正弦波音频（连续的"嘟~~"声）
3. 播放结束后，按钮恢复为 **"播放音频"**

**失败情况（需反馈）**: ❌
1. 出现 Alert 弹窗 **"播放失败"**，显示错误信息
2. 诊断面板自动展开并显示 **"播放错误"** 部分:
   ```
   播放错误:
   消息: [错误消息]
   代码: [错误代码]
   堆栈: [可横向滚动查看]
   原始: [完整 JSON 对象]
   ```

**如果播放失败，请记录**:
- 错误消息 (message)
- 错误代码 (code)
- 完整的 raw JSON（使用"复制"功能）

---

### 步骤 5: 测试"复制诊断信息"功能

- 点击诊断面板右上角的 **"复制"** 按钮

**预期结果**: ✅
1. 出现 Alert **"已复制"**
2. 打开任意文本编辑器，粘贴内容
3. 验证包含以下格式:
   ```
   === 音频诊断信息 ===
   URL: ...
   状态码: ...
   Content-Type: ...
   ...

   === 播放错误信息 ===
   消息: ...
   代码: ...
   ...
   ```

---

### 步骤 6: 测试错误场景（可选）

#### 6.1 不存在的 session
- 手动修改 URL 或尝试访问不存在的 session

**预期结果**: ✅ 显示 **"未找到会话"**

#### 6.2 网络断开
- 关闭 WiFi/移动数据
- 点击"检查音频链接"或"播放音频"

**预期结果**: ✅ 诊断面板显示网络错误信息

#### 6.3 无效 URL
- 如果 audio_url 为空或格式错误

**预期结果**: ✅ Alert **"音频路径不可用"**

---

## 反馈模板

如果测试失败，请提供以下信息:

```
## 失败报告

### 基本信息
- 失败步骤: 步骤 X
- Session ID: [从前置准备记录]
- audio_url: [从 App 显示的值]
- 设备型号: [如 iPhone 12, Samsung S21]
- 操作系统: [如 iOS 16, Android 13]
- Expo Go 版本: [查看 App 设置]

### 实际错误信息
[粘贴 Alert 弹窗或诊断面板的完整文本]

### 诊断面板截图
[如有可能，提供截图]

### 完整诊断信息（使用"复制"功能）
```
[粘贴复制的完整诊断信息]
```

### 控制台输出（如果可访问）
[在 Expo 开发工具中查看 console.log]
```

---

## 技术背景（供开发者参考）

### Phase 4 实现内容
- **checkAudioUrl()**: HEAD 或 GET Range: bytes=0-1023 检查音频可访问性
- **playAudio() 增强**: 完整错误捕获（message, code, stack, raw JSON）
- **诊断面板**: 分节显示音频检查和播放错误，支持横向滚动和复制
- **console.log**: 播放流程日志（在 Expo 开发工具查看）
- **UI 改造**: ScrollView 替换 FlatList，便于诊断面板集成

### 保留决策
- 继续使用 `expo-av@14.0.7`（虽已 deprecated，但本轮不迁移）
- 不引入 React Query/Axios（保持原有技术栈）
- 仅增加可观测性，不改动核心播放逻辑

### 已知问题
- expo-av 已被标记为 deprecated，建议未来迁移到 expo-audio
- 诊断面板仅在开发和真机测试中有效，生产环境应考虑添加远程日志

---

## 测试完成标志

当以下所有项均通过时，Phase 4 测试完成:

- [ ] 步骤 1: 登录成功
- [ ] 步骤 2: 会话详情页显示正确
- [ ] 步骤 3: "检查音频链接" 返回 HTTP 200 和正确的 Content-Type
- [ ] 步骤 4: "播放音频" 成功播放 2 秒正弦波
- [ ] 步骤 5: "复制诊断信息" 功能正常
- [ ] （可选）步骤 6: 错误场景处理正确

---

**版本**: Phase 4 (P0-1)
**文档日期**: 2025-12-23
**Commit**: ba9d201
**生产环境**: http://47.236.106.225:9000
