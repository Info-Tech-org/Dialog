# Web 端复盘体验加厚 — 交付证据

**部署地址**: http://43.142.49.126:9000
**提交区间**: `a406ba3` → `2f044f2`
**验证时间**: 2026-02-12

---

## 一、功能清单

### P0 功能（已全部实现）

| 功能 | 说明 | 状态 |
|------|------|------|
| 会话摘要卡片 | 时长/说话人数/风险片段数/AI摘要文字/最高严重度星级/主要类别 | ✅ |
| Highlights 面板 | 3-5条关键片段，可点击跳转 + 显示原因 + 一键复制替代说法 | ✅ |
| LLM 分析展开 | 每条有害语句可展开查看 severity★/category/explanation | ✅ |
| 反馈按钮 | 误报/🚩标记/★收藏/📝笔记，持久化到 DB | ✅ |
| 替代说法生成 | 按需触发，结果持久化，下次直接展示 | ✅ |
| AI 摘要生成 | 点击"生成AI复盘摘要"按钮触发，幂等 | ✅ |

### P1 功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 复盘流 ReviewFeed | 跨会话有害语句浏览，含筛选/分页 | ✅ |
| 类型筛选 | 仅有害 / 仅正常 / 全部 | ✅ |
| 设备筛选 | 按 device_id 过滤 | ✅ |
| 分页加载 | 每页20条，"加载更多"按钮 | ✅ |
| 点击跳转 | 点击条目 → `/sessions/{id}?utt={id}` 深链接 | ✅ |

---

## 二、后端 API 验证

### 新增端点（已在 OpenAPI 文档确认）

```
GET  /api/sessions/{session_id}/review
POST /api/sessions/{session_id}/generate
POST /api/utterances/{utterance_id}/feedback
POST /api/utterances/{utterance_id}/suggestion
```

### GET /api/sessions/{id}/review — 响应示例

```bash
curl -s 'http://43.142.49.126:9000/api/sessions/2011854_15165/review' \
  -H 'Authorization: Bearer <token>'
```

```json
{
  "generated": false,
  "summary": {
    "text": "",
    "top_category": "",
    "max_severity": 0,
    "generated_at": null
  },
  "highlights": [],
  "analyses": {},
  "feedbacks": {}
}
```

当 `generated: true` 时响应示例：

```json
{
  "generated": true,
  "summary": {
    "text": "本次对话情绪紧张，家长多次使用贬低语句",
    "top_category": "贬低",
    "max_severity": 4,
    "generated_at": "2026-02-11T14:23:10"
  },
  "highlights": [
    {"utterance_id": "abc123", "score": 0.95, "reason": "直接贬低孩子能力", "rank": 1},
    {"utterance_id": "def456", "score": 0.82, "reason": "威胁惩罚", "rank": 2}
  ],
  "analyses": {
    "abc123": {
      "severity": 4,
      "category": "贬低",
      "explanation": "否定孩子自我价值，造成自尊伤害",
      "suggestion": "可以换成：'我相信你能做到，我们一起想想方法'"
    }
  },
  "feedbacks": {
    "abc123": {
      "is_false_positive": false,
      "is_flagged": true,
      "is_starred": false,
      "note": "这句话对孩子影响很大"
    }
  }
}
```

### POST /api/utterances/{id}/feedback

```bash
curl -s -X POST 'http://43.142.49.126:9000/api/utterances/abc123/feedback' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"is_starred": true, "note": "需要重点关注"}'
```

返回 `{"ok": true}`

---

## 三、数据库表结构

运行 `run_migrations()` 后自动创建四张新表：

| 表名 | 用途 |
|------|------|
| `utterance_feedback` | 用户对单条语句的反馈（误报/收藏/标记/笔记） |
| `utterance_analysis` | LLM 分析结果（severity/category/explanation/suggestion） |
| `session_highlights` | 会话关键片段列表（rank/score/reason） |
| `session_summaries` | 会话级摘要（text/top_category/max_severity） |

---

## 四、前端页面

### SessionDetail (`/sessions/:id`)

**组件结构**:
- `SummaryCard` — 统计数据 + AI摘要 + 生成按钮
- `HighlightsPanel` — 关键片段列表，点击跳转到对应 utterance
- `UtteranceRow` × N — 每条对话，有害条目含分析展开 + 反馈栏

**路由参数**: `?utt={utterance_id}` — 自动滚动并高亮目标语句

### ReviewFeed (`/review`)

- 从会话列表入口进入（"复盘流"按钮）
- 支持按 `harmful/normal/all` 和 `device_id` 过滤
- 点击条目跳转至对应会话的深链接

---

## 五、变更文件清单

### 后端

| 文件 | 类型 | 说明 |
|------|------|------|
| `backend/models/review_models.py` | 新建 | 4张review表 SQLModel |
| `backend/models/__init__.py` | 修改 | 导出新模型 |
| `backend/offline/review_generator.py` | 新建 | LLM 复盘生成器 |
| `backend/api/review_routes.py` | 新建 | review/feedback/suggestion API |
| `backend/main.py` | 修改 | 注册 review_router，调用 run_migrations() |

### 前端

| 文件 | 类型 | 说明 |
|------|------|------|
| `frontend/src/pages/SessionDetail.jsx` | 大幅重写 | SummaryCard + Highlights + 反馈 |
| `frontend/src/pages/ReviewFeed.jsx` | 新建 | 跨会话复盘流 |
| `frontend/src/pages/SessionsList.jsx` | 修改 | 添加"复盘流"导航按钮 |
| `frontend/src/main.jsx` | 修改 | 添加 /review 路由 |
| `frontend/src/index.css` | 修改 | 新增 300+ 行 review 相关样式 |

---

## 六、Git 提交

```
2f044f2  feat(web): add full review experience — summary card, highlights, feedback, ReviewFeed
a406ba3  feat(api): add feedback persistence and review data models
```
