"""
Database connection, session management, and base declarative class for SQLAlchemy.
Supports both SQLite (local development) and PostgreSQL (Supabase / Render / Cloud production).
"""
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import settings


def get_normalized_database_url(raw_url: str) -> str:
    """
    Normalizes PostgreSQL connection strings from cloud platforms (Supabase, Render)
    to use the modern 'postgresql+psycopg' driver.
    """
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+psycopg://", 1)
    if raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+"):
        return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_url


normalized_db_url = get_normalized_database_url(settings.DATABASE_URL)

connect_args = {}
engine_kwargs = {"echo": False}

if normalized_db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    # PostgreSQL connection pool settings for production
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
    })

engine = create_engine(
    normalized_db_url,
    connect_args=connect_args,
    **engine_kwargs,
)

# Factory for creating fresh database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy database models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session per request
    and guarantees it is closed when the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Creates all database tables defined in models if they do not exist."""
    if normalized_db_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    else:
        try:
            Base.metadata.create_all(bind=engine, checkfirst=True)
        except Exception:
            pass

    # Ensure optional media columns exist in existing databases without requiring full migrations
    with engine.begin() as conn:
        for col_def in [
            "ALTER TABLE campaigns ADD COLUMN media_url VARCHAR(500)",
            "ALTER TABLE campaigns ADD COLUMN media_type VARCHAR(20)",
        ]:
            try:
                conn.execute(text(col_def))
            except Exception:
                pass
