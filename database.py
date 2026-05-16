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
    _seed_masters()


def _seed_masters():
    """Pre-load demo master artisans so matching works immediately."""
    session = Session()
    if session.query(Master).count() > 0:
        session.close()
        return

    seed = [
        Master(phone="+254700000001", name="Mzee Kamau",    location="Gikomba",    trade="welding",    years_exp=15, bio="Arc and MIG welding, gate fabrication, structural steel", capacity=2),
        Master(phone="+254700000002", name="Mama Wanjiru",  location="Eastleigh",  trade="tailoring",  years_exp=10, bio="Fashion design, sewing machine repair, bridal wear",      capacity=3),
        Master(phone="+254700000003", name="Baba Oduya",    location="Kamukunji",  trade="plumbing",   years_exp=12, bio="Pipe fitting, drainage, solar water heating install",    capacity=2),
        Master(phone="+254700000004", name="Ali Hassan",    location="Mombasa",    trade="carpentry",  years_exp=20, bio="Furniture making, roofing, wood joinery",                capacity=1),
        Master(phone="+254700000005", name="Grace Atieno",  location="Kisumu",     trade="hairdressing",years_exp=8, bio="Natural hair, braiding, salon management",              capacity=4),
        Master(phone="+254700000006", name="Peter Mutua",   location="Machakos",   trade="motorcycle", years_exp=6,  bio="Motorbike repair, engine overhaul, electrical systems",  capacity=2),
        Master(phone="+254700000007", name="David Kipchoge",location="Eldoret",    trade="masonry",    years_exp=18, bio="Block laying, plastering, tiling, construction",         capacity=3),
        Master(phone="+254700000008", name="Fatuma Omar",   location="Mombasa",    trade="embroidery", years_exp=9,  bio="Kitenge designs, embroidery, textile printing",          capacity=2),
    ]
    session.bulk_save_objects(seed)
    session.commit()
    session.close()
    print("✅ Seeded master artisans database.")


def get_session():
    return Session()
