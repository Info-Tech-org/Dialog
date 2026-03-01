# Mobile (Expo + TypeScript)

默认连接的后端地址：`http://47.236.106.225:9000`。如果需要指向本地或其他环境，可通过环境变量覆盖：

```bash
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000
```

运行步骤（开发模式）：
1. 安装依赖：`npm install`
2. 启动打包器：`npx expo start --offline`
3. 使用 Expo Go 扫码/连接 Metro，登录后调用真实后端 API（登录、会话、上传等）。

其他说明：
- `mobile/.env.example` 提供环境变量示例，必要时可复制为 `.env` 并调整地址。
- API 取值顺序：`EXPO_PUBLIC_API_BASE_URL` 优先，其次默认的线上地址。*** End Patch
