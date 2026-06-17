from pathlib import Path

from sqlalchemy import create_engine, inspect, text
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
    """Create all tables if they don't exist, then run light migrations."""
    Base.metadata.create_all(engine)
    _migrate_applications()
    _migrate_jobs()


def _migrate_jobs():
    """Add the saved / from_last_search columns to an existing jobs table."""
    insp = inspect(engine)
    if "jobs" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("jobs")}
    added = []
    with engine.begin() as conn:
        if "saved" not in existing:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN saved BOOLEAN DEFAULT 0"))
            added.append("saved")
        if "from_last_search" not in existing:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN from_last_search BOOLEAN DEFAULT 0"))
            # Backfill: treat current jobs as the latest search so the page isn't empty.
            conn.execute(text("UPDATE jobs SET from_last_search = 1"))
            added.append("from_last_search")
        if "match_score" not in existing:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN match_score INTEGER"))
            added.append("match_score")


def _migrate_applications():
    """Add the new pipeline columns to an existing applications table (SQLite-safe)."""
    insp = inspect(engine)
    if "applications" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("applications")}
    new_cols = {
        "stage": "VARCHAR DEFAULT 'postulado'",
        "archived": "BOOLEAN DEFAULT 0",
        "stage_entered_at": "DATETIME",
        "outcome": "VARCHAR",
        "priority": "VARCHAR",
        "details": "TEXT",
    }
    added_stage = "stage" not in existing
    with engine.begin() as conn:
        for name, ddl in new_cols.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE applications ADD COLUMN {name} {ddl}"))
        if added_stage:
            # Backfill the pipeline stage from the legacy status.
            conn.execute(text(
                "UPDATE applications SET stage = CASE status "
                "WHEN 'applied' THEN 'postulado' "
                "WHEN 'interview' THEN 'entrevista' "
                "WHEN 'offer' THEN 'oferta' "
                "WHEN 'rejected' THEN 'cerrado' "
                "ELSE 'postulado' END "
                "WHERE stage IS NULL OR stage = ''"
            ))
            conn.execute(text(
                "UPDATE applications SET stage_entered_at = created_at "
                "WHERE stage_entered_at IS NULL"
            ))


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()
