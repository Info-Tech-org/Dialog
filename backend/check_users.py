from sqlmodel import Session, select, create_engine
from models.user_model import User

engine = create_engine('sqlite:///data/family_emotion.db')

with Session(engine) as session:
    users = session.exec(select(User)).all()
    print(f'Found {len(users)} users in database:')
    for u in users:
        print(f'  - Username: {u.username}, Email: {u.email}')
