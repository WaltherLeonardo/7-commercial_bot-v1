# db.py
import os
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DB_URL", "sqlite:///data/cotizadores.db")

engine = create_engine(DB_URL, future=True)

def init_db():
    with engine.begin() as conn:
        # Enable WAL for better concurrency
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")