from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.ext.mutable import MutableDict
from app.db.base import Base


# Use a portable JSON column: Text for generic, JSONB for Postgres, JSON for SQLite
try:
    from sqlalchemy import JSON as SA_JSON
except Exception:
    SA_JSON = None  # type: ignore


def _json_column():
    # Prefer generic JSON if available; otherwise fallback to Text
    if SA_JSON is not None:
        return MutableDict.as_mutable(SA_JSON)
    return Text


class SchemaSnapshot(Base):
    __tablename__ = "schema_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, index=True, nullable=False)
    name = Column(String(255), nullable=False, default="")
    schema_json = Column(_json_column(), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
