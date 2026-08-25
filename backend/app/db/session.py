"""
FinSight — SQLAlchemy Engine & Session
Provides get_db() dependency for FastAPI route injection.
Phase 7: pool tuning, get_db_direct for health checks.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,        # Phase 7 tuning per §17.3
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,   # recycle connections every 30 min
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a scoped DB session, closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_direct() -> Generator[Session, None, None]:
    """
    Non-dependency-injection version of get_db().
    Used in health checks and scripts where FastAPI DI is not available.
    Caller is responsible for calling .close() or using as generator.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
