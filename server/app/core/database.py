from sqlalchemy import MetaData, create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

_connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
if settings.DATABASE_URL.startswith("postgresql+psycopg"):
    from pathlib import Path
    _connect_args = {"prepare_threshold": None, "connect_timeout": 10, "sslmode": "verify-full", "sslrootcert": str(Path(__file__).resolve().parents[2] / "certs" / "supabase.crt")}
engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args,
                       **({"poolclass": NullPool, "hide_parameters": True} if settings.CLOUD_MODE else {}))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    metadata = MetaData(schema=settings.DATABASE_SCHEMA)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
