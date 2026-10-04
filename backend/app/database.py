from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def sqlite_integrity(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def begin_auth_write(db):
    """Serialize SQLite writers before reads; PostgreSQL uses explicit row locks."""
    if db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))


def validate_disposable_database(target_engine, parent: Path):
    """Required guard before test schema destruction."""
    url = target_engine.url
    if url.drivername != "sqlite" or not url.database or url.database == ":memory:":
        raise ValueError("An explicit disposable SQLite database is required")
    path = Path(url.database).resolve()
    if not path.is_relative_to(parent.resolve()) or path.name == "scamshield.db":
        raise ValueError("Refusing non-disposable database target")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
