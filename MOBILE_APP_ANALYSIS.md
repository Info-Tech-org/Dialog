# Mobile App 开发现状分析与问题清单

## 📋 项目概况

**分析时间**: 2025-12-20
**当前状态**: 已有基础代码，但不符合原始需求规范

---

## ✅ 已完成的工作

### 1. 目录结构
- ✅ 已创建 `/mobile` 目录（但需求要求是 `/mobile-app`）
- ✅ 使用了 Expo + TypeScript
- ✅ 基本导航结构已搭建

### 2. 技术栈对比

| 需求要求 | 当前实现 | 状态 |
|---------|---------|------|
| Expo (managed workflow) | ✅ Expo ~54.0.29 | ✅ 符合 |
| TypeScript | ✅ TypeScript ~5.9.2 | ✅ 符合 |
| React Navigation | ✅ @react-navigation/native ^7.0.14 | ✅ 符合 |
| TanStack React Query | ❌ **缺失** | ❌ **未实现** |
| Axios | ❌ 使用 fetch API | ⚠️ **需替换** |
| expo-secure-store | ✅ ~13.0.0 | ✅ 符合 |
| expo-document-picker | ✅ ~12.0.0 | ✅ 符合 |
| expo-av | ✅ ~14.0.7 | ✅ 符合 |
| zod (可选) | ❌ 未使用 | ⚠️ 建议添加 |

### 3. 已实现的页面

| 页面 | 文件路径 | 完成度 |
|-----|---------|--------|
| 登录页 | `src/screens/LoginScreen.tsx` | ✅ 已实现 |
| 会话列表 | `src/screens/SessionsScreen.tsx` | ✅ 已实现 |
| 会话详情 | `src/screens/SessionDetailScreen.tsx` | ⚠️ 需验证 |
| 上传页 | `src/screens/UploadScreen.tsx` | ⚠️ 需验证 |
| 上传状态 | `src/screens/UploadStatusScreen.tsx` | ⚠️ 需验证 |
| 设置页 (Tab) | ❌ **缺失** | ❌ **未实现** |

---

## ❌ 关键问题清单

### 🔴 严重问题（必须修复）

#### 1. **目录名称不符合规范**
- **需求**: `/mobile-app`
- **现状**: `/mobile`
- **影响**: 不符合项目规范，需重命名
- **修复**: 重命名目录 + 更新所有路径引用

#### 2. **缺少 TanStack React Query**
- **需求**: 必须使用 React Query 进行数据请求与缓存
- **现状**: 直接使用 fetch API
- **影响**: 没有请求缓存、没有状态管理、没有自动重试
- **修复**: 安装 `@tanstack/react-query` + 重构所有 API 调用

#### 3. **缺少 Axios**
- **需求**: 使用 Axios 作为 HTTP 客户端
- **现状**: 使用原生 fetch
- **影响**: 缺少拦截器、自动 JSON 转换等功能
- **修复**: 安装 `axios` + 重构 `src/api/client.ts`

#### 4. **缺少设置页（Settings Tab）**
- **需求**: 必须实现设置页，显示 API Base URL、退出登录、App 版本
- **现状**: 完全缺失
- **影响**: 无法切换环境、无法退出登录
- **修复**: 创建 `SettingsScreen.tsx` + 实现底部 Tab 导航

#### 5. **导航结构不符合需求**
- **需求**: AuthStack + MainTabs（会话列表、上传、设置三个Tab）
- **现状**: 全部是 Stack 导航，没有 Tab 导航
- **影响**: 用户体验差，不符合规范
- **修复**: 使用 `@react-navigation/bottom-tabs` 重构导航

#### 6. **API 路径不一致**
- **后端实际**:
  - 登录: `/api/auth/login`
  - 会话列表: `/api/sessions`
  - 会话详情: `/api/sessions/{id}`
  - 上传: `/api/audio/upload`
  - 上传状态: `/api/audio/upload/status/{id}`
- **前端使用**:
  - 上传: `/api/audio/upload` ✅
  - 其他: 需验证
- **修复**: 统一 API 路径定义

### ⚠️ 中等问题（需要改进）

#### 7. **缺少轮询机制验证**
- **需求**: 处理中的 session 每 2-3 秒轮询状态
- **现状**: 代码中似乎有实现，但需要验证
- **修复**: 测试轮询功能 + 确保页面退出时取消

#### 8. **缺少环境配置文件**
- **需求**: `.env.example` 文件
- **现状**: 缺失
- **修复**: 创建 `.env.example` 示例文件

#### 9. **缺少 README_MOBILE.md**
- **需求**: 详细的使用文档
- **现状**: 缺失
- **修复**: 创建完整的文档

#### 10. **音频播放未验证**
- **需求**: 支持播放后端返回的音频 URL（预签名 URL 或代理 URL）
- **现状**: 代码似乎有实现，但未测试
- **修复**: 测试音频播放功能

### 💡 优化建议（非强制）

#### 11. **添加 zod 类型验证**
- **好处**: 运行时类型安全、API 响应验证
- **现状**: 未使用
- **建议**: 添加 zod 验证所有 API 返回

#### 12. **错误处理不完善**
- **现状**: 简单的 try-catch
- **建议**: 统一错误提示组件、网络错误重试机制

#### 13. **缺少 Loading 和 Error 状态**
- **现状**: 部分页面可能缺少加载状态
- **建议**: 统一 Loading/Error UI 组件

---

## 🎯 后端 API 确认清单

### 已确认的 API Endpoints

