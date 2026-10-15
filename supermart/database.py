# supermart/database.py - synchronous SQLAlchemy 2.x session pattern
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from supermart.config import settings
 
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=30,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
 
def get_db():
    with SessionLocal() as db:
        yield db