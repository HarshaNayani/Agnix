from sqlalchemy.orm import Session
from backend.models import User, Chat, Message
from backend.schemas import UserCreate, ChatCreate, MessageCreate
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# User Functions
def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()


def create_user(db: Session, user: UserCreate):
    try:
        hashed_password = pwd_context.hash(user.password)
        db_user = User(
            username=user.username,
            email=user.email,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except:
        db.rollback()
        raise

# Chat Functions
def create_chat(db: Session, chat: ChatCreate, user_id: int):
    try:
        db_chat = Chat(**chat.dict(), user_id=user_id)
        db.add(db_chat)
        db.commit()
        db.refresh(db_chat)
        return db_chat
    except:
        db.rollback()
        raise

def get_chats(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(Chat)\
        .filter(Chat.user_id == user_id)\
        .offset(skip)\
        .limit(limit)\
        .all()

# Message Functions
def create_message(db: Session, message: MessageCreate, chat_id: int):
    try:
        db_message = Message(**message.dict(), chat_id=chat_id)
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        return db_message
    except:
        db.rollback()
        raise

def get_chat_messages(db: Session, chat_id: int, limit: int = 20):
    """
    Limit messages for AI (prevents token overflow)
    """
    return db.query(Message)\
        .filter(Message.chat_id == chat_id)\
        .order_by(Message.created_at.desc())\
        .limit(limit)\
        .all()[::-1]  # reverse to maintain order