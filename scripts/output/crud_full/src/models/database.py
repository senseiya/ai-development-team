from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.config import settings
from src.models.task import Base


def get_engine():
    """
    Creates and returns a SQLAlchemy engine based on the application settings.

    Returns:
        sqlalchemy.engine.Engine: The configured SQLAlchemy engine.
    """
    return create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
        echo=settings.DATABASE_ECHO,
    )


engine = get_engine()

# SessionLocal is a factory for producing new database sessions.
# Each session is a handle to a database connection pool.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """
    Initializes the database by creating all tables defined in the metadata.
    Should be called during application startup.
    """
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    Dependency generator for FastAPI to provide a database session per request.
    Yields a new session and ensures it is closed after the request is processed.

    Yields:
        sqlalchemy.orm.Session: A database session instance.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()