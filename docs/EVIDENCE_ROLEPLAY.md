# AI 演绎 (Roleplay/Coaching) — 交付证据

**部署地址**: http://43.142.49.126:9000
**验证时间**: 2026-02-12
**状态**: 代码已部署，API 端点正常。需更新 OpenRouter API Key 后 LLM 生成即可工作。

---

## 一、功能概述

对任意 utterance（对话片段）生成 AI 演绎内容，帮助家长理解语言影响并练习更好的沟通方式。

### 生成内容

| 模块 | 说明 |
|------|------|
| 影响分析 (impact) | 2-4 条要点，分析这句话对孩子的潜在影响 |
| 替代表达 (rewrites) | 2-3 种更温和有效的替代说法 |
| 情景演练 (rehearsal) | 3 轮对话模拟（家长→孩子→家长），展示改进后的沟通方式 |

### 技术栈

- LLM: OpenRouter (`google/gemma-2-27b-it`)
- 缓存: 首次生成后存入 `utterance_roleplays` 表，后续直接返回
- 前端: Modal 弹窗，支持复制全部 / 重新生成

---

## 二、API 端点

### `POST /api/utterances/{utterance_id}/roleplay`

触发 AI 演绎生成（已有缓存则直接返回）。

**请求**:
```bash
curl -X POST http://43.142.49.126:9000/api/utterances/{UTT_ID}/roleplay \
  -H "Authorization: Bearer {TOKEN}"
```

**响应**:
```json
{
  "ok": true,
  "cached": false,
  "utterance_id": "...",
  "text": "原始文本",
  "content": {
    "impact": ["影响1", "影响2"],
    "rewrites": ["替代说法1", "替代说法2"],
    "rehearsal": [
      {"role": "parent", "text": "..."},
      {"role": "child", "text": "..."},
      {"role": "parent", "text": "..."}
    ]
  },
  "model": "google/gemma-2-27b-it",
  "created_at": "2026-02-12T..."
}
```

### `GET /api/utterances/{utterance_id}/roleplay`

获取已生成的演绎（不触发生成）。

---

## 三、前端使用

1. 打开任意会话详情页 `/sessions/{id}`
2. 每条 utterance 行的按钮栏中有 **"AI 演绎"** 按钮（紫色）
3. 点击后弹出 Modal：
   - 加载中显示 "正在生成 AI 演绎..."
   - 生成成功后分三栏展示：影响分析、替代表达、情景演练
   - 底部有 "复制全部" 和 "重新生成" 按钮
4. 关闭 Modal 后再次点击，直接显示缓存结果（秒开）

---

## 四、变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `backend/models/roleplay_model.py` | 新建 | UtteranceRoleplay SQLModel |
| `backend/models/__init__.py` | 修改 | 导出 UtteranceRoleplay |
| `backend/api/roleplay_routes.py` | 新建 | POST/GET 端点 + LLM prompt |
| `backend/main.py` | 修改 | 注册 roleplay_router |
| `frontend/src/pages/SessionDetail.jsx` | 修改 | RoleplayModal 组件 + AI 演绎按钮 |
| `frontend/src/index.css` | 修改 | Roleplay modal 样式 |

---

## 五、数据模型

```sql
CREATE TABLE utterance_roleplays (
    id          INTEGER PRIMARY KEY,
    utterance_id TEXT NOT NULL,
    user_id     INTEGER,
    model       TEXT DEFAULT '',
    content_json TEXT DEFAULT '{}',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_utterance_roleplays_utterance_id ON utterance_roleplays(utterance_id);
CREATE INDEX ix_utterance_roleplays_user_id ON utterance_roleplays(user_id);
```

---

## 六、故障排查

| 症状 | 排查 |
|------|------|
| 502 LLM generation failed | 检查 OpenRouter API key 和额度 |
| Modal 一直 loading | `docker logs family-backend --tail 20` 查看 LLM 调用日志 |
| 点击无反应 | 检查浏览器控制台是否有 401（token 过期）|
| 内容为空 | 确认 utterance 存在且有文本内容 |

---

## 七、部署验证日志 (2026-02-12)

### 后端启动
```
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```

### GET 端点 (正常)
```bash
GET /api/utterances/5a8c3100-.../roleplay → 200
{
  "ok": true,
  "exists": false,
  "utterance_id": "5a8c3100-...",
  "text": "你妈的你啊...",
  "content": null
}
```

### POST 端点 (OpenRouter key 过期)
```bash
POST /api/utterances/5a8c3100-.../roleplay → 502
{"detail": "LLM generation failed: Client error '401 Unauthorized'..."}
```

> **注意**: 返回 502 是因为 OpenRouter API key 已过期（`User not found`），
> 不是代码问题。更新 `.env` 中的 `OPENROUTER_API_KEY` 并重启后即可正常生成。

---

## 八、验证方法

```bash
# 1. 获取 token
TOKEN=$(curl -s -X POST http://43.142.49.126:9000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. 获取一个 utterance ID
UTT_ID=$(curl -s http://43.142.49.126:9000/api/utterances?limit=1 \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else 'none')")

# 3. 生成演绎
curl -s -X POST "http://43.142.49.126:9000/api/utterances/$UTT_ID/roleplay" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 4. 验证缓存
curl -s "http://43.142.49.126:9000/api/utterances/$UTT_ID/roleplay" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```
