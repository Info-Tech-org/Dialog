# 有害检测技术方案：关键词 + 语义向量 + LLM 筛选

## 目标

- **不错过**：绝对关键词必检；语义相近的表述通过向量召回。
- **控制误报**：向量候选交 LLM 做最终判定。
- **可扩展**：关键词与有害概念参考句可配置、可扩展；Embedding 支持本地/API。

## 三层串联

```
输入文本
    │
    ▼
┌─────────────────────────────────────┐
│ 1. 绝对关键词 (ABSOLUTE_KEYWORDS)    │  命中 → 判有害，短路
└─────────────────────────────────────┘
    │ 未命中
    ▼
┌─────────────────────────────────────┐
│ 2. 语义向量召回                       │  与 HARMFUL_REFERENCES 做
│    Embed(input) vs Embed(refs)       │  相似度；≥ 阈值 → 候选
└─────────────────────────────────────┘
    │ 候选
    ▼
┌─────────────────────────────────────┐
│ 3. LLM 筛选                          │  仅对候选调用 LLM，得到
│    OpenRouter/LLM 判定 + 严重度      │  是否有害、类别、解释
└─────────────────────────────────────┘
    │
    ▼
HarmfulResult (is_harmful, severity, category, explanation)
```

## 实现要点

| 层级 | 实现 | 说明 |
|------|------|------|
| 绝对关键词 | `harmful_rules.ABSOLUTE_KEYWORDS` + `KeywordDetector` | 预先维护，命中即有害，不调 LLM |
| 有害概念参考 | `harmful_rules.HARMFUL_REFERENCES` | 短句覆盖辱骂/威胁/贬低/情感伤害等，用于向量相似度 |
| 向量化 | `embedding_service.EmbeddingProvider` | OpenAI 兼容 API 或本地 sentence-transformers |
| 向量+LLM | `VectorThenLLMDetector` | 相似度 ≥ 阈值才调 LLM，否则直接判无害 |
| Pipeline | `detector_pipeline.run_pipeline` | 默认 `[KeywordDetector(), VectorThenLLMDetector()]` |

## 配置

- **Embedding**：`embedding_provider`（openai / local）、`embedding_api_key`、`embedding_model`（见 `config/settings.py` 与 `realtime/README_DETECTORS.md`）。
- **向量阈值**：`VectorThenLLMDetector(similarity_threshold=0.65)`，可按业务调整。
- **LLM**：沿用 OpenRouter 配置，用于向量候选的最终判定。

## 扩展建议

- 增补 **ABSOLUTE_KEYWORDS**：新词加入即生效，保证必检。
- 增补 **HARMFUL_REFERENCES**：增加覆盖场景的参考句，提升语义召回。
- 本地化 **Embedding**：安装 `sentence-transformers`，设置 `embedding_provider=local`，无需 API Key。
- 自定义 detector：实现 `BaseHarmfulDetector`，插入 pipeline 顺序即可。
