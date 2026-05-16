"""
database.py — SQLite via SQLAlchemy ORM
Tables: Youth, Master, Match
"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Float, Text, DateTime, ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from config import DATABASE_URL

engine  = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base    = declarative_base()


class Youth(Base):
    __tablename__ = "youth"

    id           = Column(Integer, primary_key=True)
    phone        = Column(String(20), unique=True, nullable=False)
    name         = Column(String(100))
    location     = Column(String(100))
    trade        = Column(String(100))          # e.g. "welding", "tailoring"
    skill_level  = Column(String(50))           # beginner / intermediate
    user_type    = Column(String(20), default="job_seeker")  # employer | job_seeker
    notify_phone = Column(String(20))           # number to SMS when a match is found
    raw_speech   = Column(Text)                 # original transcript from voice
    embedding    = Column(Text)                 # JSON list of floats
    created_at   = Column(DateTime, default=datetime.utcnow)
    session_data = Column(Text, default="{}")   # USSD session state JSON

    matches = relationship("Match", back_populates="youth")


class Master(Base):
    __tablename__ = "master"

    id          = Column(Integer, primary_key=True)
    phone       = Column(String(20), unique=True, nullable=False)
    name        = Column(String(100))
    location    = Column(String(100))
    trade       = Column(String(100))
    years_exp   = Column(Integer)
    bio         = Column(Text)                  # what they teach
    capacity    = Column(Integer, default=2)    # open apprentice slots
    embedding   = Column(Text)                  # JSON list of floats
    verified    = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    matches = relationship("Match", back_populates="master")


class Match(Base):
    __tablename__ = "match"

    id         = Column(Integer, primary_key=True)
    youth_id   = Column(Integer, ForeignKey("youth.id"))
    master_id  = Column(Integer, ForeignKey("master.id"))
    score      = Column(Float)                  # cosine similarity 0-1
    status     = Column(String(20), default="pending")  # pending/accepted/declined
    created_at = Column(DateTime, default=datetime.utcnow)

    youth  = relationship("Youth",  back_populates="matches")
    master = relationship("Master", back_populates="matches")


def init_db():
    Base.metadata.create_all(engine)
    # Lightweight migration: add notify_phone to pre-existing SQLite databases.
    try:
        with engine.connect() as conn:
            cols = [r[1] for r in conn.exec_driver_sql(
                "PRAGMA table_info(youth)").fetchall()]
            if "notify_phone" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE youth ADD COLUMN notify_phone VARCHAR(20)")
    except Exception:
        pass


def get_session():
    return Session()
