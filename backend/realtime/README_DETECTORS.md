# 有害语检测插件

可插拔的有害检测管道：**绝对关键词 → 语义向量召回 → LLM 筛选**，确保不错过、控制误报。

## 流程概览

1. **绝对关键词（必检）**：命中 `harmful_rules.ABSOLUTE_KEYWORDS` 任一即判有害并短路，不依赖 LLM。
2. **语义向量召回**：将输入文本与预置有害概念参考句（`HARMFUL_REFERENCES`）做向量相似度；达到阈值则进入下一步。
3. **LLM 筛选**：仅对「向量候选」调用 LLM 做最终判定（严重度、类别、解释），降低误报并节省调用。

## 接口

- **`BaseHarmfulDetector`**（`detector_base.py`）：抽象基类，实现 `async def detect(text: str) -> HarmfulResult`。
- **`HarmfulResult`**：dataclass，包含 `is_harmful`, `method`, `severity`, `category`, `explanation`, `keywords`（可选）等。
- **`run_pipeline(text, detectors=..., short_circuit_on_harmful=True)`**：按顺序执行多个 detector；首个返回有害即终止（可选）。

## 内置插件

| 插件 | 说明 |
|------|------|
| `KeywordDetector` | 基于 `ABSOLUTE_KEYWORDS` 的快速匹配，命中即有害 |
| `VectorThenLLMDetector` | 语义向量化（与有害概念参考句相似度）+ 达阈值后 LLM 筛选 |
| `LLMDetector` | 纯 LLM 语义分析（可单独用于兼容或降级） |

## 默认 Pipeline

```python
# 默认：Keyword + VectorThenLLM（语义 + LLM 筛选）
detectors = get_default_pipeline()  # use_vector_llm=True

# 仅关键词 + LLM（无向量，兼容旧行为）
detectors = get_default_pipeline(use_vector_llm=False)
```

## 使用方式

- **兼容旧接口**：`is_harmful_advanced(text, use_llm=True)` 内部使用默认 pipeline，返回 `(bool, dict)`。
- **直接使用 pipeline**：
  ```python
  from realtime.detector_pipeline import run_pipeline, get_default_pipeline
  from realtime.vector_detector import VectorThenLLMDetector
  from realtime.keyword_detector import KeywordDetector

  detectors = get_default_pipeline()  # Keyword + VectorThenLLM
  is_harmful, details = await run_pipeline("某段文字", detectors=detectors)
  ```

## 配置（config/settings 或 .env）

| 变量 | 说明 | 默认 |
|------|------|------|
| `embedding_provider` | `openai` \| `local`（local 需安装 sentence-transformers） | `openai` |
| `embedding_api_key` | OpenAI API Key（用于 text-embedding-3-small 等） | — |
| `embedding_model` | 模型名 | `text-embedding-3-small` |
| `embedding_base_url` | 自定义 OpenAI 兼容 endpoint | — |

未配置 `embedding_api_key` 时，向量阶段不可用，`VectorThenLLMDetector` 会退化为仅 LLM（或可视为跳过向量、仅关键词+LLM）。

## 扩展

- **绝对关键词**：在 `harmful_rules.ABSOLUTE_KEYWORDS` 中增删，或保持 `HARMFUL_KEYWORDS` 别名。
- **有害概念参考句**：在 `harmful_rules.HARMFUL_REFERENCES` 中增删，用于语义向量相似度计算。
- **自定义 detector**：继承 `BaseHarmfulDetector`，实现 `async def detect(text) -> HarmfulResult`，并加入 `run_pipeline(..., detectors=[...])`。

## 技术说明

- **Embedding**：`realtime/embedding_service.py` 提供抽象与 OpenAI 兼容实现；可选本地 `sentence-transformers`（如 `paraphrase-multilingual-MiniLM-L12-v2`）。
- **相似度**：余弦相似度；阈值默认 0.65，可在 `VectorThenLLMDetector(similarity_threshold=...)` 调整。
- **LLM**：沿用 OpenRouter/LLM 配置（`openrouter_api_key`, `openrouter_model`），用于向量候选的最终判定与严重度。
