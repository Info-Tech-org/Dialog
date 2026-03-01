from sqlmodel import SQLModel, Field
from typing import Optional
import uuid


class Utterance(SQLModel, table=True):
    """Utterance model representing a single speech segment"""

    __tablename__ = "utterances"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="sessions.session_id", index=True)
    start: float  # Start time in seconds
    end: float  # End time in seconds
    speaker: str  # "A" or "B"
    text: str
    harmful_flag: bool = Field(default=False)
