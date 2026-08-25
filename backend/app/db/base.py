"""
FinSight — SQLAlchemy Declarative Base
All models import Base from here; do not import from session.py to avoid circular deps.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
