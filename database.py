import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_session():
    return SessionLocal()


def init_db():
    """Create all tables if they don't exist. Safe to call multiple times."""
    import models  # noqa: F401 — imported so Base picks up the table definitions
    Base.metadata.create_all(engine)
