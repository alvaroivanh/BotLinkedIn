from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings
from src.db.models import Base


def get_db_url() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        db_path = Path(url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return url


engine = create_engine(get_db_url(), echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()
