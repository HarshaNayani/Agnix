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
    "sqlite:///./database.db"  # single file at project root, no missing-folder issue
)

# If the URL points at a sqlite file inside a subfolder, make sure that folder exists
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "", 1)
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

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