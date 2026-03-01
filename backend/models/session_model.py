from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class Session(SQLModel, table=True):
    """Session model representing a recording session"""

    __tablename__ = "sessions"

    session_id: str = Field(primary_key=True)
    device_id: str = Field(index=True)
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    audio_path: Optional[str] = None
    harmful_count: int = Field(default=0)
    cos_key: Optional[str] = None
    user_id: Optional[int] = Field(default=None, index=True)