| 功能 | 方法 | 路径 | 是否需要认证 | 后端状态 |
|-----|------|------|------------|---------|
| 健康检查 | GET | `/api/health` | ❌ | ✅ 已实现 |
| 用户登录 | POST | `/api/auth/login` | ❌ | ✅ 已实现 |
| 用户注册 | POST | `/api/auth/register` | ❌ | ✅ 已实现 |
| 当前用户信息 | GET | `/api/auth/me` | ✅ | ✅ 已实现 |
| 会话列表 | GET | `/api/sessions` | ✅ | ✅ 已实现 |
| 会话详情 | GET | `/api/sessions/{id}` | ✅ | ✅ 已实现 |
| 上传音频 | POST | `/api/audio/upload` | ✅ | ✅ 已实现 |
| 上传状态 | GET | `/api/audio/upload/status/{id}` | ✅ | ✅ 已实现 |
| Token 刷新 | POST | `/api/auth/refresh` | ✅ | ❓ **需确认** |

### ❓ 需要与你确认的问题

1. **Token 刷新机制**
   - 后端是否实现了 `/api/auth/refresh` endpoint？
   - 如果没有，401 错误时直接退出登录即可

2. **音频 URL 格式**
   - 后端返回的 `audio_url` 是预签名 URL 还是相对路径？
   - 是否需要前端拼接 baseURL？
   - **从代码看**: 后端会返回 COS 预签名 URL 或 `/media/{filename}` 格式
   - **前端需要**: 如果是 `/media/` 开头，需要拼接完整 URL

3. **Session 状态字段**
   - 后端返回的 session 是否有 `status` 字段（pending/processing/done/failed）？
   - **从类型定义看**: 前端期望有 `status` 字段，但后端 `SessionResponse` 没有明确定义
   - **需要**: 确认后端如何表示处理状态（可能通过 `end_time` 判断？）

4. **Utterance severity 字段**
   - 后端的 `Utterance` 是否返回 `severity` (1-5) 字段？
   - **从代码看**: 后端只有 `harmful_flag: boolean`，**没有 severity**
   - **需要**: 是否需要添加 severity 字段？

5. **生产环境服务器信息**
   - **服务器 IP**: 47.236.106.225
   - **端口**: 9000
   - **Base URL**: `http://47.236.106.225:9000`
   - **是否有域名**: 需要确认
   - **HTTPS**: 需要确认

6. **登录问题现状**
   - 之前部署时登录失败，是否已解决？
   - 需要确认管理员账户：username: admin, password: Admin123!

---

## 📝 实施计划建议

### 第一阶段：修复严重问题（必须完成）

1. ✅ **不重命名目录**（保持 `/mobile`，因为重命名影响太大）
2. 🔧 安装缺失依赖
   ```bash
   npm install @tanstack/react-query axios
   npm install @react-navigation/bottom-tabs
   npm install zod  # 可选
   ```
3. 🔧 重构 API 层
   - 用 Axios 替换 fetch
   - 集成 React Query
   - 添加请求/响应拦截器
4. 🔧 重构导航结构
   - 创建 Bottom Tabs (会话列表、上传、设置)
   - 修改 AuthStack 结构
5. 🔧 创建设置页面
6. 🔧 创建必要的配置文件
   - `.env.example`
   - `README_MOBILE.md`

### 第二阶段：测试与验证（必须完成）

1. 🧪 配置生产环境 API Base URL
2. 🧪 测试登录功能
3. 🧪 测试上传音频
4. 🧪 测试会话列表和详情
5. 🧪 测试轮询机制
6. 🧪 测试音频播放
7. 🧪 测试退出登录

### 第三阶段：优化与文档（建议完成）

1. 📝 完善文档
2. 🎨 UI/UX 优化
3. 🐛 Bug 修复
4. ✅ Git 提交历史整理（至少 5 次 commit）

---

## 🤔 需要你确认的关键决策

### 决策 1: 目录名称
- **选项 A**: 重命名 `/mobile` → `/mobile-app`（严格符合需求）
- **选项 B**: 保持 `/mobile`（避免大量路径修改）
- **我的建议**: 选项 B，因为重命名会影响现有代码和 git 历史

### 决策 2: 后端 API 修改
- **问题**: 后端缺少 `severity` 字段和 `status` 字段
- **选项 A**: 修改后端添加这些字段
- **选项 B**: 前端适配现有后端（如 `harmful_flag` 为 true 时默认 severity=3）
- **我的建议**: 选项 B，最小化后端修改

### 决策 3: Token 刷新
- **问题**: 不确定后端是否有 refresh endpoint
- **选项 A**: 如果有，实现自动刷新
- **选项 B**: 如果没有，401 时直接退出登录
- **需要**: 你确认后端是否有 refresh 功能

### 决策 4: 测试环境
- **问题**: 我无法直接运行 Android 模拟器测试
- **选项 A**: 我提供代码，你负责测试并反馈问题
- **选项 B**: 我提供详细的测试脚本和检查清单
- **我的建议**: 选项 A + 选项 B 结合

---

## 📞 下一步行动

**请你确认以下问题，然后我开始执行：**

1. ✅ 保持目录名称为 `/mobile`（不改为 `/mobile-app`）？
2. ❓ 后端是否有 `/api/auth/refresh` endpoint？
3. ❓ 后端 Session 如何表示状态（pending/processing/done/failed）？
4. ❓ 是否需要在后端添加 `severity` 字段，还是前端自己计算？
5. ❓ 生产服务器的完整 URL 是什么？（http://47.236.106.225:9000 ?)
6. ❓ 当前登录问题是否已解决？（admin / Admin123!）
7. ✅ 你同意我的实施计划吗？有什么调整？

**确认后我会立即开始实施！** 🚀
