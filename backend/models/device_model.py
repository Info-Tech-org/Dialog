from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class Device(SQLModel, table=True):
    """Device model — binds a physical device (ESP32) to a user account"""

    __tablename__ = "devices"

    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(unique=True, index=True)
    user_id: Optional[int] = Field(default=None, index=True, foreign_key="users.id")
    name: str = Field(default="")
    is_online: bool = Field(default=False)
    last_seen: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
