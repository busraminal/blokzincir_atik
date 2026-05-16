"""
ATIK AI - Veritabanı Bağlantı Yöneticisi
PostgreSQL
"""
import logging
from typing import Optional, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from ..config import config
from .exceptions import DatabaseError

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Merkezi veritabanı bağlantı yöneticisi
    
    Desteklenen veritabanları:
    - PostgreSQL: İlişkisel veriler (tesisler, atıklar, eşleşmeler)
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._engine = None
        self._session_factory = None
        self._initialized = True
    
    # =========================================================================
    # PostgreSQL
    # =========================================================================
    
    def get_engine(self):
        """SQLAlchemy engine al veya oluştur"""
        if self._engine is None:
            try:
                self._engine = create_engine(
                    config.postgres_url,
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,
                    echo=False
                )
                logger.info(f"PostgreSQL engine oluşturuldu")
            except Exception as e:
                raise DatabaseError(f"PostgreSQL bağlantı hatası: {e}")
        
        return self._engine
    
    def get_session_factory(self) -> sessionmaker:
        """Session factory al"""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.get_engine(),
                autocommit=False,
                autoflush=False
            )
        return self._session_factory
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Context manager ile session al"""
        session = self.get_session_factory()()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise DatabaseError(f"Session hatası: {e}")
        finally:
            session.close()
    
    def execute_sql(self, sql: str, params: dict = None) -> list:
        """Raw SQL çalıştır"""
        with self.session() as session:
            result = session.execute(text(sql), params or {})
            return result.fetchall()
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    def health_check(self) -> dict:
        """Tüm veritabanı bağlantılarını kontrol et"""
        status = {
            "postgresql": False
        }
        
        # PostgreSQL
        try:
            with self.session() as session:
                session.execute(text("SELECT 1"))
            status["postgresql"] = True
        except Exception as e:
            status["postgresql_error"] = str(e)
        
        return status
    
    def close(self):
        """Tüm bağlantıları kapat"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
        
        self._session_factory = None
        logger.info("Tüm veritabanı bağlantıları kapatıldı")


# Global instance
_db_manager: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Global DatabaseManager instance al"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency için session generator"""
    db = get_db()
    with db.session() as session:
        yield session
