import uuid
from datetime import datetime
from typing import Dict, Optional
from sqlmodel import Session as DBSession, select
from models import Session, engine
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages recording sessions"""

    def __init__(self):
        self.active_sessions: Dict[str, Session] = {}

    def create_session(self, device_id: str) -> str:
        """
        Create a new recording session

        Args:
            device_id: Device identifier

        Returns:
            session_id: Generated session ID
        """
        session_id = str(uuid.uuid4())

        session = Session(
            session_id=session_id,
            device_id=device_id,
            start_time=datetime.utcnow(),
        )

        # Save to database
        with DBSession(engine) as db:
            db.add(session)
            db.commit()
            db.refresh(session)

        # Store in memory
        self.active_sessions[session_id] = session

        logger.info(f"Created session {session_id} for device {device_id}")
        return session_id

    def end_session(self, session_id: str, audio_path: str, harmful_count: int = 0):
        """
        End a recording session

        Args:
            session_id: Session identifier
            audio_path: Path to recorded audio file
            harmful_count: Number of harmful utterances detected
        """
        if session_id not in self.active_sessions:
            logger.warning(f"Session {session_id} not found in active sessions")
            return

        # Update database
        with DBSession(engine) as db:
            session = db.get(Session, session_id)
            if session:
                session.end_time = datetime.utcnow()
                session.audio_path = audio_path
                session.harmful_count = harmful_count
                db.add(session)
                db.commit()

        # Remove from active sessions
        del self.active_sessions[session_id]

        logger.info(f"Ended session {session_id}")

    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID

        Args:
            session_id: Session identifier

        Returns:
            Session object or None
        """
        # Check active sessions first
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]

        # Query database
        with DBSession(engine) as db:
            session = db.get(Session, session_id)
            return session

    def increment_harmful_count(self, session_id: str):
        """
        Increment harmful utterance count for session

        Args:
            session_id: Session identifier
        """
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            # Note: This updates the in-memory object
            # Will be persisted when session ends
            if not hasattr(session, '_harmful_count'):
                session._harmful_count = 0
            session._harmful_count += 1
