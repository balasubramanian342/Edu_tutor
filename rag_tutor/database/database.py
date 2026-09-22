"""
Database Connection and Session Management
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from .models import Base


class Database:
    """Database connection and session management"""
    
    def __init__(self, database_url: str = "sqlite:///rag_tutor.db"):
        """
        Initialize database connection.
        
        Args:
            database_url: SQLAlchemy database URL
        """
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def create_tables(self):
        """Create all tables and migrate SQLite schema for newer fields."""
        Base.metadata.create_all(self.engine)

        if self.engine.dialect.name != "sqlite":
            return

        with self.engine.begin() as conn:
            cols = conn.execute(text("PRAGMA table_info(students)")).fetchall()
            existing = {row[1] for row in cols}

            if 'class_name' not in existing:
                conn.execute(text("ALTER TABLE students ADD COLUMN class_name VARCHAR(100)"))
            if 'exam_marks' not in existing:
                conn.execute(text("ALTER TABLE students ADD COLUMN exam_marks FLOAT"))
            if 'classification' not in existing:
                conn.execute(text("ALTER TABLE students ADD COLUMN classification VARCHAR(50)"))
            if 'attendance_percentage' not in existing:
                conn.execute(text("ALTER TABLE students ADD COLUMN attendance_percentage FLOAT"))
    
    def drop_tables(self):
        """Drop all tables (use with caution!)"""
        Base.metadata.drop_all(self.engine)
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.
        
        Usage:
            with db.get_session() as session:
                student = session.query(Student).first()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def init_db(self):
        """Initialize database with tables"""
        self.create_tables()
        print("Database initialized successfully")
