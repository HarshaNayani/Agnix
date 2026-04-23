from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

# -------------------------------
# Database URL
# -------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./database/database.db"  # correct path
)

# -------------------------------
# Engine
# -------------------------------
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=True  # enables SQL logs (useful for debugging)
)

# -------------------------------
# Session
# -------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# -------------------------------
# Base Model
# -------------------------------
Base = declarative_base()

# -------------------------------
# Dependency
# -------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()