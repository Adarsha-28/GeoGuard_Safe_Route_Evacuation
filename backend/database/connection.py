"""Database engine and session management for GeoGuard V2."""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.config import logger, settings

# SQLAlchemy connection pooling engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # Test connections for liveness before issuing queries
)

# Thread-safe session maker
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional SQLAlchemy session with clean lifecycle management."""
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_connection() -> tuple[bool, str]:
    """Verify active database connectivity and PostGIS availability."""
    try:
        with engine.connect() as conn:
            # Check basic connection
            conn.execute(text("SELECT 1;"))
            
            # Check PostGIS extension
            postgis_version = "unavailable"
            try:
                result = conn.execute(text("SELECT PostGIS_Version();"))
                row = result.fetchone()
                if row:
                    postgis_version = str(row[0])
            except Exception:
                pass

            return True, f"connected (PostGIS {postgis_version})"
    except Exception as e:
        logger.warning(f"Database connection check warning: {e}")
        return False, f"disconnected: {type(e).__name__}"
