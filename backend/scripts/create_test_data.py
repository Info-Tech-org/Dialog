"""
Create test data for demonstration
创建测试数据用于演示
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from datetime import datetime, timedelta
import uuid
from sqlmodel import Session
from backend.models import create_db_and_tables, engine, Session as SessionModel, Utterance, User
from backend.api.auth import get_password_hash


def create_test_user():
    """创建测试用户"""
    with Session(engine) as db:
        # Check if user already exists
        from sqlmodel import select
        statement = select(User).where(User.username == "admin")
        existing_user = db.exec(statement).first()

        if existing_user:
            print("Test user 'admin' already exists")
            return

        user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            full_name="管理员",
            is_admin=True
        )

        db.add(user)
        db.commit()
        print("Created test user: admin / admin123")


def create_test_sessions():
    """创建测试会话数据"""
    with Session(engine) as db:
        # 删除现有测试数据
        from sqlmodel import select
        statement = select(SessionModel)
        sessions = db.exec(statement).all()
        for session in sessions:
            db.delete(session)
        db.commit()

        # 创建 3 个测试会话
        now = datetime.utcnow()

        # 会话 1: 有2条有害语句
        session1_id = str(uuid.uuid4())
        session1 = SessionModel(
            session_id=session1_id,
            device_id="test_device_001",
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=2) + timedelta(minutes=5),
            audio_path="./data/audio/test_session_1.wav",
            harmful_count=2
        )
        db.add(session1)

        # 会话1的对话内容
        utterances1 = [
            Utterance(
                session_id=session1_id,
                start=0.0,
                end=3.2,
                speaker="A",
                text="今天数学考试考得怎么样？",
                harmful_flag=False
            ),
            Utterance(
                session_id=session1_id,
                start=3.5,
                end=5.8,
                speaker="B",
                text="不太好，只考了75分。",
                harmful_flag=False
            ),
            Utterance(
                session_id=session1_id,
                start=6.0,
                end=9.5,
                speaker="A",
                text="你怎么这么笨！这么简单的题都不会做！",
                harmful_flag=True
            ),
            Utterance(
                session_id=session1_id,
                start=10.0,
                end=12.3,
                speaker="B",
                text="对不起，我会努力的。",
                harmful_flag=False
            ),
            Utterance(
                session_id=session1_id,
                start=12.5,
                end=16.8,
                speaker="A",
                text="你看看别人家的孩子，人家考100分，你呢？真是让我失望！",
                harmful_flag=True
            ),
        ]

        for utt in utterances1:
            db.add(utt)

        # 会话 2: 有1条有害语句
        session2_id = str(uuid.uuid4())
        session2 = SessionModel(
            session_id=session2_id,
            device_id="test_device_001",
            start_time=now - timedelta(hours=5),
            end_time=now - timedelta(hours=5) + timedelta(minutes=3),
            audio_path="./data/audio/test_session_2.wav",
            harmful_count=1
        )
        db.add(session2)

        utterances2 = [
            Utterance(
                session_id=session2_id,
                start=0.0,
                end=2.5,
                speaker="A",
                text="作业做完了吗？",
                harmful_flag=False
            ),
            Utterance(
                session_id=session2_id,
                start=2.7,
                end=4.2,
                speaker="B",
                text="还没有，有点难。",
                harmful_flag=False
            ),
            Utterance(
                session_id=session2_id,
                start=4.5,
                end=7.8,
                speaker="A",
                text="又是这样！你就是懒，一点都不认真！",
                harmful_flag=True
            ),
        ]

        for utt in utterances2:
            db.add(utt)

        # 会话 3: 没有有害语句（正面示例）
        session3_id = str(uuid.uuid4())
        session3 = SessionModel(
            session_id=session3_id,
            device_id="test_device_002",
            start_time=now - timedelta(days=1),
            end_time=now - timedelta(days=1) + timedelta(minutes=4),
            audio_path="./data/audio/test_session_3.wav",
            harmful_count=0
        )
        db.add(session3)

        utterances3 = [
            Utterance(
                session_id=session3_id,
                start=0.0,
                end=2.8,
                speaker="A",
                text="今天在学校怎么样？",
                harmful_flag=False
            ),
            Utterance(
                session_id=session3_id,
                start=3.0,
                end=6.5,
                speaker="B",
                text="很好！老师今天表扬我了，说我进步很大。",
                harmful_flag=False
            ),
            Utterance(
                session_id=session3_id,
                start=7.0,
                end=10.2,
                speaker="A",
                text="真棒！继续保持，妈妈为你感到骄傲。",
                harmful_flag=False
            ),
            Utterance(
                session_id=session3_id,
                start=10.5,
                end=13.8,
                speaker="B",
                text="谢谢妈妈！我会继续努力的。",
                harmful_flag=False
            ),
        ]

        for utt in utterances3:
            db.add(utt)

        db.commit()
        print(f"Created 3 test sessions with utterances")
        print(f"- Session 1: {session1_id} (2 harmful utterances)")
        print(f"- Session 2: {session2_id} (1 harmful utterance)")
        print(f"- Session 3: {session3_id} (0 harmful utterances)")


if __name__ == "__main__":
    print("Creating database tables...")
    create_db_and_tables()

    print("\nCreating test user...")
    create_test_user()

    print("\nCreating test sessions...")
    create_test_sessions()

    print("\n✅ Test data created successfully!")
    print("\nYou can now:")
    print("1. Login with: username=admin, password=admin123")
    print("2. View sessions at: http://localhost:3000/sessions")
    print("3. API docs at: http://localhost:8000/docs")
