"""
Harmful language detection rules.
- 绝对关键词：命中即判有害，不依赖 LLM，确保不错过。
- 有害概念参考句：用于语义向量化检索，与向量检测器配合。
"""

# 预先的多个绝对关键词：命中任一即判定有害，短路后续检测
ABSOLUTE_KEYWORDS = [
    # 侮辱性词汇
    "没用", "废物", "蠢", "笨蛋", "白痴", "傻子", "混蛋", "垃圾", "窝囊废",
    "丢人", "丢脸", "羞耻", "丢死人", "没出息",

    # 脏话粗口
    "操你妈", "他妈的", "妈的", "去你妈的", "你妈", "草你妈", "日你妈",
    "操", "草", "日", "shit", "fuck", "damn",

    # 威胁性语言
    "滚出去", "闭嘴", "打死你", "去死", "滚", "揍你", "杀了你",
    "不要你了", "丢掉你", "不认你", "流浪去", "扔出去",

    # 情感伤害
    "讨厌你", "后悔生你", "不爱你", "恨你", "烦死了",
    "看见你就烦", "懒得理你", "不配", "别烦我",

    # 否定贬低
    "就知道", "永远不会", "从来没有", "一点用都没有",
    "什么都不会", "什么都做不好", "这么简单都不会",
]

# 兼容旧变量名
HARMFUL_KEYWORDS = ABSOLUTE_KEYWORDS

# 有害概念参考句：用于语义向量空间检索，覆盖辱骂/威胁/贬低/情感伤害等
# 向量检测器将输入与这些句子的 embedding 做相似度，高于阈值则进入 LLM 筛选
HARMFUL_REFERENCES = [
    "你真是没用，废物一个",
    "蠢死了，笨蛋",
    "滚出去，不要你了",
    "打死你，去死",
    "我后悔生了你",
    "看见你就烦，别烦我",
    "你什么都不行，什么都做不好",
    "不爱你，讨厌你",
    "闭嘴，滚",
    "不要你了，扔出去",
    "丢人现眼，没出息",
    "恨你，懒得理你",
    "这么简单都不会，废物",
    "威胁恐吓孩子",
    "贬低否定孩子",
    "辱骂脏话",
    "情感冷暴力",
]


def is_harmful(text: str) -> bool:
    """
    Check if text contains harmful keywords

    Args:
        text: Text to check

    Returns:
        True if text contains any harmful keyword
    """
    text_lower = text.lower()
    return any(kw in text_lower for kw in ABSOLUTE_KEYWORDS)


def get_harmful_keywords(text: str) -> list[str]:
    """
    Get list of harmful keywords found in text (uses ABSOLUTE_KEYWORDS).
    """
    text_lower = text.lower()
    return [kw for kw in ABSOLUTE_KEYWORDS if kw in text_lower]


async def is_harmful_advanced(text: str, use_llm: bool = True) -> tuple[bool, dict]:
    """
    高级有害语检测：use_llm=True 时走默认 pipeline（绝对关键词 → 语义向量 → LLM 筛选）；
    use_llm=False 时仅关键词检测。

    Returns:
        (is_harmful, details) tuple；details 含 method/keywords/severity/category/explanation 等。
    """
    from .detector_pipeline import run_pipeline, get_default_pipeline
    from .keyword_detector import KeywordDetector

    if use_llm:
        detectors = get_default_pipeline(use_vector_llm=True)
    else:
        detectors = [KeywordDetector()]
    return await run_pipeline(text, detectors=detectors, short_circuit_on_harmful=True)
