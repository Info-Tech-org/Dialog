# AI 演绎 502 修复 — 交付证据

**部署地址**: http://43.142.49.126:9000
**验证时间**: 2026-02-12
**状态**: 错误详情已改善；功能阻塞原因 = OpenRouter API key 过期，更新即可。

---

## 一、原始 502 问题

旧版 `roleplay_routes.py` 捕获所有异常用 `except Exception as e`，导致 502 响应体为：

```json
{"detail": "LLM generation failed: Client error '401 Unauthorized' for url 'https://openrouter.ai/...'"}
```

该信息过长且不聚焦，难以快速定位根因。

---

## 二、修复内容

`backend/api/roleplay_routes.py` 新增 `httpx.HTTPStatusError` 分支，从响应体提取 OpenRouter 的 `error.message` 字段：

```python
except httpx.HTTPStatusError as e:
    body_msg = ""
    try:
        body_msg = e.response.json().get("error", {}).get("message", "")
    except Exception:
        body_msg = e.response.text[:300]
    detail = f"LLM API {e.response.status_code}: {body_msg or str(e)}"
    raise HTTPException(status_code=502, detail=detail)
```

---

## 三、修复后 502 响应

```json
{"detail": "LLM API 401: User not found."}
```

清晰地指向：key 无效 / 账号不存在。

---

## 四、测试脚本输出

```bash
$ python3 tools/test_roleplay_generate.py \
    --base http://43.142.49.126:9000 \
    --username admin --password admin123
```

```
[1] Logging in as admin...
  ✓ Token: eyJhbGciOiJIUzI1NiIsInR5cCI6Ik...
[2] Fetching first utterance...
  ✓ Using utterance: 66926ae6-8cbf-... — '接着嗯，首先开始说一下话...'
[3] GET existing roleplay...
  HTTP 200
  No existing roleplay — will generate.
[4] POST generate roleplay (may take 10-30s)...
  HTTP 502
  ✗ LLM generation failed: LLM API 401: User not found.

  → OPENROUTER_API_KEY is expired or invalid.
  → Update /opt/info-tech/deploy/.env:
       OPENROUTER_API_KEY=sk-or-v1-<new-key>
  → Restart backend:
       sshpass -p '...' ssh ubuntu@43.142.49.126
       cd /opt/info-tech/deploy && sudo docker compose up -d --build backend

✗ FAIL: LLM call blocked by API key issue.
```

---

## 五、修复 OpenRouter Key 步骤

```bash
# 1. 在 https://openrouter.ai 获取新 key

# 2. 更新服务器配置
sshpass -p 'gawtAn-8butmy-bargyz' ssh ubuntu@43.142.49.126
# 编辑 /opt/info-tech/deploy/.env:
#   OPENROUTER_API_KEY=sk-or-v1-<新 key>

# 3. 重启 backend
cd /opt/info-tech/deploy && sudo docker compose up -d --build backend

# 4. 重新运行测试
python3 tools/test_roleplay_generate.py \
  --base http://43.142.49.126:9000 \
  --username admin --password admin123
# 预期: ✓ PASS: roleplay generation and caching work correctly.
```

---

## 六、测试脚本使用说明

`tools/test_roleplay_generate.py` — 全流程验证脚本：

1. 登录获取 JWT
2. 获取（或指定）一个 utterance
3. GET roleplay — 检查缓存
4. POST roleplay — 触发生成（30s 超时）
5. GET roleplay — 验证缓存写入

退出码：
- `0` = 通过
- `1` = 非 LLM 错误（认证/格式问题）
- `2` = LLM API 错误（key 过期等），并打印修复步骤

---

## 七、一句话结论

502 错误详情已从原始 httpx 异常字符串改为 `LLM API 401: User not found.`，根因一目了然；更新 `.env` 中的 `OPENROUTER_API_KEY` 并重启 backend 后即可正常生成。
