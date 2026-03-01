"""
Roleplay / AI 演绎 数据模型
- UtteranceRoleplay: LLM 生成的演绎内容（impact/rewrites/rehearsal）
"""

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class UtteranceRoleplay(SQLModel, table=True):
    __tablename__ = "utterance_roleplays"

    id: Optional[int] = Field(default=None, primary_key=True)
    utterance_id: str = Field(index=True)
    user_id: Optional[int] = Field(default=None, index=True)
    model: str = Field(default="")
    content_json: str = Field(default="{}")  # JSON string with impact/rewrites/rehearsal
    created_at: datetime = Field(default_factory=datetime.utcnow)
