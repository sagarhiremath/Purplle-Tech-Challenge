from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL, STORE_LAYOUT_PATH


class Base(DeclarativeBase):
    pass


class EventRecord(Base):
    __tablename__ = "events"

    event_id = Column(String(36), primary_key=True)
    store_id = Column(String(64), index=True, nullable=False)
    camera_id = Column(String(64), nullable=False)
    visitor_id = Column(String(64), index=True, nullable=False)
    event_type = Column(String(64), index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    zone_id = Column(String(64), nullable=True)
    dwell_ms = Column(Integer, default=0)
    is_staff = Column(Boolean, default=False)
    confidence = Column(Float, nullable=False)
    metadata_json = Column(Text, default="{}")
    ingested_at = Column(DateTime, default=datetime.utcnow)


class POSTransactionRecord(Base):
    __tablename__ = "pos_transactions"

    transaction_id = Column(String(64), primary_key=True)
    store_id = Column(String(64), index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    basket_value_inr = Column(Float, nullable=False)


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_store_layout() -> dict:
    with STORE_LAYOUT_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def get_store_ids() -> list[str]:
    layout = load_store_layout()
    return [store["store_id"] for store in layout["stores"]]
