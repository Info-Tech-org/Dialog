"""
Review / 复盘相关数据模型
- UtteranceFeedback: 用户对 utterance 的反馈（误报、收藏、笔记）
- UtteranceAnalysis: LLM 对单条 utterance 的分析（severity/category/explanation/suggestion）
- SessionHighlight: 本次会话的 highlight 片段
- SessionSummary: 会话级别的 LLM 摘要
"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class UtteranceFeedback(SQLModel, table=True):
    __tablename__ = "utterance_feedback"

    id: Optional[int] = Field(default=None, primary_key=True)
    utterance_id: str = Field(index=True)
    session_id: str = Field(index=True)
    user_id: Optional[int] = Field(default=None, index=True)

    is_false_positive: bool = Field(default=False)   # 误报
    is_flagged: bool = Field(default=False)           # 需要关注
    is_starred: bool = Field(default=False)           # 收藏
    note: Optional[str] = Field(default=None)         # 笔记

    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        table = True


class UtteranceAnalysis(SQLModel, table=True):
    __tablename__ = "utterance_analysis"

    id: Optional[int] = Field(default=None, primary_key=True)
    utterance_id: str = Field(index=True, unique=True)
    session_id: str = Field(index=True)

    severity: int = Field(default=0)          # 0-5
    category: str = Field(default="")         # 辱骂/威胁/贬低等
    explanation: str = Field(default="")      # 解释
    suggestion: str = Field(default="")       # 替代说法

    generated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        table = True


class SessionHighlight(SQLModel, table=True):
    __tablename__ = "session_highlights"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    utterance_id: str = Field(index=True)

    score: float = Field(default=0.0)     # 重要性评分 0-1
    reason: str = Field(default="")       # highlight 原因
    rank: int = Field(default=0)          # 排序

    generated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        table = True


class SessionSummary(SQLModel, table=True):
    __tablename__ = "session_summaries"

    session_id: str = Field(primary_key=True)
    summary_text: str = Field(default="")
    top_category: str = Field(default="")
    max_severity: int = Field(default=0)

    generated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        table = True
